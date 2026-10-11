"""
Unit tests for trip_category (the Activity Map's one-label-per-receipt rule).
Cases are the real mislabels found in the Oct 2026 map audit.

    python tests/test_trip_category.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trip_category import trip_category, is_food_service, DINING, OTHER  # noqa: E402

failures = []


def check(name, cond):
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond:
        failures.append(name)


def i(cat, total, qty=1, unit=None):
    return {"category": cat, "total_price": total, "quantity": qty, "unit_price": unit}


print("food service")
check("KFC + Sprite is a takeaway trip, not Beverages",
      trip_category([i("Beverages", 0), i("Other", 100.4)], 100.4, "KFC GREENACRES") == DINING)
check("Debonairs chicken is takeaway, not Meat",
      trip_category([i("Meat & Poultry", 0), i("Other", 109.9)], 109.9, "Debonairs Pizza") == DINING)
check("Chicken Licken loaf is takeaway, not Bread",
      trip_category([i("Bread & Bakery", 90), i("Other", 441)], 531, "Chicken Licken") == DINING)
check("'Golf Estate Rest' steak is dining", trip_category([i("Meat & Poultry", 0)], 912, "Copper Leaf Golf Estate Rest") == DINING)
check("any Dining line marks a restaurant", trip_category([i("Dining & Takeaways", 50), i("Meat & Poultry", 490)], 2349, "Ginja") == DINING)
check("frozen burger patties don't make Pick n Pay a takeaway",
      trip_category([i("Dining & Takeaways", 56), i("Meat & Poultry", 38), i("Fresh Produce", 64), i("Other", 300)], 481, "PICK N PAY") != DINING)
check("a sushi lunch at Checkers still wins by value",
      trip_category([i("Dining & Takeaways", 105), i("Beverages", 14)], 119, "Checkers") == DINING)
check("café with no name clue, coffee on the slip", trip_category([i("Dining & Takeaways", 100)], 189, "MCC HOBART") == DINING)
check("Pick n Pay is not food service", not is_food_service("Pick n Pay Rosebank", ["Staples & Grocery"]))
check("'Forest Hill Spar' — 'rest' needs a whole word", not is_food_service("Forest Hill SPAR"))

print("coverage floor")
check("R40 'orange' colour line can't label a R838 clothing slip",
      trip_category([i("Fresh Produce", 40), i("Other", 798)], 838, "FACTORIE") == OTHER)
check("R30 jam can't label a R238 grocery shop", trip_category([i("Staples & Grocery", 29.99), i("Other", 208)], 238.31, "Pick n Pay") == OTHER)
check("dominant category over 25% wins", trip_category([i("Meat & Poultry", 300), i("Other", 100)], 400, "Joe's Butchery") == "Meat & Poultry")
check("non-product lines don't count", trip_category([i("Non-product", 500), i("Dairy & Eggs", 60)], 80, "Corner Shop") == "Dairy & Eggs")
check("OCR misread uses qty x unit", trip_category([i("Beverages", 295, 3, 40), i("Snacks & Sweets", 200)], 320, "Shop") == "Snacks & Sweets")
check("nothing categorised -> Other", trip_category([i("Other", 50)], 50, "Shop") == OTHER)
check("no items -> Other", trip_category([], 0, None) == OTHER)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASS")
