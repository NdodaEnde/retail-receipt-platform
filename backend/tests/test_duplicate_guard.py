"""
Unit tests for duplicate_guard (pure rules — no network, no database).

    python tests/test_duplicate_guard.py
"""
import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402
import duplicate_guard as dg  # noqa: E402

failures = []


def check(name, cond):
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond:
        failures.append(name)


def slip_photo(seed: int) -> Image.Image:
    """A receipt-ish photo: white strip on a dark table, rows of 'text' blocks."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (600, 900), (40 + seed % 30, 35, 30))
    d = ImageDraw.Draw(img)
    d.rectangle([150, 40, 450, 860], fill=(245, 245, 240))
    for y in range(70, 840, 22):
        w = rnd.randint(60, 260)
        d.rectangle([170, y, 170 + w, y + 10], fill=(30, 30, 30))
        d.rectangle([380, y, 380 + rnd.randint(20, 50), y + 10], fill=(30, 30, 30))
    return img


def jpeg(img: Image.Image, quality=90, scale=1.0) -> bytes:
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


print("image fingerprint")
a = slip_photo(1)
h_orig = dg.image_dhash(jpeg(a))
h_recompressed = dg.image_dhash(jpeg(a, quality=35, scale=0.5))   # WhatsApp-style re-encode
h_other = dg.image_dhash(jpeg(slip_photo(2)))
check("hash is 256 bits", h_orig is not None and len(h_orig) == 64)
check("same bytes -> distance 0", dg.hamming(h_orig, dg.image_dhash(jpeg(a))) == 0)
d_re = dg.hamming(h_orig, h_recompressed)
check(f"recompressed + resized stays near ({d_re} ≤ {dg.IMAGE_NEAR_BITS})", d_re <= dg.IMAGE_NEAR_BITS)
d_other = dg.hamming(h_orig, h_other)
check(f"a different slip is far ({d_other} > {dg.IMAGE_NEAR_BITS})", d_other > dg.IMAGE_NEAR_BITS)
check("garbage bytes -> None, no crash", dg.image_dhash(b"not an image") is None)
check("hamming of missing hash is None", dg.hamming(None, h_orig) is None)

print("slip identity is verified against the printed text")
RAW = "SHOPRITE BRACKENFELL\nDate: 2026/10/11  Time 14:32\nTill 3  Trans 004512\nTOTAL 387.89"
check("printed time accepted", dg.verify_slip_time("14:32", RAW) == "14:32")
check("time with seconds normalised", dg.verify_slip_time("14:32:05", RAW + " 14:32:05") == "14:32")
check("invented time rejected", dg.verify_slip_time("15:10", RAW) is None)
check("not a time rejected", dg.verify_slip_time("387.89", RAW) is None)
check("printed transaction ref accepted", dg.verify_transaction_ref("004512", RAW) == "004512")
check("ref not on the slip rejected", dg.verify_transaction_ref("998877", RAW) is None)
check("ref without digits rejected", dg.verify_transaction_ref("ABCD", RAW + " ABCD") is None)

print("matching")
items3 = [{"total_price": 29.99}, {"total_price": 45.0}, {"total_price": 12.5}]
base = {"amount": 87.49, "shop_name": "SHOPRITE Brackenfell", "shop_id": None, "receipt_date": "2026-10-11",
        "slip_time": None, "transaction_ref": None, "image_hash": h_orig, "items": items3}
other_photo = {**base, "image_hash": h_other}
check("same photo -> same_image", dg.match_slip(base, dict(base)) == dg.SAME_IMAGE)
check("identical photo wins even when OCR read a different total",
      dg.match_slip({**base, "amount": 1503.0}, {**base, "amount": 1898.0}) == dg.SAME_IMAGE)
check("recompressed photo + same total -> same_image", dg.match_slip({**base, "image_hash": h_recompressed}, base) == dg.SAME_IMAGE)
check("re-encoded copy of the same photo is a copy whatever OCR read",
      dg.match_slip({**base, "image_hash": h_recompressed, "amount": 99.0, "items": []}, base) == dg.SAME_IMAGE)
check("a different photo with a different total -> not a match",
      dg.match_slip({**other_photo, "amount": 99.0, "items": []}, base) is None)
check("different photo, same 3 line prices + total -> same_content", dg.match_slip(other_photo, base) == dg.SAME_CONTENT)
check("OCR name variants don't matter ('Meerenda1')",
      dg.match_slip({**other_photo, "shop_name": "Bossa Meerenda1"}, {**base, "shop_name": "BOSSA Meerendal"}) == dg.SAME_CONTENT)
check("different shop -> not a match", dg.match_slip({**other_photo, "shop_name": "Pick n Pay"}, base) is None)
check("different printed dates -> not a match", dg.match_slip({**other_photo, "receipt_date": "2026-10-12"}, base) is None)
two = [{"total_price": 49.9}, {"total_price": 50.0}]
lunch = {**other_photo, "amount": 99.9, "items": two}
check("2 lines alone is too weak (two people buy the same combo)", dg.match_slip(lunch, {**base, "amount": 99.9, "items": two}) is None)
check("2 lines + same printed time -> same_content",
      dg.match_slip({**lunch, "slip_time": "12:05"}, {**base, "amount": 99.9, "items": two, "slip_time": "12:05"}) == dg.SAME_CONTENT)
check("same printed transaction ref -> same_transaction",
      dg.match_slip({**other_photo, "items": [], "transaction_ref": "004512"},
                    {**base, "items": [], "transaction_ref": "004512"}) == dg.SAME_TRANSACTION)
check("same time + same date + same total, no items -> same_content",
      dg.match_slip({**other_photo, "items": [], "slip_time": "14:32"}, {**base, "items": [], "slip_time": "14:32"}) == dg.SAME_CONTENT)
check("same time but undated -> not enough",
      dg.match_slip({**other_photo, "items": [], "slip_time": "14:32", "receipt_date": None},
                    {**base, "items": [], "slip_time": "14:32", "receipt_date": None}) is None)
check("qty x unit used when line total missing", dg.price_signature([{"quantity": 2, "unit_price": 10}]) == (2000,))

print("recent memory (slips not saved yet)")
dg._recent_images.clear(); dg._recent_slips.clear()
check("first sight of an image is new", dg.seen_image_recently("27001", h_orig) is False)
check("same customer, same image again -> seen", dg.seen_image_recently("27001", h_orig) is True)
check("another customer's first sight is new", dg.seen_image_recently("27002", h_orig) is False)
check("first slip is remembered, no match", dg.match_recent_slip("27001", {**base, "id": None}) is None)
m = dg.match_recent_slip("27002", other_photo)
check("racing copy from another customer is caught", m is not None and m["same_customer"] is False and m["pending"])
m2 = dg.match_recent_slip("27001", dict(base))
check("same customer's resend is flagged as same customer", m2 is not None and m2["same_customer"])

print("fraud-data summary")
signals = [
    {"customer_phone": "27002", "matched_phone": "27001", "same_customer": False, "created_at": "2026-10-11T10:00"},
    {"customer_phone": "27003", "matched_phone": "27002", "same_customer": False, "created_at": "2026-10-11T11:00"},
    {"customer_phone": "27009", "matched_phone": "27008", "same_customer": False, "created_at": "2026-10-11T12:00"},
    {"customer_phone": "27005", "matched_phone": "27005", "same_customer": True, "created_at": "2026-10-11T09:00"},
]
s = dg.summarize_signals(signals)
check("chain of sharing forms one cluster of 3", s["clusters"][0]["phones"] == ["27001", "27002", "27003"])
check("separate pair is its own cluster", len(s["clusters"]) == 2 and s["clusters"][1]["size"] == 2)
check("honest resends never link phones", all("27005" not in c["phones"] for c in s["clusters"]))
p5 = next(p for p in s["phones"] if p["phone"] == "27005")
check("resend counted on the phone", p5["resends"] == 1 and p5["cross_customer"] == 0)
check("empty input is safe", dg.summarize_signals([]) == {"clusters": [], "phones": [], "signals": 0})

print()
if failures:
    print(f"RESULT: {len(failures)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASS")
