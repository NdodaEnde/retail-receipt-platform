"""
Duplicate slip guard — one till slip enters the draw once.

Two very different people send the same slip twice:
  * the same customer, by mistake (double-send, resend after a slow reply)
    -> friendly "we already have this one", nothing saved, no penalty
  * a different customer (a shared photo — family, WhatsApp group, or a ring)
    -> saved, kept out of the draw, sent to admin review, told neutrally, and a
       fraud signal is logged with both numbers, locations and the match kind

How a duplicate is recognised:
  same_image        256-bit perceptual hash within RESEND_BITS (the same photo, whatever
                    OCR read — one photo was read as R1 503 and as R1 898), or within
                    IMAGE_NEAR_BITS plus the same total (re-compressed / screenshotted)
Every other kind requires the same total — a slip has exactly one:
  same_transaction  same printed transaction/till reference at a compatible shop
  same_content      same set of line prices (>= 3 lines, or >= 2 plus the same
                    printed time), or same printed time + date at a compatible shop

Before OCR, an image within RESEND_BITS of one the *same* customer sent recently is
a resend — answered without spending an OCR call.

Pure matching functions + thin async DB helpers (find_duplicate, log_signal).
"""
from __future__ import annotations

import io
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

WINDOW_DAYS = 60          # a slip older than this can't win anyway
HASH_SIZE = 16            # 16x16 difference hash = 256 bits
IMAGE_NEAR_BITS = 20      # ~8% of bits: same photo after recompression/screenshot (+ same total required)
RESEND_BITS = 6           # effectively the same image file
# Calibrated on 147 real slips (Oct 2026): copies 0 bits apart, different slips >= 56.
RECENT_TTL_SECONDS = 30 * 60

SAME_IMAGE, SAME_TRANSACTION, SAME_CONTENT = "same_image", "same_transaction", "same_content"


# ── Image fingerprint ────────────────────────────────────────────────────────

def image_dhash(image_bytes: bytes, size: int = HASH_SIZE) -> Optional[str]:
    """Difference hash: grayscale, shrink to (size+1) x size, compare neighbours.
    Survives JPEG recompression and resizing; hex string of size*size bits."""
    if not image_bytes:
        return None
    try:
        from PIL import Image, ImageOps
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except Exception:
            pass
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("L").resize((size + 1, size), Image.LANCZOS)
        px = list(img.getdata())
        bits = 0
        for row in range(size):
            for col in range(size):
                left, right = px[row * (size + 1) + col], px[row * (size + 1) + col + 1]
                bits = (bits << 1) | (1 if left > right else 0)
        return f"{bits:0{size * size // 4}x}"
    except Exception as e:
        logger.warning(f"image hash failed: {str(e)[:100]}")
        return None


def hamming(a: Optional[str], b: Optional[str]) -> Optional[int]:
    if not a or not b or len(a) != len(b):
        return None
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# ── Slip identity (proposed by the LLM, verified against the printed text) ───

_TIME_RE = re.compile(r"^([01]?\d|2[0-3])[:hH.]([0-5]\d)(?::[0-5]\d)?$")


def verify_slip_time(proposed: Optional[str], raw_text: Optional[str]) -> Optional[str]:
    """HH:MM if `proposed` is a real clock time that is printed on the slip, else None."""
    if not proposed:
        return None
    m = _TIME_RE.match(str(proposed).strip())
    if not m:
        return None
    hh, mm = int(m.group(1)), m.group(2)
    if raw_text and not re.search(rf"(?<!\d)0?{hh}[:hH.]{mm}(?!\d)", raw_text):
        return None
    return f"{hh:02d}:{mm}"


def verify_transaction_ref(proposed: Optional[str], raw_text: Optional[str]) -> Optional[str]:
    """Normalised reference if it looks like one (has a digit, 4-30 chars) and is printed."""
    if not proposed:
        return None
    ref = re.sub(r"\s+", "", str(proposed)).upper()
    if not (4 <= len(ref) <= 30) or not re.search(r"\d", ref) or not re.fullmatch(r"[A-Z0-9/#:\-.]+", ref):
        return None
    if raw_text and ref not in re.sub(r"\s+", "", raw_text).upper():
        return None
    return ref


# ── Content matching (pure) ──────────────────────────────────────────────────

def _f(v) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def price_signature(items: Iterable[dict]) -> Tuple[int, ...]:
    """Sorted line totals in cents — name-insensitive, because two photos of one slip
    OCR names differently ('Meerendal' / 'Meerenda1') but read prices the same."""
    cents = []
    for it in items or []:
        total = _f(it.get("total_price"))
        if total is None:
            q, u = _f(it.get("quantity")), _f(it.get("unit_price"))
            total = q * u if q and u else None
        if total is not None and total > 0:
            cents.append(round(total * 100))
    return tuple(sorted(cents))


_STOP = {"the", "and", "pty", "ltd", "store", "shop", "cape", "town", "johannesburg", "pretoria", "durban"}


def _shop_tokens(name: Optional[str]) -> set:
    return {t for t in re.findall(r"[a-z]{3,}", (name or "").lower()) if t not in _STOP}


def shops_compatible(a: dict, b: dict) -> bool:
    if a.get("shop_id") and b.get("shop_id"):
        if a["shop_id"] == b["shop_id"]:
            return True
    ta, tb = _shop_tokens(a.get("shop_name")), _shop_tokens(b.get("shop_name"))
    if not ta or not tb:
        return True  # an unread shop name is not evidence of a different shop
    return bool(ta & tb)


def _dates_compatible(a: dict, b: dict) -> bool:
    da, db_ = (a.get("receipt_date") or "")[:10], (b.get("receipt_date") or "")[:10]
    return not da or not db_ or da == db_


def match_slip(new: dict, old: dict) -> Optional[str]:
    """The kind of duplicate `new` is of `old`, or None.
    Each dict: amount, shop_name, shop_id, receipt_date, slip_time, transaction_ref,
    image_hash, items."""
    dist = hamming(new.get("image_hash"), old.get("image_hash"))
    if dist is not None and dist <= RESEND_BITS:
        return SAME_IMAGE
    a, b = _f(new.get("amount")), _f(old.get("amount"))
    if not a or not b or abs(a - b) > 0.01:
        return None
    if not _dates_compatible(new, old):
        return None
    same_shop = shops_compatible(new, old)

    if new.get("transaction_ref") and new.get("transaction_ref") == old.get("transaction_ref") and same_shop:
        return SAME_TRANSACTION
    if dist is not None and dist <= IMAGE_NEAR_BITS:
        return SAME_IMAGE
    if not same_shop:
        return None
    same_time = bool(new.get("slip_time")) and new.get("slip_time") == old.get("slip_time")
    sig_new, sig_old = price_signature(new.get("items")), price_signature(old.get("items"))
    if sig_new and sig_new == sig_old and (len(sig_new) >= 3 or (len(sig_new) >= 2 and same_time)):
        return SAME_CONTENT
    both_dated = bool(new.get("receipt_date")) and bool(old.get("receipt_date"))
    if same_time and both_dated:
        return SAME_CONTENT
    return None


# ── Recent memory: slips not yet saved (pending location) or racing in ──────

_recent_images: Dict[str, List[Tuple[str, float]]] = {}
_recent_slips: List[Tuple[str, dict, float]] = []


def _prune(now: float):
    for phone in list(_recent_images):
        _recent_images[phone] = [(h, t) for h, t in _recent_images[phone] if now - t < RECENT_TTL_SECONDS]
        if not _recent_images[phone]:
            del _recent_images[phone]
    _recent_slips[:] = [s for s in _recent_slips if now - s[2] < RECENT_TTL_SECONDS]


def seen_image_recently(phone: str, image_hash: Optional[str]) -> bool:
    """Check-and-remember in one step (no await in between, so concurrent tasks can't
    both pass): True if this customer sent this image in the last 30 minutes."""
    if not image_hash:
        return False
    now = time.time()
    _prune(now)
    for h, _ in _recent_images.get(phone, []):
        d = hamming(h, image_hash)
        if d is not None and d <= RESEND_BITS:
            return True
    _recent_images.setdefault(phone, []).append((image_hash, now))
    return False


def match_recent_slip(phone: str, slip: dict) -> Optional[dict]:
    """Check-and-remember a just-read slip against slips read in the last 30 minutes
    (by anyone) that may not be in the database yet."""
    now = time.time()
    _prune(now)
    for other_phone, other, _ in _recent_slips:
        kind = match_slip(slip, other)
        if kind:
            return {"receipt_id": other.get("id"), "customer_phone": other_phone, "kind": kind,
                    "same_customer": other_phone == phone, "pending": True}
    _recent_slips.append((phone, slip, now))
    return None


# ── Database helpers ─────────────────────────────────────────────────────────

def _bare(phone: Optional[str]) -> str:
    return (phone or "").lstrip("+")


def _since() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).isoformat()


def find_resend(db, phone: str, image_hash: Optional[str]) -> Optional[dict]:
    """Pre-OCR: a saved receipt from this customer whose image is (nearly) identical."""
    if not image_hash or not db._column_exists("receipts", "image_hash"):
        return None
    bare = _bare(phone)
    try:
        rows = db.client.table("receipts").select("id,image_hash,created_at,shop_name,amount") \
            .in_("customer_phone", [bare, f"+{bare}"]).gte("created_at", _since()) \
            .neq("status", "rejected").not_.is_("image_hash", "null").limit(500).execute().data or []
    except Exception as e:
        logger.warning(f"resend lookup failed: {str(e)[:100]}")
        return None
    for r in rows:
        d = hamming(r.get("image_hash"), image_hash)
        if d is not None and d <= RESEND_BITS:
            return r
    return None


def find_duplicate(db, phone: str, slip: dict) -> Optional[dict]:
    """Earliest saved receipt (any customer, last WINDOW_DAYS) that `slip` duplicates.
    Returns {receipt_id, customer_phone, kind, same_customer, created_at} or None."""
    amount = _f(slip.get("amount"))
    if not amount:
        return None
    cols = ["id", "customer_phone", "shop_id", "shop_name", "amount", "receipt_date", "created_at", "status"]
    cols += [c for c in ("duplicate_of", "image_hash", "slip_time", "transaction_ref")
             if db._column_exists("receipts", c)]  # migration 009
    try:
        rows = db.client.table("receipts").select(",".join(cols)) \
            .gte("amount", amount - 0.01).lte("amount", amount + 0.01).gte("created_at", _since()) \
            .neq("status", "rejected").order("created_at").limit(200).execute().data or []
    except Exception as e:
        logger.warning(f"duplicate lookup failed: {str(e)[:100]}")
        return None
    rows = [r for r in rows if r["id"] != slip.get("id")]
    if not rows:
        return None
    items: Dict[str, list] = {}
    try:
        for row in db.client.table("receipt_items").select("receipt_id,quantity,unit_price,total_price") \
                .in_("receipt_id", [r["id"] for r in rows]).execute().data or []:
            items.setdefault(row["receipt_id"], []).append(row)
    except Exception as e:
        logger.warning(f"duplicate items lookup failed: {str(e)[:100]}")
    for r in rows:  # oldest first: point at the original, not at another copy
        kind = match_slip(slip, {**r, "items": items.get(r["id"], [])})
        if kind:
            return {"receipt_id": r.get("duplicate_of") or r["id"], "customer_phone": _bare(r["customer_phone"]),
                    "kind": kind, "same_customer": _bare(r["customer_phone"]) == _bare(phone),
                    "created_at": r.get("created_at")}
    return None


def log_signal(db, kind: str, phone: str, match: dict, receipt_id: Optional[str] = None,
               latitude: Optional[float] = None, longitude: Optional[float] = None,
               details: Optional[dict] = None) -> None:
    """Append to fraud_signals (migration 009). P-class: admin-only. Never raises."""
    try:
        db.client.table("fraud_signals").insert({
            "kind": kind,
            "customer_phone": _bare(phone),
            "receipt_id": receipt_id,
            "matched_receipt_id": match.get("receipt_id"),
            "matched_phone": _bare(match.get("customer_phone")),
            "match_kind": match.get("kind"),
            "same_customer": bool(match.get("same_customer")),
            "upload_latitude": latitude,
            "upload_longitude": longitude,
            "details": details or {},
        }).execute()
    except Exception as e:
        logger.warning(f"fraud signal not logged (run migration 009?): {str(e)[:120]}")


# ── Admin view: who shares slips with whom ──────────────────────────────────

def summarize_signals(signals: List[dict]) -> Dict:
    """Group phones linked by shared slips into clusters (union-find), plus per-phone counts.
    Same-customer resends are counted but never link phones."""
    parent: Dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    per_phone: Dict[str, dict] = {}
    for s in signals:
        p = _bare(s.get("customer_phone"))
        if not p:
            continue
        row = per_phone.setdefault(p, {"phone": p, "resends": 0, "cross_customer": 0,
                                       "partners": set(), "last_seen": None})
        ts = s.get("created_at")
        row["last_seen"] = max(filter(None, [row["last_seen"], ts]), default=None)
        if s.get("same_customer"):
            row["resends"] += 1
            continue
        row["cross_customer"] += 1
        m = _bare(s.get("matched_phone"))
        if m:
            row["partners"].add(m)
            per_phone.setdefault(m, {"phone": m, "resends": 0, "cross_customer": 0,
                                     "partners": set(), "last_seen": None})["partners"].add(p)
            parent[find(p)] = find(m)

    clusters: Dict[str, dict] = {}
    for p, row in per_phone.items():
        if not row["partners"]:
            continue
        c = clusters.setdefault(find(p), {"phones": [], "shared_slips": 0})
        c["phones"].append(p)
        c["shared_slips"] += row["cross_customer"]
    out_clusters = sorted(({"phones": sorted(c["phones"]), "size": len(c["phones"]),
                            "shared_slips": c["shared_slips"]} for c in clusters.values()),
                          key=lambda c: (-c["shared_slips"], -c["size"]))
    phones = sorted(({**r, "partners": len(r["partners"])} for r in per_phone.values()),
                    key=lambda r: (-r["cross_customer"], -r["resends"]))
    return {"clusters": out_clusters, "phones": phones, "signals": len(signals)}
