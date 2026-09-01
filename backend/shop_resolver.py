"""
Shop resolution — several independent witnesses, confidence from agreement.

Witnesses: the slip's phone number, its address text, its suburb, its postcode
(all verified by extraction_verifier), Google Places / Geocoding, and the
customer's location (a *bias* and plausibility check, never proof).

    resolve_shop(...) -> Resolution | None

Precision of the result:
    verified  two independent witnesses agree — the place's phone number matches
              the slip, or its name AND its address agree with the slip's text
    rooftop   one precise witness (address geocode / name+postcode)
    biased    found only by searching around the customer (name match) — a small
              distance to the customer is NOT fraud evidence
    street / suburb / city   coarser address geocodes
Every step taken is recorded in Resolution.evidence.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from geocoding import (get_geocoding_service, address_consistent, _name_tokens,
                       SA_LOCATIONS, GOOD_PRECISION)
from extraction_verifier import METRO_CITIES

logger = logging.getLogger(__name__)

STREET_WORDS = (' st', ' rd', ' ave', ' dr', ' blvd', ' ln', ' cres', 'street', 'road',
                'avenue', 'drive', 'boulevard', 'lane', 'crescent')


@dataclass
class Resolution:
    latitude: float
    longitude: float
    formatted_address: str
    display_name: str
    precision: str
    place_id: Optional[str] = None     # only for Places (establishment) results — the branch identity
    place_name: Optional[str] = None   # Google's own name for the business
    source: str = ""
    evidence: List[str] = field(default_factory=list)


def _digits(s: Optional[str]) -> str:
    return re.sub(r"\D", "", s or "")


PREMISE_WORDS = ("shop", "unit", "level", "floor", "corner", "cnr", "centre", "center", "mall",
                 "shopping", "block", "building", "suite", "wharf", "&", "ah")


def suburb_from_formatted(formatted: Optional[str]) -> Optional[str]:
    """
    Google formats SA addresses as 'Premise, Street, Suburb, City, Postcode, Country'.
    The suburb is the part two before the postcode; without a postcode, the first
    part that is neither a premise nor a street.
    """
    if not formatted:
        return None
    parts = [p.strip() for p in formatted.split(",")]
    parts = [p for p in parts if p and "south africa" not in p.lower()]
    if len(parts) < 2:
        return None

    def is_place(part: str) -> bool:
        low = part.lower()
        if part.isdigit() or len(part) <= 3 or re.search(r"\d", part):
            return False
        if any(w in low.split() or w in low for w in PREMISE_WORDS) or any(w in low for w in STREET_WORDS):
            return False
        return True

    pc = next((i for i, p in enumerate(parts) if re.fullmatch(r"\d{4}", p)), None)
    if pc is not None:
        for i in (pc - 2, pc - 1):
            if 0 < i < len(parts) and is_place(parts[i]):
                return parts[i]
    for part in parts[1:]:
        if is_place(part):
            return part
    return None


def display_name_with(shop_name: str, suburb: Optional[str]) -> str:
    if suburb and suburb.lower() not in shop_name.lower():
        return f"{shop_name} {suburb}"
    return shop_name


def display_name_from_ocr_address(shop_name: str, shop_address: Optional[str]) -> str:
    """
    When resolution fails, still give the customer a location in the confirmation
    ("Chicken Licken, Sloane Square") using the address text read off the slip.
    """
    if not shop_address or re.search(r"www\.|https?:|\.co\b|\.com\b|@", shop_address.lower()):
        return shop_name
    lowered = shop_address.lower()
    for suburb in SA_LOCATIONS:
        if suburb in lowered and suburb not in shop_name.lower():
            return f"{shop_name} {suburb.title()}"
    short = shop_address.strip(" ,.")
    if 0 < len(short) <= 32 and not re.search(r"\d{3,}", short) and short.lower() not in shop_name.lower():
        return f"{shop_name}, {short}"
    return shop_name


def _name_matches(shop_name: str, place_name: str) -> bool:
    want = _name_tokens(shop_name)
    return not want or bool(want & _name_tokens(place_name))


_BRAND_SKIP = {"the", "la", "le", "el", "cafe", "café", "restaurant", "store", "shop"}


def _brand_matches(shop_name: str, place_name: str) -> bool:
    """
    The slip's *brand* token (first meaningful word) must appear in the place's
    name — otherwise "Checkers Walmer Park" happily matches the mall itself.
    Fuzzy on containment so OCR damage survives ("ARGAIN" ~ "Bargain").
    """
    tokens = [t for t in re.findall(r"[a-z0-9]+", (shop_name or "").lower()) if len(t) >= 3 and t not in _BRAND_SKIP]
    if not tokens:
        return True
    brand = tokens[0]
    for got in re.findall(r"[a-z0-9]+", (place_name or "").lower()):
        if got == brand or (len(brand) >= 4 and (brand in got or got in brand)):
            return True
    return False


async def resolve_shop(shop_name: Optional[str], address: Optional[str] = None,
                       address_lines: Optional[List[str]] = None, postal_code: Optional[str] = None,
                       phone: Optional[str] = None, suburb: Optional[str] = None,
                       customer_lat: Optional[float] = None, customer_lon: Optional[float] = None
                       ) -> Optional[Resolution]:
    svc = get_geocoding_service()
    evidence: List[str] = []
    has_customer = customer_lat is not None and customer_lon is not None
    bias = (customer_lat, customer_lon) if has_customer else (None, None)
    address = address or (", ".join(address_lines) if address_lines else None)
    fallback: Optional[Resolution] = None

    def make(place, precision, source, disp_suburb=None) -> Resolution:
        is_place = source.startswith("places:")
        place_name = place.get("name") if is_place else None
        # Google's business name is canonical when it plausibly names the same shop;
        # otherwise (odd phone matches) keep what the slip said.
        if place_name and (not shop_name or _brand_matches(shop_name, place_name)):
            name = place_name
        else:
            name = shop_name or place_name or "Shop"
        sub = disp_suburb or suburb_from_formatted(place.get("formatted_address"))
        return Resolution(
            latitude=place["latitude"], longitude=place["longitude"],
            formatted_address=place.get("formatted_address", ""),
            display_name=display_name_with(name, sub), precision=precision,
            place_id=place.get("place_id") if is_place else None, place_name=place_name,
            source=source, evidence=list(evidence),
        )

    # 1. Phone number — a branch identifier. Places supports phone-number queries.
    if phone:
        want = _digits(phone)[-9:]
        for place in await svc.places_text_search(phone, *bias):
            if _digits(place.get("phone"))[-9:] == want:
                evidence.append(f"phone {phone} matches {place['name']!r}")
                if shop_name and not _name_matches(shop_name, place["name"]):
                    evidence.append(f"note: place name {place['name']!r} differs from slip name {shop_name!r}")
                return make(place, "verified", "places:phone")
        evidence.append(f"phone {phone}: no place with that number")

    if not shop_name and not address:
        evidence.append("no shop name or address to search with")
        logger.warning("resolve_shop: nothing to search with")
        return None

    # 2. Name + address text — verified when the place's address agrees with the slip.
    #    Long OCR addresses confuse text search, so also try the first line or two.
    if shop_name and address:
        queries = [f"{shop_name} {address}"]
        if address_lines and len(address_lines) > 1:
            queries.append(f"{shop_name} {' '.join(address_lines[:2])}")
        seen = set()
        for query in queries:
            for place in await svc.places_text_search(query, *bias):
                if place.get("place_id") in seen:
                    continue
                seen.add(place.get("place_id"))
                name_ok = _brand_matches(shop_name, place["name"])
                addr_ok = address_consistent(address, place["formatted_address"])
                if name_ok and addr_ok:
                    evidence.append(f"name+address agree with {place['formatted_address']!r}")
                    return make(place, "verified", "places:name+address")
                if name_ok and has_customer and fallback is None:
                    fallback = make(place, "biased", "places:name+address(bias-only)")
        evidence.append("name+address search: no candidate agreed with the slip's address")

    # 3. Name + suburb from the slip (a metro city is not a suburb — it cannot pick a branch)
    if shop_name and suburb and suburb.lower() not in METRO_CITIES:
        for place in await svc.places_text_search(f"{shop_name} {suburb}", *bias):
            if _brand_matches(shop_name, place["name"]) and suburb.lower() in place["formatted_address"].lower():
                evidence.append(f"name+suburb {suburb!r} agree with {place['formatted_address']!r}")
                return make(place, "verified", "places:name+suburb")
        evidence.append(f"name+suburb search: no agreement on {suburb!r}")

    # 4. Address geocode (independent of name); must be consistent with the slip
    if address:
        for query, name in ((address, shop_name), (address, None)):
            result = await svc.geocode_address(query, name)
            if result and result.get("precision") in GOOD_PRECISION and result.get("source") == "google_maps" \
                    and address_consistent(address, result.get("formatted_address")):
                evidence.append(f"address geocoded [{result['precision']}] {result.get('formatted_address')!r}")
                return make(result, result["precision"], "geocode:address")
        evidence.append("address geocode: no consistent result")

    # 5. Name + postcode
    if shop_name and postal_code:
        result = await svc.geocode_address(f"{shop_name}, {postal_code}, South Africa", None)
        if result and result.get("precision") in GOOD_PRECISION and postal_code in (result.get("formatted_address") or ""):
            evidence.append(f"name+postcode {postal_code} -> {result.get('formatted_address')!r}")
            return make(result, "rooftop", "geocode:name+postcode")
        evidence.append(f"name+postcode {postal_code}: no result in that postcode")

    # 6. Name near the customer (bias-only: not independent evidence)
    if shop_name and has_customer:
        if fallback is None:
            for place in await svc.places_text_search(shop_name, *bias):
                if _brand_matches(shop_name, place["name"]):
                    fallback = make(place, "biased", "places:name(bias-only)")
                    break
        if fallback:
            fallback.evidence = evidence + [f"matched by name near customer: {fallback.formatted_address!r}"]
            return fallback
        evidence.append("no name match near the customer")

    # 7. Postcode alone -> city-level
    if postal_code:
        result = await svc.geocode_address(f"{postal_code}, South Africa", None)
        if result and "postal_code" in (result.get("types") or []):
            evidence.append(f"postcode {postal_code} alone -> city level")
            return make(result, "city", "geocode:postcode")

    logger.warning(f"resolve_shop: unresolved {shop_name!r} / {address!r} / {phone!r} — " + "; ".join(evidence))
    return None
