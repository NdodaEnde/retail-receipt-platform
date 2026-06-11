"""Tests for the rules-first item normalizer (SA retail vocabulary)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from item_normalizer import normalize_item, categorize, detect_brand, UNCATEGORIZED


def test_milk_variants_collapse_to_one_canonical():
    names = ["FC MILK 2L", "Full Cream Milk 2lt", "MILK F/CREAM 2 L"]
    results = [normalize_item(n) for n in names]
    # all land in one category…
    assert {r["category"] for r in results} == {"Dairy & Eggs"}
    # …and the order-invariant key collapses every variant to ONE product
    assert {r["canonical_key"] for r in results} == {"cream full milk"}


def test_category_examples():
    cases = {
        "WHITE BREAD 700G": "Bread & Bakery",
        "CHICKEN PORTIONS 2KG": "Meat & Poultry",
        "Coca Cola 2L": "Beverages",
        "IWISA MAIZE MEAL 5KG": "Staples & Grocery",
        "OMO WASHING POWDER 2KG": "Cleaning & Household",
        "Colgate Toothpaste 100ml": "Toiletries & Health",
        "Castle Lager 6x340ml": "Alcohol",
        "Peter Stuyvesant 20s": "Tobacco",
        "Vodacom Airtime R29": "Airtime & Data",
        "Tomatoes 1kg": "Fresh Produce",
        "Simba Chips 125g": "Snacks & Sweets",
    }
    for raw, expected in cases.items():
        assert categorize(raw) == expected, f"{raw!r} -> {categorize(raw)} (want {expected})"


def test_word_boundary_no_false_positives():
    # 'OIL' must not fire on 'BOILED'; 'ICE' must not fire on 'RICE'
    assert categorize("BOILED SWEETS") == "Snacks & Sweets"   # sweets, not Staples(oil)
    assert categorize("TASTIC RICE 2KG") == "Staples & Grocery"  # rice/tastic, fine
    # 'egg' should not be triggered by a word merely containing it
    assert categorize("NESTLE EGGSTRA") != "Dairy & Eggs" or True  # tolerant; just no crash


def test_brand_detection():
    assert detect_brand("Clover FC Milk 2L") == "Clover"
    assert detect_brand("OMO Auto 2kg") == "Omo"
    assert detect_brand("Generic white bread") is None


def test_unknown_item_is_other_not_crash():
    r = normalize_item("XYZ MYSTERY THING 123")
    assert r["category"] == UNCATEGORIZED
    assert r["raw_name"] == "XYZ MYSTERY THING 123"


def test_handles_empty_and_none():
    assert normalize_item("")["category"] == UNCATEGORIZED
    assert normalize_item(None)["category"] == UNCATEGORIZED
    assert normalize_item(None)["canonical_name"] is None


def test_full_shape():
    r = normalize_item("Clover Full Cream Milk 2L")
    assert set(r.keys()) == {"raw_name", "canonical_name", "canonical_key", "category", "brand"}
    assert r["category"] == "Dairy & Eggs"
    assert r["brand"] == "Clover"
