"""
Fingerprint every stored receipt (image hash) and mark the later copies of a slip
as duplicates (migration 009), using the same rules as live ingestion
(duplicate_guard.match_slip).

    python scripts/backfill_duplicates.py            # dry run — groups + image-distance calibration
    python scripts/backfill_duplicates.py --apply    # write image_hash + duplicate_of/kind, take copies out of the draw

The original (earliest) receipt of each group is untouched. Copies get
duplicate_of / duplicate_kind and draw_eligible=false — nothing is deleted.
Historical copies are not logged as fraud signals (pre-launch testing).
"""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from database import get_database  # noqa: E402
from duplicate_guard import image_dhash, hamming, match_slip, IMAGE_NEAR_BITS, RESEND_BITS  # noqa: E402


def fetch_all(client, table, cols):
    rows, start = [], 0
    while True:
        page = client.table(table).select(cols).range(start, start + 999).execute().data or []
        rows += page
        if len(page) < 1000:
            return rows
        start += 1000


def main(apply: bool):
    db = get_database()
    client = db.client
    if apply and not db._column_exists("receipts", "duplicate_of"):
        print("❌ migration 009 not applied (receipts.duplicate_of missing) — run it first")
        return

    receipts = fetch_all(client, "receipts",
                         "id,customer_phone,shop_id,shop_name,amount,receipt_date,created_at,status,image_url,draw_eligible")
    receipts = [r for r in receipts if r.get("status") != "rejected"]
    receipts.sort(key=lambda r: r["created_at"])
    items = {}
    for it in fetch_all(client, "receipt_items", "receipt_id,quantity,unit_price,total_price"):
        items.setdefault(it["receipt_id"], []).append(it)

    print(f"Hashing {sum(1 for r in receipts if r.get('image_url'))} images…")
    with httpx.Client(timeout=30) as http:
        for r in receipts:
            r["items"] = items.get(r["id"], [])
            r["image_hash"] = None
            if r.get("image_url"):
                for attempt in range(3):
                    try:
                        resp = http.get(r["image_url"])
                        if resp.status_code == 200:
                            r["image_hash"] = image_dhash(resp.content)
                        break
                    except Exception:
                        time.sleep(2 ** attempt)

    # chronological grouping: each receipt is a copy of the earliest earlier match
    original_of, kinds = {}, Counter()
    for i, r in enumerate(receipts):
        for prev in receipts[:i]:
            kind = match_slip(r, prev)
            if kind:
                original_of[r["id"]] = (original_of.get(prev["id"], (prev["id"], None))[0], kind)
                kinds[kind] += 1
                break

    # calibration: image distance for copies vs for different slips
    by_id = {r["id"]: r for r in receipts}
    dup_d = [hamming(by_id[c]["image_hash"], by_id[o]["image_hash"]) for c, (o, _) in original_of.items()]
    dup_d = sorted(d for d in dup_d if d is not None)
    hashed = [r for r in receipts if r["image_hash"]]
    copies = set(original_of)
    diff_d = sorted(hamming(a["image_hash"], b["image_hash"])
                    for i, a in enumerate(hashed) for b in hashed[i + 1:]
                    if a["id"] not in copies and b["id"] not in copies)
    print(f"\nimage distance (of 256 bits): copies {dup_d[:10]}{'…' if len(dup_d) > 10 else ''}")
    print(f"  different slips: min {diff_d[:8]}  (thresholds: resend ≤{RESEND_BITS}, near ≤{IMAGE_NEAR_BITS})")
    print(f"  different-slip pairs within near threshold: {sum(1 for d in diff_d if d <= IMAGE_NEAR_BITS)} of {len(diff_d)}")

    groups = Counter(o for o, _ in original_of.values())
    print(f"\n{len(receipts)} receipts → {len(original_of)} copies of {len(groups)} slips  {dict(kinds)}")
    for orig, n in groups.most_common():
        o = by_id[orig]
        phones = {by_id[c]["customer_phone"][-4:] for c, (oo, _) in original_of.items() if oo == orig}
        print(f"  {n + 1}x  {str(o['shop_name'])[:30]:30} R{o['amount']:>9}  {o['created_at'][:10]}  "
              f"phones …{o['customer_phone'][-4:]} + {sorted(phones)}")

    if not apply:
        print("\n(dry run — nothing written)")
        return
    n = 0
    for r in receipts:
        upd = {"image_hash": r["image_hash"]} if r["image_hash"] else {}
        if r["id"] in original_of:
            orig, kind = original_of[r["id"]]
            upd.update({"duplicate_of": orig, "duplicate_kind": kind, "draw_eligible": False})
        if upd:
            client.table("receipts").update(upd).eq("id", r["id"]).execute()
            n += 1
    print(f"\n✅ {n} receipts updated ({len(original_of)} marked as copies)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    main(ap.parse_args().apply)
