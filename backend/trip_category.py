"""
Trip category — the one label a receipt gets on the Activity Map (pure, no I/O).

Item categories describe *products* (a Coke at KFC is still a Coke, which is what
a brand client wants). A trip label describes the *mission*: a visit to KFC is a
takeaway trip, not a "Beverages" trip because the Sprite was the only line the
rules recognised. So:

  1. food-service shop (fast-food chain, restaurant-ish name, or any Dining line
     on the slip — except at grocery chains, where a Dining line is a ready meal
     and only wins by value like any category)    -> "Dining & Takeaways"
  2. else the category with the most line value, but only if it covers at least
     MIN_SHARE of the receipt — one R30 jar of jam must not label a R240 Pick n Pay
     shop as "Staples"                             -> that category
  3. otherwise                                     -> "Other" (mixed / unrecognised)
"""
import re
from typing import Dict, Iterable, Optional

from brand_registry import infer_chain
from category_drilldown import line_spend

DINING = "Dining & Takeaways"
OTHER = "Other"
MIN_SHARE = 0.25
_IGNORED = {None, "", OTHER, "Non-product"}

FOOD_SERVICE_CHAINS = [
    "kfc", "debonairs", "chicken licken", "nando's", "nandos", "steers", "wimpy", "mcdonald's",
    "mcdonalds", "spur", "ocean basket", "burger king", "fishaways", "roman's pizza", "romans pizza",
    "pizza hut", "mugg & bean", "mugg and bean", "vida e caffe", "seattle coffee", "starbucks",
    "galito's", "galitos", "rocomamas", "panarottis", "john dory's", "col'cacchio", "simply asia",
    "hungry lion", "king pie", "pedros", "barcelos", "domino's", "dominos", "dunkin", "krispy kreme",
    "milky lane", "news cafe", "turn n tender", "the hussar grill", "tashas", "fego",
]
FOOD_SERVICE_WORDS = [
    "restaurant", "rest", "grill", "grills", "grillhouse", "bistro", "brasserie", "cafe", "café",
    "coffee", "pizza", "pizzeria", "trattoria", "osteria", "kitchen", "eatery", "diner", "tavern",
    "pub", "bar", "lounge", "cocktail", "steakhouse", "sushi", "shisanyama", "chisa nyama",
    "takeaway", "takeaways", "canteen", "bakery cafe",
    "country club", "golf club", "golf estate", "clubhouse", "club house", "halfway house",
]
_CHAIN_RE = re.compile(r"\b(" + "|".join(re.escape(c) for c in FOOD_SERVICE_CHAINS) + r")\b", re.IGNORECASE)
_WORD_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in FOOD_SERVICE_WORDS) + r")\b", re.IGNORECASE)


def is_food_service(shop_name: Optional[str], item_categories: Iterable[Optional[str]] = ()) -> bool:
    """A restaurant / takeaway / bar / café, by name or by what's on the slip."""
    if shop_name and (_CHAIN_RE.search(shop_name) or _WORD_RE.search(shop_name)):
        return True
    if infer_chain(shop_name):  # Checkers / Pick n Pay / Woolworths / SPAR sell ready meals
        return False
    return any(c == DINING for c in item_categories)


def trip_category(items: Iterable[dict], amount, shop_name: Optional[str] = None,
                  min_share: float = MIN_SHARE) -> str:
    """items: receipt_items rows (category, total_price, quantity, unit_price)."""
    items = list(items)
    if is_food_service(shop_name, (i.get("category") for i in items)):
        return DINING
    totals: Dict[str, float] = {}
    for it in items:
        cat = it.get("category")
        if cat in _IGNORED:
            continue
        totals[cat] = totals.get(cat, 0.0) + line_spend(it)[0]
    if not totals:
        return OTHER
    best = max(totals, key=totals.get)
    product_value = sum(line_spend(i)[0] for i in items if i.get("category") != "Non-product")
    try:
        base = max(float(amount or 0), product_value)
    except (TypeError, ValueError):
        base = product_value
    return best if base and totals[best] / base >= min_share else OTHER
