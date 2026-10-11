"""
Unit tests for wallet_share (pure aggregation, no I/O).

    python tests/test_wallet_share.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wallet_share import compute_wallet_share, suppress_thin, round_coord, INDEPENDENT  # noqa: E402

SHOPS = [
    {"id": "s1", "name": "Checkers Douglasdale", "chain": "Shoprite Group"},
    {"id": "s2", "name": "Woolworths Fourways", "chain": "Woolworths"},
    {"id": "s3", "name": "Joe's Butchery", "chain": None},
]


def r(phone, shop_id, amount, suburb="Douglasdale", status="processed", lat=-26.04, lon=28.02):
    return {"customer_phone": phone, "shop_id": shop_id, "shop_name": None, "amount": amount, "status": status,
            "upload_suburb": suburb, "upload_locality": "Sandton", "upload_latitude": lat, "upload_longitude": lon}


failures = []


def check(name, cond):
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond:
        failures.append(name)


receipts = [
    r("27000000001", "s1", 300), r("27000000002", "s1", 100), r("+27000000003", "s2", 100),
    r("27000000004", "s3", 100), r("27000000005", "s1", 400),
    r("27000000001", "s2", 999, status="rejected"),                      # rejected: ignored
    r("27000000006", "s1", 50, suburb="Bryanston"),                     # thin suburb
    {"customer_phone": "27000000007", "shop_id": "s1", "amount": 10, "status": "processed",
     "upload_suburb": None, "upload_latitude": -26.1, "upload_longitude": 28.0},   # located, no suburb
    {"customer_phone": "27000000008", "shop_id": "s1", "amount": 10, "status": "processed",
     "upload_suburb": None, "upload_latitude": None, "upload_longitude": None},     # no location at all
]
res = compute_wallet_share(receipts, SHOPS, k_floor=5)
sub = {s["suburb"]: s for s in res["suburbs"]}

print("compute_wallet_share")
check("suburbs bucketed by customer suburb", set(sub) == {"Douglasdale", "Bryanston"})
d = sub["Douglasdale"]
check("rejected receipts excluded", d["spend"] == 1000 and d["receipts"] == 5)
check("customers counted once, '+' and bare phone equal", d["customers"] == 5)
check("leader is the biggest branch", d["leader"]["shop_id"] == "s1" and d["leader"]["share"] == 0.8)
check("shares sum to 1", abs(sum(x["share"] for x in d["split"]) - 1) < 1e-6)
check("chain roll-up; no chain -> Independent",
      {c["chain"]: c["spend"] for c in d["chains"]} == {"Shoprite Group": 800, "Woolworths": 100, INDEPENDENT: 100})
check("k-floor: 5 customers is not thin", d["thin"] is False)
check("k-floor: 1 customer is thin", sub["Bryanston"]["thin"] is True)
check("located but unassigned receipts counted", res["unassigned"] == 1)
check("suburbs sorted by spend", res["suburbs"][0]["suburb"] == "Douglasdale")

print("suppress_thin (the only externally exposable form)")
pub = suppress_thin(res)
check("thin suburbs dropped", [s["suburb"] for s in pub["suburbs"]] == ["Douglasdale"] and pub["suppressed"] == 1)
check("no per-branch customer counts", all("customers" not in x for x in pub["suburbs"][0]["split"]))
check("no coordinates", "latitude" not in pub["suburbs"][0] and "longitude" not in pub["suburbs"][0])
check("admin result left untouched", "customers" in res["suburbs"][0]["split"][0])

print("by home area (customer-chosen)")
homes = {"27000000001": {"suburb": "Soweto", "locality": "Soweto"},
         "27000000002": {"suburb": "Soweto", "locality": "Soweto"},
         "27000000003": {"suburb": "Khayelitsha", "locality": "Cape Town"}}
hres = compute_wallet_share(receipts, SHOPS, k_floor=2, by="home", homes=homes)
hsub = {s["suburb"]: s for s in hres["suburbs"]}
check("grouped by home area, not upload suburb", set(hsub) == {"Soweto", "Khayelitsha"})
check("'+' phone matches its bare home entry", hsub["Khayelitsha"]["spend"] == 100)
check("receipts of customers without an area are unassigned", hres["unassigned"] == 5)
check("no coordinates in home mode (upload points aren't homes)", hsub["Soweto"]["latitude"] is None)
check("k-floor applies per home area", hsub["Soweto"]["thin"] is False and hsub["Khayelitsha"]["thin"] is True)
check("result says which grouping", hres["by"] == "home" and res["by"] == "upload")

print("round_coord")
check("3 decimal places (~110 m)", round_coord(-26.123456, 28.987654) == (-26.123, 28.988))
check("missing coordinate -> None", round_coord(None, 28.0) is None)

print("\nRESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
