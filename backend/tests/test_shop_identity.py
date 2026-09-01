"""Identity rules of get_or_create_shop with an in-memory fake DB (no network)."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
import server  # noqa: E402


class FakeDB:
    def __init__(self):
        self.shops, self.aliases = [], []

    async def shops_find_one(self, f):
        for s in self.shops:
            if "place_id" in f and s.get("place_id") == f["place_id"]:
                return dict(s)
            if "name" in f and isinstance(f["name"], dict):
                pat = f["name"]["$regex"].strip("^$").replace("\\", "")
                if s["name"].lower() == pat.lower():
                    return dict(s)
        return None

    async def shops_find_by_name(self, name):
        return [dict(s) for s in self.shops if s["name"].lower() == name.lower()]

    async def shops_update_one(self, f, u):
        for s in self.shops:
            if s["id"] == f["id"]:
                s.update(u["$set"])

    async def shops_insert_one(self, d):
        d = dict(d); d["id"] = f"shop{len(self.shops) + 1}"; self.shops.append(d); return d

    async def shop_alias_add(self, sid, alias):
        self.aliases.append((sid, alias)); return True


FAILS = []
def check(c, m):
    print(("  ✅ " if c else "  ❌ ") + m)
    if not c: FAILS.append(m)


async def run():
    db = FakeDB(); server.db = db
    g = server.get_or_create_shop
    # 1. new branch with a place id -> canonical name, alias recorded
    a = await g("PICK N PAY", "Cnr Douglas Dr", -26.0385, 27.9935, "verified", place_id="P1", display_name="Pick n Pay Douglasdale", phone="+27118998634")
    check(a["name"] == "Pick n Pay Douglasdale" and a["place_id"] == "P1" and a["phone"] == "+27118998634", "new branch created with canonical name")
    check(("shop1", "PICK N PAY") in db.aliases, "OCR name recorded as alias")
    # 2. same place id, different OCR name -> same shop
    b = await g("Pick n Pay", None, -26.0386, 27.9936, "rooftop", place_id="P1", display_name="Pick n Pay Douglasdale")
    check(b["id"] == a["id"] and len(db.shops) == 1, "same place_id -> same shop")
    # 3. same OCR name, different branch (different place id, 1 400 km away) -> new shop
    c = await g("PICK N PAY", None, -33.9, 18.4, "verified", place_id="P2", display_name="Pick n Pay V&A Waterfront")
    check(c["id"] != a["id"] and len(db.shops) == 2, "same name, other place_id -> different shop")
    # 4. legacy name-only shop is claimed by the first resolved receipt at the same place
    db.shops.append({"id": "legacy", "name": "WOOLWORTHS", "latitude": None, "longitude": None, "place_id": None, "address": None})
    d = await g("WOOLWORTHS", "Cnr Leslie", -26.04, 27.99, "verified", place_id="P3", display_name="Woolworths Douglasdale")
    check(d["id"] == "legacy" and d["place_id"] == "P3" and d["name"] == "Woolworths Douglasdale", "legacy shop claimed and renamed")
    # 5. legacy shop far away is NOT claimed
    db.shops.append({"id": "legacy2", "name": "SHOPRITE", "latitude": -33.9, "longitude": 18.6, "place_id": None, "address": None, "geocode_confidence": "rooftop"})
    e = await g("SHOPRITE", None, -26.2, 28.05, "verified", place_id="P4", display_name="Shoprite Hillbrow")
    check(e["id"] != "legacy2", "far-away legacy shop not claimed -> new branch")
    # 6. no place id: name match only counts at the same place
    f = await g("SHOPRITE", None, -33.9, 18.6, "suburb")
    check(f["id"] == "legacy2", "no place_id, same place -> existing shop")
    h = await g("SHOPRITE", None, -29.85, 31.0, "suburb")
    check(h["id"] not in ("legacy2", e["id"]), "no place_id, far away -> new shop")
    # 7. a verified result upgrades a suburb-level stored location, not the reverse
    before = dict(db.shops[[s["id"] for s in db.shops].index(h["id"])])
    await g("SHOPRITE", None, -29.851, 31.001, "verified", place_id="P5", display_name="Shoprite Durban")
    after = next(s for s in db.shops if s["id"] == h["id"])
    check(after.get("place_id") == "P5" and after["geocode_confidence"] == "verified", "verified claim upgrades suburb-level shop")
    await g("Shoprite Durban", None, -29.86, 31.01, "biased", place_id="P5")
    after2 = next(s for s in db.shops if s["id"] == h["id"])
    check(after2["latitude"] == -29.851, "biased result does not overwrite verified coords")
    # 8. never store the country centroid
    i = await g("Mystery", None, -30.559482, 22.937506, "rooftop")
    check(i.get("latitude") is None, "centroid never stored")


asyncio.run(run())
print("RESULT:", "ALL PASS" if not FAILS else f"{len(FAILS)} FAILED")
sys.exit(1 if FAILS else 0)
