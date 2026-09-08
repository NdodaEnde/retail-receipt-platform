"""
SA retail brand registry — house (private-label) brands and chain inference.

House brands only ever appear in their owner chain's stores, which gives us both
a detection guard (a "SPAR" token on a Shoprite slip is not the SPAR house brand)
and, later, a discovery mechanism (a brand token exclusive to one chain across
many receipts is a house-brand candidate).

Entries marked confirmed=False come from desk research that hasn't yet been
corroborated by a slip in our own data; they only match when the receipt's chain
agrees with the owner. Clothing-only labels (The Edit, Collection by Woolworths)
are deliberately absent — this registry serves till-slip grocery lines.

Public API:
    infer_chain(shop_name)                  -> owner-group name | None
    detect_house_brand(raw_name, chain)     -> {brand, owner, tier} | None
"""
from __future__ import annotations
import re
from typing import Optional

# Owner-group names (must match HOUSE_BRANDS[].owner)
SHOPRITE = "Shoprite Group"
PNP = "Pick n Pay Group"
WOOLWORTHS = "Woolworths"
SPAR = "SPAR"
MAKRO = "Makro"
CLICKS = "Clicks"
DISCHEM = "Dis-Chem"

# tier: value | mainstream | premium
HOUSE_BRANDS: list[dict] = [
    # ── Shoprite Group (Shoprite, Usave, Checkers, OK) ──
    {"brand": "Ritebrand",       "owner": SHOPRITE, "tier": "value",      "confirmed": True,  "aliases": ["RITEBRAND", "RITE BRAND"]},
    {"brand": "Ubrand",          "owner": SHOPRITE, "tier": "value",      "confirmed": False, "aliases": ["UBRAND", "U BRAND"]},
    {"brand": "Housebrand",      "owner": SHOPRITE, "tier": "mainstream", "confirmed": True,  "aliases": ["HOUSEBRAND", "HOUSE BRAND", "HSEBRAND"]},
    {"brand": "Simple Truth",    "owner": SHOPRITE, "tier": "premium",    "confirmed": True,  "aliases": ["SIMPLE TRUTH", "SMPL TRUTH"]},
    {"brand": "Forage & Feast",  "owner": SHOPRITE, "tier": "premium",    "confirmed": True,  "aliases": ["FORAGE & FEAST", "FORAGE AND FEAST", "FORAGE&FEAST"]},
    {"brand": "Oh My Goodness!", "owner": SHOPRITE, "tier": "mainstream", "confirmed": False, "aliases": ["OH MY GOODNESS"]},
    {"brand": "Foodie!",         "owner": SHOPRITE, "tier": "mainstream", "confirmed": False, "aliases": ["FOODIE"]},
    {"brand": "Cafe Culture",    "owner": SHOPRITE, "tier": "mainstream", "confirmed": False, "aliases": ["CAFE CULTURE", "CAFÉ CULTURE"]},
    {"brand": "Gourmade",        "owner": SHOPRITE, "tier": "premium",    "confirmed": False, "aliases": ["GOURMADE"]},
    {"brand": "Crystal Valley",  "owner": SHOPRITE, "tier": "mainstream", "confirmed": True,  "aliases": ["CRYSTAL VALLEY", "CRYSTAL VLY"]},  # seen in our own Shoprite receipts
    {"brand": "Royale",          "owner": SHOPRITE, "tier": "mainstream", "confirmed": False, "aliases": ["ROYALE"]},
    {"brand": "Pot O' Gold",     "owner": SHOPRITE, "tier": "value",      "confirmed": False, "aliases": ["POT O' GOLD", "POT O GOLD", "POT O'GOLD"]},
    # "OK brand" exists but the bare token OK is unmatchable safely — discovery will find it.

    # ── Pick n Pay Group (Pick n Pay, Boxer, TM) ──
    {"brand": "No Name",             "owner": PNP, "tier": "value",      "confirmed": True,  "aliases": ["NO NAME", "NONAME", "NO-NAME"]},
    {"brand": "PnP",                 "owner": PNP, "tier": "mainstream", "confirmed": True,  "aliases": ["PNP", "P N P", "PICK N PAY"]},
    {"brand": "PnP Finest",          "owner": PNP, "tier": "premium",    "confirmed": True,  "aliases": ["PNP FINEST", "FINEST COLLECTION"]},
    {"brand": "Crafted Collection",  "owner": PNP, "tier": "premium",    "confirmed": False, "aliases": ["CRAFTED COLLECTION", "THE CRAFTED COLLECTION"]},
    {"brand": "Qualisave",           "owner": PNP, "tier": "value",      "confirmed": False, "aliases": ["QUALISAVE"]},
    {"brand": "Boxer",               "owner": PNP, "tier": "value",      "confirmed": False, "aliases": ["BOXER"]},

    # ── Woolworths (essentially all own-brand — see chain-level rule below) ──
    {"brand": "Woolworths",   "owner": WOOLWORTHS, "tier": "premium",    "confirmed": True,  "aliases": ["WOOLWORTHS", "W/WORTHS"]},
    {"brand": "Good Living",  "owner": WOOLWORTHS, "tier": "mainstream", "confirmed": False, "aliases": ["GOOD LIVING"]},

    # ── SPAR ──
    {"brand": "SPAR",                "owner": SPAR, "tier": "mainstream", "confirmed": True,  "aliases": ["SPAR"]},
    {"brand": "SPAR Premium",        "owner": SPAR, "tier": "premium",    "confirmed": False, "aliases": ["SPAR PREMIUM", "SIGNATURE SELECTION"]},
    {"brand": "Nature's Choice",     "owner": SPAR, "tier": "mainstream", "confirmed": False, "aliases": ["NATURE'S CHOICE", "NATURES CHOICE"]},

    # ── Others ──
    {"brand": "M Brand",  "owner": MAKRO,   "tier": "value",      "confirmed": False, "aliases": ["M BRAND", "M-BRAND"]},
    {"brand": "Clicks",   "owner": CLICKS,  "tier": "mainstream", "confirmed": True,  "aliases": ["CLICKS"]},
    {"brand": "Dis-Chem", "owner": DISCHEM, "tier": "mainstream", "confirmed": True,  "aliases": ["DIS-CHEM", "DISCHEM"]},
]

# Chains where effectively the whole shelf is own-brand: an item with no other
# detected brand at these chains is treated as the chain's house brand.
OWN_BRAND_CHAINS = {WOOLWORTHS: "Woolworths"}

_CHAIN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(checkers|shoprite|usave|u-save|ok foods|ok minimark|ok value)\b", re.I), SHOPRITE),
    (re.compile(r"\b(pick n pay|pick 'n pay|pnp|boxer)\b", re.I), PNP),
    (re.compile(r"\b(woolworths|woolies)\b", re.I), WOOLWORTHS),
    (re.compile(r"\b(superspar|kwikspar|spar)\b", re.I), SPAR),
    (re.compile(r"\bmakro\b", re.I), MAKRO),
    (re.compile(r"\bclicks\b", re.I), CLICKS),
    (re.compile(r"\b(dis-chem|dischem)\b", re.I), DISCHEM),
]


def infer_chain(shop_name: Optional[str]) -> Optional[str]:
    """Owner group a shop belongs to, from its (canonical or OCR) name."""
    if not shop_name:
        return None
    for pattern, owner in _CHAIN_PATTERNS:
        if pattern.search(shop_name):
            return owner
    return None


def _alias_re(alias: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(alias).replace(r"\ ", r"\s+") + r"\b", re.I)


_HOUSE_PATTERNS = [
    (entry, [_alias_re(a) for a in entry["aliases"]]) for entry in HOUSE_BRANDS
]


def detect_house_brand(raw_name: str, chain: Optional[str] = None) -> Optional[dict]:
    """
    Detect a house brand in an item line, guarded by the receipt's chain:
      * chain known and disagrees with the owner  -> no match (that token means
        something else there — "SPAR" printed at a Shoprite is not SPAR-brand)
      * chain unknown                             -> confirmed entries only
      * chain agrees                              -> confirmed and unverified match
    Returns {"brand", "owner", "tier"} or None.
    """
    if not raw_name:
        return None
    for entry, patterns in _HOUSE_PATTERNS:
        if chain is not None and chain != entry["owner"]:
            continue
        if chain is None and not entry["confirmed"]:
            continue
        if any(p.search(raw_name) for p in patterns):
            return {"brand": entry["brand"], "owner": entry["owner"], "tier": entry["tier"]}
    return None
