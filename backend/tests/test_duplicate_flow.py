"""
End-to-end test of the WhatsApp receipt flow with the duplicate guard: drives the real
process_receipt_from_whatsapp -> finalise_receipt_with_location, faking only the outside
world (WhatsApp, OCR, geocoding, storage, database). Duplicate lookups use the real
matching rules against the receipts this test has "saved".

    python tests/test_duplicate_flow.py
"""
import asyncio
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_KEY", "test")

from PIL import Image, ImageDraw  # noqa: E402
import server  # noqa: E402
import duplicate_guard as dg  # noqa: E402

failures = []


def check(name, cond):
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond:
        failures.append(name)


def photo(seed, bg=(35, 30, 30), shift=0):
    img = Image.new("RGB", (400, 700), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([100 + shift, 30, 300 + shift, 670], fill=(245, 245, 240))
    for i, y in enumerate(range(50, 650, 20)):
        d.rectangle([115 + shift, y, 115 + shift + (37 * (i + seed) * 7) % 150 + 20, y + 8], fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


SLIP_A, SLIP_B = photo(1), photo(9)
SLIP_A_RETAKE = photo(1, bg=(150, 120, 90), shift=60)  # same slip, re-photographed on another table
OCR = {  # what "LandingAI" reads from each photo
    SLIP_A: {"amount": 87.49, "items": [{"name": "Bread", "total_price": 29.99}, {"name": "Milk", "total_price": 45.0},
                                        {"name": "Eggs", "total_price": 12.5}]},
    SLIP_A_RETAKE: {"amount": 87.49, "items": [{"name": "Brcad", "total_price": 29.99}, {"name": "Milk", "total_price": 45.0},
                                               {"name": "Egg5", "total_price": 12.5}]},
    SLIP_B: {"amount": 212.0, "items": [{"name": "Chicken", "total_price": 112.0}, {"name": "Rice", "total_price": 100.0}]},
}


class FakeWA:
    def __init__(self):
        self.sent, self.media = [], {}

    async def download_media(self, media_id):
        return self.media[media_id]

    async def send_text_message(self, to, message):
        self.sent.append((to, "text", message))

    async def send_location_request(self, to, message):
        self.sent.append((to, "location", message))

    async def send_receipt_confirmation(self, to, shop_name, amount, items_count, fraud_flag, portal_url=None,
                                        not_in_draw_reason=None):
        self.sent.append((to, "confirmation", not_in_draw_reason or fraud_flag))


class FakeProcessor:
    def process_receipt_image(self, image_base64, mime_type):
        import base64
        o = OCR[base64.b64decode(image_base64)]
        self_calls.append(1)
        return {"success": True, "shop_name": "SHOPRITE Brackenfell", "shop_address": None, "amount": o["amount"],
                "items": o["items"], "date": "2026-10-11", "raw_text": "", "grounding": {}}


class FakeDB:
    def __init__(self):
        self.receipts = []

    async def receipts_insert_one(self, doc):
        doc.pop("items", None)
        self.receipts.append(doc)

    async def shops_update_one(self, *a, **k):
        pass

    async def customers_update_one(self, *a, **k):
        pass


self_calls, signals = [], []
wa, fdb, pending, locations = FakeWA(), FakeDB(), {}, {}


def fake_find_duplicate(db, phone, slip):
    for r in fdb.receipts:
        kind = dg.match_slip(slip, {**r, "items": r["_items"]})
        if kind:
            return {"receipt_id": r["id"], "customer_phone": r["customer_phone"], "kind": kind,
                    "same_customer": r["customer_phone"] == phone, "created_at": r["created_at"]}
    return None


def fake_find_resend(db, phone, image_hash):
    for r in fdb.receipts:
        d = dg.hamming(r.get("image_hash"), image_hash)
        if r["customer_phone"] == phone and d is not None and d <= dg.RESEND_BITS:
            return r
    return None


async def fake_insert(doc):
    doc["_items"] = doc.get("items") or []
    await FakeDB.receipts_insert_one(fdb, doc)


async def noop(*a, **k):
    return None


async def cache_set(phone, data):
    pending[phone] = data


async def cache_get(phone):
    return pending.get(phone)


async def cache_pop(phone):
    return pending.pop(phone, None)


async def loc_pop(phone):
    return locations.pop(phone, None)


async def geocode(*a, **k):
    return None, None, "Shoprite Brackenfell", None, None, None


async def shop(*a, **k):
    return {"id": "shop-1"}


async def area(*a, **k):
    return {}


class FakeStorage:
    def upload_image(self, rid, b64):
        return None, None


server.get_whatsapp_client = lambda: wa
server.get_receipt_processor = lambda: FakeProcessor()
server.db = fdb
fdb.receipts_insert_one = fake_insert
server.cache_set_pending_receipt, server.cache_get_pending_receipt = cache_set, cache_get
server.cache_pop_pending_receipt, server.cache_pop_customer_location = cache_pop, loc_pop
server.geocode_shop_from_receipt, server.get_or_create_shop = geocode, shop
server.upload_area_fields, server.maybe_ask_home_area = area, noop
server.get_storage = lambda: FakeStorage()
server.get_portal_url = lambda phone: None
server.check_draw_eligibility = lambda d: True
dg.find_duplicate, dg.find_resend = fake_find_duplicate, fake_find_resend
dg.log_signal = lambda db, kind, phone, match, **k: signals.append({"signal": kind, "phone": phone, "match": match, **k})

CUSTOMER = {"id": "c1"}


async def send(phone, image, media_id):
    wa.media[media_id] = image
    await server.process_receipt_from_whatsapp(phone, media_id, "image/jpeg", CUSTOMER)


async def share_location(phone):
    p = await cache_pop(phone)
    if p:
        await server.finalise_receipt_with_location(phone, p, -33.87, 18.63, CUSTOMER)


def last(phone):
    return [m for m in wa.sent if m[0] == phone][-1]


async def main():
    ALICE, BOB, CAROL = "27000000001", "27000000002", "27000000003"

    print("first slip")
    await send(ALICE, SLIP_A, "m1")
    check("asked for location", last(ALICE)[1] == "location")
    await share_location(ALICE)
    check("entered in the draw", last(ALICE) == (ALICE, "confirmation", "valid"))
    check("saved once, eligible, fingerprinted", len(fdb.receipts) == 1 and fdb.receipts[0]["draw_eligible"]
          and fdb.receipts[0].get("image_hash"))

    print("same customer re-sends the same photo")
    ocr_before = len(self_calls)
    await send(ALICE, SLIP_A, "m2")
    check("told 'we already have this slip'", "already have this slip" in last(ALICE)[2])
    check("no OCR call spent", len(self_calls) == ocr_before)
    check("nothing saved", len(fdb.receipts) == 1)
    check("logged as a resend", signals[-1]["signal"] == "resend" and signals[-1]["match"]["same_customer"])

    print("same customer, a new photo of the same slip")
    await send(ALICE, SLIP_A_RETAKE, "m3")
    d = dg.hamming(dg.image_dhash(SLIP_A), dg.image_dhash(SLIP_A_RETAKE))
    check(f"(the re-take is a visually different photo: {d} bits apart)", d > dg.IMAGE_NEAR_BITS)
    check("recognised by content, still friendly", "already have this slip" in last(ALICE)[2])
    check("nothing saved", len(fdb.receipts) == 1)

    print("double-send before the location step")
    await send(ALICE, SLIP_B, "m4")
    await send(ALICE, SLIP_B, "m5")
    check("second copy: 'tap the location button'", "location button" in last(ALICE)[2])
    await share_location(ALICE)
    check("slip B saved once", len(fdb.receipts) == 2)

    print("another customer sends Alice's slip")
    await send(BOB, SLIP_A_RETAKE, "m6")
    check("Bob is asked for location as normal (no tip-off)", last(BOB)[1] == "location")
    await share_location(BOB)
    bob = fdb.receipts[-1]
    check("saved for the evidence", len(fdb.receipts) == 3 and bob["customer_phone"] == BOB)
    check("not in the draw", bob["draw_eligible"] is False)
    check("sent to review", bob["fraud_flag"] == "review" and bob["status"] == "review")
    check("points at Alice's original", bob["duplicate_of"] == fdb.receipts[0]["id"] and bob["duplicate_kind"] == dg.SAME_CONTENT)
    check("told neutrally it's already entered", last(BOB) == (BOB, "confirmation", "duplicate"))
    sig = signals[-1]
    check("fraud signal: both phones, Bob's location, his receipt",
          sig["signal"] == "cross_customer_duplicate" and sig["match"]["customer_phone"] == ALICE and sig["phone"] == BOB
          and sig["latitude"] == -33.87 and sig["receipt_id"] == bob["id"])

    print("two customers racing with the same new slip")
    dg._recent_slips.clear()
    slip_c = photo(13)
    OCR[slip_c] = {"amount": 55.5, "items": [{"total_price": 20.0}, {"total_price": 25.5}, {"total_price": 10.0}]}
    await send(CAROL, slip_c, "m7")
    await send(BOB, slip_c, "m8")  # neither has shared location yet
    await share_location(CAROL)
    await share_location(BOB)
    carol, bob2 = fdb.receipts[-2], fdb.receipts[-1]
    check("first sender entered", carol["customer_phone"] == CAROL and carol["draw_eligible"])
    check("racing copy kept out of the draw", bob2["customer_phone"] == BOB and bob2["draw_eligible"] is False)

    print("message to the customer")
    from whatsapp_cloud import WhatsAppCloudAPI
    captured = []

    async def capture(self, to, message):
        captured.append(message)
    WhatsAppCloudAPI.send_text_message = capture
    await WhatsAppCloudAPI.__new__(WhatsAppCloudAPI).send_receipt_confirmation(
        BOB, "Shoprite", 87.49, 3, "review", not_in_draw_reason="duplicate")
    msg = captured[-1]
    check("says it's already entered", "already been entered" in msg)
    check("never accuses or names anyone", not any(w in msg.lower() for w in ("fraud", "another customer", "someone")))


asyncio.run(main())
print()
if failures:
    print(f"RESULT: {len(failures)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASS")
