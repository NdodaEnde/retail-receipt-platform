"""
Unit tests for category_drilldown (pure aggregation) and the sub-category rules.

    python tests/test_category_drilldown.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from category_drilldown import (  # noqa: E402
    compute_category_drilldown, line_spend, pack_label, NO_BRAND, NO_SUBURB, INDEPENDENT,
)
from item_normalizer import categorize, subcategorize, UNSPLIT  # noqa: E402

failures = []


def check(name, cond):
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond:
        failures.append(name)


print("sub-categories")
check("still water -> Water", subcategorize("Beverages", "Min Still Lrg 1lt") == "Water")
check("soda water -> Soft drinks & mixers", subcategorize("Beverages", "Soda Water") == "Soft drinks & mixers")
check("Coke Zero -> Soft drinks", subcategorize("Beverages", "Coke Zero") == "Soft drinks & mixers")
check("teabags -> Tea", subcategorize("Beverages", "RITEBRAND TEABAGS 100S") == "Tea")
check("iced tea is not Tea", subcategorize("Beverages", "Lipton Iced Tea Peach") == "Iced tea")
check("misspelt cappucino -> Coffee", subcategorize("Beverages", "Coffee Cappucino / Bar") == "Coffee")
check("Brookes Oros -> Juice & cordial", subcategorize("Beverages", "Brookes Oros") == "Juice & cordial")
check("unmatched beverage stays unsplit", subcategorize("Beverages", "Mystery 440ml") == UNSPLIT)
check("category without rules is unsplit", subcategorize("Fresh Produce", "Bananas") == UNSPLIT)
check("amasi before milk", subcategorize("Dairy & Eggs", "Clover Amasi 2L") == "Amasi")

print("category fixes")
check("chewing gum is a sweet, not water", categorize("Water Air Rush Chewing Gum Menthol") == "Snacks & Sweets")
check("spirit & mixer is Alcohol", categorize("Double Buffels & coke") == "Alcohol")
check("plain Coke still Beverages", categorize("Coke 440ml") == "Beverages")
check("mixer pattern -> Spirits", subcategorize("Alcohol", "Double Buffels & coke") == "Spirits & mixed drinks")

print("line spend")
check("consistent line uses total", line_spend({"quantity": 3, "unit_price": 40, "total_price": 120}) == (120, False))
check("OCR misread takes the smaller, flagged", line_spend({"quantity": 3, "unit_price": 40, "total_price": 295}) == (120, True))
check("rounding is not a conflict", line_spend({"quantity": 3, "unit_price": 33.33, "total_price": 100}) == (100, False))
check("no unit price -> total", line_spend({"quantity": 2, "unit_price": None, "total_price": 50}) == (50, False))
check("pack 1500 ml -> 1.5 L", pack_label(1500, "ml") == "1.5 L")
check("single each -> no pack", pack_label(1, "each") is None)

print("drill-down")
SHOPS = [{"id": "s1", "name": "Checkers Rosebank", "chain": "Shoprite Group"},
         {"id": "s2", "name": "Corner Cafe", "chain": None}]
RECEIPTS = [
    {"id": f"r{i}", "status": "processed", "customer_phone": f"2700000000{i}", "shop_id": "s1",
     "upload_suburb": "Rosebank"} for i in range(1, 6)
] + [
    {"id": "r6", "status": "processed", "customer_phone": "+27000000006", "shop_id": "s2", "upload_suburb": None},
    {"id": "r7", "status": "rejected", "customer_phone": "27000000007", "shop_id": "s1", "upload_suburb": "Rosebank"},
]


def item(rid, name, total, brand=None, qty=1, unit=None, pack=None, cat="Beverages", tk=None):
    return {"receipt_id": rid, "name": name, "canonical_name": name, "category": cat, "brand": brand,
            "brand_type": "national" if brand else None, "quantity": qty, "unit_price": unit,
            "total_price": total, "pack_size": pack[0] if pack else None,
            "pack_unit": pack[1] if pack else None, "type_key": tk or name.lower()}


ITEMS = [item(f"r{i}", "Coke 2L", 30, brand="Coke", pack=(2000, "ml"), tk="2l") for i in range(1, 6)] + [
    item("r6", "Coke Zero", 295, brand="Coke", qty=3, unit=40, tk="zero"),   # misread -> 120
    item("r1", "Still Water", 10),
    item("r7", "Coke 2L", 999, brand="Coke"),                                  # rejected receipt
    item("r1", "Bread", 15, cat="Bread & Bakery"),                             # other category
]
d = compute_category_drilldown("Beverages", ITEMS, RECEIPTS, SHOPS)
check("rejected receipts and other categories excluded", d["lines"] == 7)
check("spend uses corrected misread", d["spend"] == 280.0)
check("conflict counted", d["coverage"]["price_conflicts"] == 1)
check("brand coverage 6/7", d["coverage"]["brand"] == round(6 / 7, 3))
check("customers deduped across +/bare", d["customers"] == 6)
subs = {s["name"]: s for s in d["subcategories"]}
check("two sub-categories", set(subs) == {"Soft drinks & mixers", "Water"})
soft = subs["Soft drinks & mixers"]
check("sorted by spend", d["subcategories"][0]["name"] == "Soft drinks & mixers")
check("share within parent", soft["share"] == round(270 / 280, 4))
check("5+ shoppers is not thin", soft["thin"] is False)
check("1 shopper is thin", subs["Water"]["thin"] is True)
coke = soft["brands"][0]
check("brand level", coke["name"] == "Coke" and coke["brand_type"] == "national")
prods = {p["name"]: p for p in coke["products"]}
check("products split by type + pack", set(prods) == {"Coke 2L", "Coke Zero"})
check("pack label on product", prods["Coke 2L"]["pack"] == "2 L" and prods["Coke 2L"]["units"] == 5)
check("avg unit price from corrected spend", prods["Coke Zero"]["avg_unit_price"] == 40.0)
check("unbranded bucket kept", subs["Water"]["brands"][0]["name"] == NO_BRAND)
chains = {c["chain"]: c for c in d["chains"]}
check("independent bucket", INDEPENDENT in chains and chains["Shoprite Group"]["spend"] == 160.0)
check("unknown suburb bucket", NO_SUBURB in {s["suburb"] for s in d["suburbs"]})
check("no internal keys leak", all("_lines" not in s for s in d["subcategories"]))
check("empty category is safe", compute_category_drilldown("Alcohol", ITEMS, RECEIPTS, SHOPS)["lines"] == 0)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASS")
