"""
Item Normalizer — rules-first canonicalization of OCR receipt line items.

Resolves the "item-normalization bottleneck": raw OCR names like
"FC MILK 2L", "Full Cream Milk 2lt", "MILK F/CREAM 2 L" all map to a single
canonical product + category, so product/category analytics become possible.

Per the data-intelligence strategy: SIMPLE RULES BEFORE ML. This is a
deterministic, extensible, fully-testable rule engine — no model, no API call,
no per-item cost. Categories use South African retail vocabulary.

Public API:
    normalize_item(raw_name) -> {raw_name, canonical_name, category, brand}
    categorize(name) -> category
    detect_brand(name) -> brand | None
"""
from __future__ import annotations
import re
from typing import Optional, Tuple

from brand_registry import detect_house_brand, OWN_BRAND_CHAINS

UNCATEGORIZED = "Other"

# ── Abbreviation expansion (whole-word) ──────────────────────────────────────
ABBREVIATIONS = {
    "FC": "FULL CREAM", "F/CREAM": "FULL CREAM", "FCREAM": "FULL CREAM",
    "L/FAT": "LOW FAT", "LF": "LOW FAT",
    "MLK": "MILK", "BRN": "BROWN", "WHT": "WHITE", "WH": "WHITE",
    "CHKN": "CHICKEN", "CHK": "CHICKEN", "BF": "BEEF",
    "VEG": "VEGETABLE", "TOM": "TOMATO", "POT": "POTATO",
    "CLDRNK": "COLD DRINK", "CDRINK": "COLD DRINK", "CD": "COLD DRINK",
    "S/LIGHT": "SUNLIGHT", "W/POWDER": "WASHING POWDER",
    "T/PAPER": "TOILET PAPER", "T/PASTE": "TOOTHPASTE",
    "M/MEAL": "MAIZE MEAL", "MMEAL": "MAIZE MEAL",
}

# ── Category rules: ordered (first category with a keyword hit wins) ──────────
# Keywords are matched as whole words / phrases (word boundaries), so "ICE"
# does not match "RICE" and "OIL" does not match "BOILED".
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Alcohol", [
        "beer", "lager", "black label", "castle", "hansa", "carling", "amstel",
        "heineken", "wine", "brandy", "vodka", "whisky", "whiskey", "cider",
        "savanna", "hunters", "klipdrift", "viceroy", "spirits", "gin", "rum",
    ]),
    ("Tobacco", [
        "cigarette", "cigarettes", "stuyvesant", "remington", "dunhill",
        "courtleigh", "tobacco", "cigs",
    ]),
    ("Airtime & Data", [
        "airtime", "data", "voucher", "recharge", "vodacom", "mtn", "cell c",
        "telkom", "blu voucher",
    ]),
    ("Dining & Takeaways", [
        # unambiguous prepared-food / cafe terms (this platform ingests restaurant
        # receipts). Generic 'coffee'/'tea'/'grilled'/'steak' are intentionally
        # excluded here so grocery items aren't miscategorised.
        "cappuccino", "espresso", "americano", "latte", "macchiato", "mocha",
        "flat white", "milkshake", "smoothie", "tagliata", "calamari", "squid",
        "sushi", "sashimi", "pizza", "burger", "risotto", "schnitzel", "nachos",
        "tapas", "padano", "broccolini", "tramezzini", "sirloin", "ribeye",
    ]),
    ("Meat & Poultry", [
        "chicken", "beef", "mince", "polony", "vienna", "viennas", "russian",
        "russians", "wors", "boerewors", "sausage", "steak", "chop", "chops",
        "pork", "lamb", "mutton", "fish", "hake", "ribs", "liver", "gizzard",
        "drumstick", "drumsticks", "braai pack", "biltong",
    ]),
    ("Dairy & Eggs", [
        "milk", "amasi", "maas", "cheese", "butter", "yoghurt", "yogurt",
        "egg", "eggs", "cream", "margarine", "rama", "stork", "custard",
    ]),
    ("Bread & Bakery", [
        "bread", "roll", "rolls", "bun", "buns", "loaf", "cake", "muffin",
        "scone", "bakery", "rusks",
    ]),
    ("Fresh Produce", [
        "tomato", "tomatoes", "onion", "onions", "potato", "potatoes", "apple",
        "apples", "banana", "bananas", "orange", "oranges", "spinach", "cabbage",
        "carrot", "carrots", "lettuce", "avo", "avocado", "butternut", "lemon",
        "naartjie", "fruit", "vegetable", "vegetables",
    ]),
    ("Beverages", [
        "juice", "cold drink", "cooldrink", "coke", "coca cola", "fanta",
        "sprite", "stoney", "soda", "water", "tea", "teabags", "tea bags",
        "coffee", "rooibos", "energy drink", "oros", "cordial", "mageu",
        "maheu", "iced tea", "still water", "still", "sparkling", "mineral",
    ]),
    ("Snacks & Sweets", [
        "chips", "crisps", "nik naks", "niknaks", "simba", "lays", "doritos",
        "sweets", "chocolate", "choc", "biscuit", "biscuits", "cookies",
        "chappies", "gum", "lollipop", "popcorn",
    ]),
    ("Cleaning & Household", [
        "soap", "washing powder", "dishwash", "omo", "sunlight", "surf",
        "handy andy", "toilet", "bleach", "jik", "detergent", "fabric softener",
        "air freshener", "domestos", "scourer", "candle", "candles", "matches",
        "foil", "cleaner",
    ]),
    ("Toiletries & Health", [
        "toothpaste", "toothbrush", "colgate", "shampoo", "roll on", "roll-on",
        "deodorant", "lotion", "vaseline", "sanitary", "pads", "always",
        "diaper", "nappies", "huggies", "pampers", "tissue", "toilet paper",
        "twinsaver", "lifebuoy", "dettol", "plaster", "panado", "grandpa",
    ]),
    ("Staples & Grocery", [
        "maize meal", "mealie meal", "mealie", "iwisa", "white star", "ace",
        "rice", "tastic", "samp", "flour", "sugar", "salt", "oil", "cooking oil",
        "pasta", "macaroni", "spaghetti", "beans", "baked beans", "soup",
        "sauce", "tomato sauce", "spice", "stock", "koo", "all gold",
        "lucky star", "knorr", "maggi", "rajah", "aromat", "oats", "instant oats",
        "cereal", "weetbix", "pronutro", "mealiemeal", "vinegar", "jam",
    ]),
]

# ── Non-product rows: subtotals, department headers, VAT/rounding lines, bags,
#    and LandingAI OCR-description fragments. These are NOT products and must be
#    EXCLUDED from category analytics, not lumped into 'Other'.
NON_ITEM_EXACT = {
    "groceries", "household", "personal care", "general merchandise",
    "perishables", "non perishables", "departments", "department",
    "subtotal", "sub total", "total", "balance", "balance due", "change",
    "tender", "tendered", "rounding", "round off", "vat", "tax", "cash",
    "card", "discount", "savings",
}
NON_ITEM_PATTERNS = [
    re.compile(r"\((?:part|partial|text|visible|word|background|dark|blurred|cut)", re.IGNORECASE),
    re.compile(r"^\s*\d+([.,]\d+)?\s*%\s*$"),                       # "15.0%"
    re.compile(r"\b(carrier|checkout|plastic|shopping)\s+bag\b", re.IGNORECASE),
    re.compile(r"\b(100%|\d+\s*lt?r?)\s+bag\b", re.IGNORECASE),  # "CLICKS 100% 12LT BAG" = carrier bag
    re.compile(r"\bbag\s+(levy|fee)\b", re.IGNORECASE),
    re.compile(r"\b(rounding|round\s*off)\b", re.IGNORECASE),
    re.compile(r"^\s*[-=*.]+\s*$"),                                  # separator rows
]


def is_non_item(raw_name: str) -> bool:
    """True if the row is a subtotal/header/VAT/bag/OCR-fragment, not a product."""
    if not raw_name or not raw_name.strip():
        return True
    low = re.sub(r"\s+", " ", raw_name.strip().lower())
    if low in NON_ITEM_EXACT:
        return True
    return any(p.search(raw_name) for p in NON_ITEM_PATTERNS)

# ── Brand detection (whole-word) ─────────────────────────────────────────────
BRANDS = [
    "Clover", "Parmalat", "Sasko", "Albany", "Blue Ribbon", "White Star",
    "Iwisa", "Ace", "Tastic", "Coca Cola", "Coke", "Fanta", "Sprite", "Stoney",
    "Oros", "Simba", "Lays", "Doritos", "Nestle", "Bakers", "Five Roses",
    "Joko", "Ricoffy", "Nescafe", "Jacobs", "Omo", "Sunlight", "Surf",
    "Handy Andy", "Jik", "Domestos", "Colgate", "Aquafresh", "Vaseline",
    "Lifebuoy", "Dettol", "Panado", "Grandpa", "Stuyvesant", "Black Label",
    "Castle", "Hansa", "Savanna", "Hunters", "Heineken", "Amstel", "Klipdrift",
    "Vodacom", "MTN", "Cell C", "Telkom", "Huletts", "Selati", "Maggi", "Knorr",
    "Rajah", "Aromat", "Koo", "All Gold", "Lucky Star", "Nola", "Rama", "Stork",
]


# ── Pack size: captured BEFORE _prep strips it, normalized to g / ml / each ──
# Comparability across shops is (product type + size); per-pack prices lie when
# packs differ (Ritebrand 2kg vs No Name 2.5kg), so we keep size structured.
_MULTIPACK_RE = re.compile(
    r"\b(\d{1,3})\s*[xX]\s*(\d+(?:[.,]\d+)?)\s*(kg|g|gr|gram|grams|ml|l|lt|ltr|litre)s?\b", re.IGNORECASE)
_MEASURE_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(kg|g|gr|gram|grams|mg|ml|l|lt|ltr|litre)s?\b", re.IGNORECASE)
_COUNT_RE = re.compile(r"\b(\d{1,3})\s*(?:'?s\b|pk\b|pack\b|pcs\b|ea\b|doz\b|dozen\b)", re.IGNORECASE)

_UNIT_FACTOR = {  # -> (base unit, multiplier)
    "kg": ("g", 1000), "g": ("g", 1), "gr": ("g", 1), "gram": ("g", 1), "grams": ("g", 1),
    "mg": ("g", 0.001),
    "l": ("ml", 1000), "lt": ("ml", 1000), "ltr": ("ml", 1000), "litre": ("ml", 1000),
    "ml": ("ml", 1),
}


def parse_pack_size(raw_name: str) -> Tuple[Optional[float], Optional[str]]:
    """('COKE 6X330ML' -> (1980, 'ml')), ('SUGAR 2.5KG' -> (2500, 'g')),
    ('EGGS 18S' -> (18, 'each')). (None, None) when nothing printed."""
    if not raw_name:
        return None, None
    m = _MULTIPACK_RE.search(raw_name)
    if m:
        count, value, unit = int(m.group(1)), float(m.group(2).replace(",", ".")), m.group(3).lower()
        base, factor = _UNIT_FACTOR[unit]
        return round(count * value * factor, 3), base
    m = _MEASURE_RE.search(raw_name)
    if m:
        value, unit = float(m.group(1).replace(",", ".")), m.group(2).lower()
        base, factor = _UNIT_FACTOR[unit]
        size = round(value * factor, 3)
        return (size, base) if size > 0 else (None, None)
    m = _COUNT_RE.search(raw_name)
    if m:
        count = int(m.group(1))
        if "doz" in m.group(0).lower():
            count *= 12
        return (float(count), "each") if count > 0 else (None, None)
    return None, None


# ── GTIN (barcode) — the product world's Place ID, printed on some slips ─────
_GTIN_CONTEXT = re.compile(r"\b(gtin|ean|barcode|upc)\b", re.IGNORECASE)
_GTIN_TOKEN = re.compile(r"(?<!\d)(\d{8}|\d{12,14})(?!\d)")


def _gs1_check_ok(digits: str) -> bool:
    total = sum(int(d) * (3 if (len(digits) - i) % 2 == 0 else 1) for i, d in enumerate(digits[:-1]))
    return (10 - total % 10) % 10 == int(digits[-1])


def extract_gtin(raw_name: str) -> Optional[str]:
    """A GTIN only counts if its check digit validates AND either the line says
    so (GTIN/EAN/barcode) or it's a 13-digit code with South Africa's GS1
    prefix (600/601) — a bare number that merely looks long is not identity."""
    if not raw_name:
        return None
    labelled = bool(_GTIN_CONTEXT.search(raw_name))
    for m in _GTIN_TOKEN.finditer(raw_name):
        code = m.group(1)
        if not _gs1_check_ok(code):
            continue
        if labelled or (len(code) == 13 and code[:3] in ("600", "601")):
            return code
    return None


def _word_re(term: str) -> re.Pattern:
    """Whole-word/phrase matcher (case-insensitive). Avoids ICE matching RICE."""
    return re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)


# Precompile for speed
_CATEGORY_PATTERNS = [(cat, [_word_re(k) for k in kws]) for cat, kws in CATEGORY_RULES]
_BRAND_PATTERNS = [(b, _word_re(b)) for b in BRANDS]


def _expand(name: str) -> str:
    """Expand known abbreviations (whole-word). Runs BEFORE punctuation stripping
    so slash forms like F/CREAM -> FULL CREAM expand correctly."""
    out = name
    for abbr, full in ABBREVIATIONS.items():
        out = re.sub(r"\b" + re.escape(abbr) + r"\b", full, out, flags=re.IGNORECASE)
    return out


def _prep(raw_name: str) -> str:
    """OCR markup -> expand abbreviations -> strip codes/sizes/prices -> clean text."""
    if not raw_name:
        return ""
    s = raw_name
    # OCR markup like <::LOGO: ...::> and stray tags
    s = re.sub(r"<::[^>]*::>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    # expand abbreviations while slashes are still intact (F/CREAM, T/PAPER…)
    s = _expand(s)
    # leading PLU / barcode codes and standalone long digit runs
    s = re.sub(r"^\s*\d{3,}\s+", " ", s)
    s = re.sub(r"\b\d{5,}\b", " ", s)
    # pack sizes / units: 2L, 500g, 2 kg, 6x, x12, 750ML, 1.5LT, 20s
    s = re.sub(r"\b\d+([.,]\d+)?\s*(kg|kgs|g|gr|gram|grams|l|lt|ltr|litre|ml|"
               r"ea|pk|pack|pkt|pkts|doz|dz|ct|ctn|s|x)\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\bx\s?\d+\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d+\s?x\b", " ", s, flags=re.IGNORECASE)
    # currency / prices / asterisks / trailing bare numbers
    s = re.sub(r"r?\s*\d+[.,]\d{2}\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"[*#@]+", " ", s)
    s = re.sub(r"\s+\d+\s*$", " ", s)
    # collapse stray punctuation and whitespace
    s = re.sub(r"[._/\\|]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _canonical_key(prepped: str) -> str:
    """Order-invariant grouping key: significant tokens, lower-cased, sorted.
    'FC MILK 2L' and 'MILK F/CREAM' both -> 'cream full milk'."""
    tokens = [t.lower() for t in prepped.split() if len(t) > 1]
    return " ".join(sorted(set(tokens)))


NON_PRODUCT = "Non-product"


def categorize(name: str) -> str:
    """Return the retail category for an item name (rules-first, word-boundary)."""
    if not name:
        return UNCATEGORIZED
    if is_non_item(name):
        return NON_PRODUCT
    hay = _prep(name) or name
    for category, patterns in _CATEGORY_PATTERNS:
        if any(p.search(hay) for p in patterns):
            return category
    return UNCATEGORIZED


def detect_brand(name: str) -> Optional[str]:
    """Return the first recognised brand in the name, or None."""
    if not name:
        return None
    for brand, pat in _BRAND_PATTERNS:
        if pat.search(name):
            return brand
    return None


def _type_key(canonical_key: Optional[str], brand: Optional[str]) -> Optional[str]:
    """Brand-independent product key: the canonical_key minus the brand's own
    tokens. 'Ritebrand White Sugar 2kg' and 'No Name White Sugar' share the
    type_key 'sugar white' — with pack_size/unit, that's apples to apples."""
    if not canonical_key:
        return None
    if not brand:
        return canonical_key
    brand_tokens = {t for t in re.findall(r"[a-z0-9]+", brand.lower()) if len(t) > 1}
    kept = [t for t in canonical_key.split() if t not in brand_tokens]
    return " ".join(kept) or None


_EMPTY_ATTRS = {"brand": None, "brand_type": None, "brand_owner": None, "brand_tier": None,
                "pack_size": None, "pack_unit": None, "gtin": None, "type_key": None}


def normalize_item(raw_name: str, chain: Optional[str] = None) -> dict:
    """
    Normalize a raw OCR item name into a canonical product descriptor.

    chain — owner group of the shop the receipt came from (brand_registry.infer_chain);
            guards house-brand detection and enables the Woolworths chain-level rule.

    Returns: {raw_name, canonical_name, canonical_key, type_key, category,
              brand, brand_type, brand_owner, brand_tier, pack_size, pack_unit, gtin}
      canonical_name — human-readable cleaned label
      canonical_key  — order-invariant key grouping variants of one product
      type_key       — canonical_key minus brand tokens: the cross-shop,
                       cross-brand comparison key (with pack_size/pack_unit)
    Never raises — callers may use it inline without guarding.
    """
    try:
        category = categorize(raw_name)
        if category == NON_PRODUCT:
            # not a product — don't give it a grouping key or brand
            return {"raw_name": raw_name, "canonical_name": None,
                    "canonical_key": None, "category": NON_PRODUCT, **_EMPTY_ATTRS}
        cleaned = _prep(raw_name)
        canonical = cleaned.title() if cleaned else (raw_name or "").strip().title()
        canonical_key = _canonical_key(cleaned) or None
        pack_size, pack_unit = parse_pack_size(raw_name)

        house = detect_house_brand(raw_name, chain)
        if house:
            brand, brand_type = house["brand"], "house"
            brand_owner, brand_tier = house["owner"], house["tier"]
        else:
            brand = detect_brand(raw_name)
            brand_type = "national" if brand else None
            brand_owner = brand_tier = None
            if brand is None and chain in OWN_BRAND_CHAINS \
                    and category != UNCATEGORIZED \
                    and re.search(r"[A-Za-z]{3,}", cleaned or ""):
                # Woolworths sells essentially only own-brand: an unbranded line
                # at that chain IS the house brand — but only for lines that are
                # recognisably products (categorised, with a real word), so OCR
                # fragments like "S 15.0" don't become Woolworths products.
                brand, brand_type = OWN_BRAND_CHAINS[chain], "house"
                brand_owner, brand_tier = chain, "premium"

        return {
            "raw_name": raw_name,
            "canonical_name": canonical or None,
            "canonical_key": canonical_key,
            "type_key": _type_key(canonical_key, brand),
            "category": category,
            "brand": brand,
            "brand_type": brand_type,
            "brand_owner": brand_owner,
            "brand_tier": brand_tier,
            "pack_size": pack_size,
            "pack_unit": pack_unit,
            "gtin": extract_gtin(raw_name),
        }
    except Exception:
        return {
            "raw_name": raw_name,
            "canonical_name": (raw_name or "").strip().title() or None,
            "canonical_key": None,
            "category": UNCATEGORIZED,
            **_EMPTY_ATTRS,
        }
