"""
Geocoding Service for Shop Location Resolution
Primary: Google Maps Geocoding API (accurate, good SA coverage)
Fallback: Local SA database for offline/rate-limited scenarios
"""

import os
import logging
import asyncio
import re
from typing import Dict, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Google's geographic centre of South Africa. When the Geocoding API cannot match a
# query it does NOT return ZERO_RESULTS — it returns the *country* with status OK at
# these coordinates. Accepting that pinned receipts to the middle of the Karoo and
# false-flagged them as >200 km fraud.
SA_CENTROID = (-30.559482, 22.937506)

# Result `types` that mean "we matched a region, not a place" → treat as a miss.
REGION_TYPES = {"country", "administrative_area_level_1", "administrative_area_level_2"}

# Precision of a resolved shop location. Ordered from best to worst.
#   rooftop  – a specific establishment / street address
#   biased   – establishment found via Places search biased to the customer's
#              location (accurate, but not independent evidence for fraud)
#   street   – a road, no number
#   suburb   – suburb / neighbourhood centroid
#   city     – town / postal-code centroid
#   none     – unresolved
PRECISION_RANK = {"rooftop": 4, "biased": 3, "street": 3, "suburb": 2, "city": 1, "none": 0}
# Legacy geocode_confidence values written by the /geocode endpoints
PRECISION_RANK.update({"high": 3, "medium": 2, "low": 1})
GOOD_PRECISION = {"rooftop", "biased", "street", "suburb"}


def is_sa_centroid(lat, lon) -> bool:
    try:
        return abs(float(lat) - SA_CENTROID[0]) < 1e-4 and abs(float(lon) - SA_CENTROID[1]) < 1e-4
    except (TypeError, ValueError):
        return False


def precision_rank(value) -> int:
    return PRECISION_RANK.get((value or "none").lower(), 0)


def classify_precision(types, location_type: str = "") -> Optional[str]:
    """Map Google result types → precision. Returns None for region-level matches."""
    t = set(types or [])
    if t & REGION_TYPES:
        return None
    if t & {"establishment", "point_of_interest", "street_address", "premise", "subpremise"} \
            or location_type == "ROOFTOP":
        return "rooftop"
    if t & {"route", "intersection"} or location_type == "RANGE_INTERPOLATED":
        return "street"
    if any(x.startswith("sublocality") for x in t) or "neighborhood" in t:
        return "suburb"
    if t & {"locality", "postal_code", "postal_town"}:
        return "city"
    return "city"


def _name_tokens(name: str) -> set:
    stop = {"the", "and", "shop", "store", "stores", "cafe", "café", "restaurant", "pty", "ltd", "cc"}
    return {w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if len(w) >= 3 and w not in stop}


_ADDRESS_STOP = {
    "shop", "shops", "unit", "cnr", "corner", "centre", "center", "mall", "plaza", "park", "square",
    "street", "road", "drive", "avenue", "boulevard", "lane", "crescent", "highway", "main",
    "south", "africa", "shopping", "retail", "floor", "level", "block", "north", "east", "west",
    "upper", "lower", "ground", "entrance", "gate", "tel", "phone", "fax",
}

def _place_tokens(text: str) -> set:
    """Alphabetic tokens (≥4 chars) that plausibly name a place: suburbs, streets, malls."""
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in _ADDRESS_STOP}


def address_consistent(ocr_address: Optional[str], formatted_address: Optional[str]) -> bool:
    """
    Guard against a *precise but wrong* match: Google happily geocodes
    "Pick n Pay, Douglasdale … Leslie Ave" to a shop 111 km away if the query is
    polluted. If the receipt address names any place, the result must name at least
    one of the same places. No place tokens on the receipt → nothing to check → True.
    """
    want = _place_tokens(ocr_address)
    if not want:
        return True
    got = _place_tokens(formatted_address)
    # allow prefix matches for OCR truncations / plurals ("douglas" ~ "douglasdale")
    for w in want:
        for g in got:
            if w == g or (len(w) >= 5 and (g.startswith(w) or w.startswith(g))):
                return True
    return False

# Fallback: Pre-defined coordinates for major SA locations
SA_LOCATIONS = {
    # Cape Town Southern Suburbs
    "constantia": {"lat": -34.0230, "lon": 18.4260},
    "newlands": {"lat": -33.9780, "lon": 18.4580},
    "claremont": {"lat": -33.9850, "lon": 18.4670},
    "wynberg": {"lat": -34.0010, "lon": 18.4650},
    "kenilworth": {"lat": -33.9980, "lon": 18.4810},
    "tokai": {"lat": -34.0550, "lon": 18.4430},
    "rondebosch": {"lat": -33.9630, "lon": 18.4730},
    "plumstead": {"lat": -34.0160, "lon": 18.4700},
    
    # Cape Town Northern Suburbs
    "brackenfell": {"lat": -33.8789, "lon": 18.6989},
    "bellville": {"lat": -33.9017, "lon": 18.6291},
    "durbanville": {"lat": -33.8320, "lon": 18.6470},
    "kraaifontein": {"lat": -33.8510, "lon": 18.7280},
    "kuils river": {"lat": -33.9310, "lon": 18.6850},
    
    # Cape Town Atlantic Seaboard & City Bowl
    "sea point": {"lat": -33.9170, "lon": 18.3880},
    "green point": {"lat": -33.9050, "lon": 18.4000},
    "camps bay": {"lat": -33.9510, "lon": 18.3780},
    "cape town": {"lat": -33.9249, "lon": 18.4241},
    "gardens": {"lat": -33.9330, "lon": 18.4130},
    
    # Johannesburg
    "sandton": {"lat": -26.1076, "lon": 28.0567},
    "rosebank": {"lat": -26.1452, "lon": 28.0445},
    "fourways": {"lat": -26.0173, "lon": 28.0128},
    "bryanston": {"lat": -26.0586, "lon": 28.0214},
    "soweto": {"lat": -26.2485, "lon": 27.8540},
    "johannesburg": {"lat": -26.2041, "lon": 28.0473},
    "randburg": {"lat": -26.0943, "lon": 27.9980},
    
    # Pretoria / Centurion
    "pretoria": {"lat": -25.7461, "lon": 28.1881},
    "centurion": {"lat": -25.8603, "lon": 28.1894},
    "midrand": {"lat": -25.9891, "lon": 28.1271},
    
    # Other major cities
    "durban": {"lat": -29.8587, "lon": 31.0218},
    "port elizabeth": {"lat": -33.9608, "lon": 25.6022},
    "gqeberha": {"lat": -33.9608, "lon": 25.6022},
    "bloemfontein": {"lat": -29.0852, "lon": 26.1596},
    "east london": {"lat": -33.0153, "lon": 27.9116},
    "polokwane": {"lat": -23.9045, "lon": 29.4688},
    "nelspruit": {"lat": -25.4753, "lon": 30.9694},
    "mbombela": {"lat": -25.4753, "lon": 30.9694},
    "kimberley": {"lat": -28.7282, "lon": 24.7499},
    "rustenburg": {"lat": -25.6670, "lon": 27.2420},
    "pietermaritzburg": {"lat": -29.6006, "lon": 30.3794},
    
    # Garden Route
    "george": {"lat": -33.9631, "lon": 22.4617},
    "knysna": {"lat": -34.0356, "lon": 23.0488},
    "plettenberg bay": {"lat": -34.0527, "lon": 23.3716},
    "mossel bay": {"lat": -34.1831, "lon": 22.1464},
    
    # Winelands
    "stellenbosch": {"lat": -33.9346, "lon": 18.8640},
    "paarl": {"lat": -33.7271, "lon": 18.9706},
    "franschhoek": {"lat": -33.9133, "lon": 19.1180},
}


class GeocodingService:
    """
    Geocoding service with Google Maps as primary and local fallback
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        # Load API key at initialization time (after .env is loaded by server.py)
        self.google_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
        
        if self.google_api_key:
            logger.info("✅ Google Maps Geocoding API configured")
        else:
            logger.warning("⚠️ Google Maps API key not set - using local fallback only")
    
    async def geocode_address(self, address: str, shop_name: str = None) -> Optional[Dict]:
        """
        Geocode an address to lat/long coordinates
        
        Priority:
        1. Cache lookup
        2. Google Maps API (if key available)
        3. Local SA database fallback
        """
        if not address and not shop_name:
            return None
        
        # Build search query
        search_query = self._build_search_query(address, shop_name)
        cache_key = search_query.lower()
        
        # Check cache
        if cache_key in self._cache:
            logger.debug(f"Cache hit for: {search_query}")
            return self._cache[cache_key]
        
        # Try Google Maps API first
        if self.google_api_key:
            result = await self._google_geocode(search_query)
            if result:
                self._cache[cache_key] = result
                return result
        
        # Fallback to local database
        result = self._local_lookup(address, shop_name)
        if result:
            self._cache[cache_key] = result
            return result
        
        # Return None with graceful handling - don't assume fraud
        logger.warning(f"Could not geocode: {search_query}")
        return None
    
    def _build_search_query(self, address: str, shop_name: str = None) -> str:
        """Build optimized search query for SA addresses"""
        parts = []
        
        if shop_name:
            parts.append(shop_name)
        if address:
            parts.append(address)
        
        query = ", ".join(parts)
        
        # Add South Africa if not present
        if "south africa" not in query.lower():
            query = f"{query}, South Africa"
        
        return query
    
    async def _google_geocode(self, query: str) -> Optional[Dict]:
        """Geocode using Google Maps API"""
        params = {
            "address": query,
            "key": self.google_api_key,
            "region": "za",  # Bias results to South Africa
            "components": "country:ZA"  # Restrict to South Africa
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    GOOGLE_GEOCODE_URL,
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("status") == "OK" and data.get("results"):
                        result = data["results"][0]
                        location = result["geometry"]["location"]
                        location_type = result["geometry"].get("location_type", "")
                        types = result.get("types", [])

                        precision = classify_precision(types, location_type)
                        if precision is None or is_sa_centroid(location["lat"], location["lng"]):
                            # Country / province match = Google could not find the place.
                            logger.warning(
                                f"Google Maps: region-level match for '{query}' "
                                f"({result.get('formatted_address')}, types={types}) — treating as no result"
                            )
                            return None

                        confidence = {"rooftop": "high", "street": "high", "suburb": "medium"}.get(precision, "low")
                        logger.info(f"✅ Google geocoded: {query} -> {location['lat']}, {location['lng']} ({precision})")

                        return {
                            "latitude": location["lat"],
                            "longitude": location["lng"],
                            "formatted_address": result.get("formatted_address", query),
                            "source": "google_maps",
                            "confidence": confidence,
                            "precision": precision,
                            "types": types,
                            "place_id": result.get("place_id"),
                            "location_type": location_type
                        }
                    
                    elif data.get("status") == "ZERO_RESULTS":
                        logger.warning(f"Google Maps: No results for '{query}'")
                    
                    elif data.get("status") == "REQUEST_DENIED":
                        logger.error(f"Google Maps API key invalid or restricted: {data.get('error_message')}")
                    
                    elif data.get("status") == "OVER_QUERY_LIMIT":
                        logger.error("Google Maps API quota exceeded")
                    
                    else:
                        logger.warning(f"Google Maps API status: {data.get('status')}")
                        
        except httpx.TimeoutException:
            logger.warning("Google Maps API request timed out")
        except Exception as e:
            logger.error(f"Google Maps geocoding error: {e}")
        
        return None
    
    def _local_lookup(self, address: str, shop_name: str = None) -> Optional[Dict]:
        """Fallback: Look up from local SA database"""
        combined = f"{shop_name or ''} {address or ''}".lower()
        
        for location, coords in SA_LOCATIONS.items():
            if location in combined:
                return {
                    "latitude": coords["lat"],
                    "longitude": coords["lon"],
                    "formatted_address": f"{location.title()}, South Africa",
                    "source": "local_fallback",
                    "confidence": "low",
                    "precision": "suburb",
                    "note": "Approximate location from local database"
                }
        
        return None
    
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """Reverse geocode coordinates to get suburb/area name for search disambiguation.
        Returns a simple string like 'Douglasdale' or 'Sandton', NOT a dict."""
        if not self.google_api_key:
            return None
        try:
            params = {
                "latlng": f"{lat},{lon}",
                "key": self.google_api_key,
                "result_type": "sublocality|locality"
            }
            async with httpx.AsyncClient() as client:
                response = await client.get(GOOGLE_GEOCODE_URL, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "OK" and data.get("results"):
                        # Look for suburb/locality in address components
                        for component in data["results"][0].get("address_components", []):
                            types = component.get("types", [])
                            if "sublocality" in types or "sublocality_level_1" in types:
                                area = component["long_name"]
                                logger.info(f"Reverse geocoded ({lat},{lon}) -> {area}")
                                return area
                            if "locality" in types:
                                area = component["long_name"]
                                logger.info(f"Reverse geocoded ({lat},{lon}) -> {area}")
                                return area
                        # Fallback: first part of formatted address
                        formatted = data["results"][0].get("formatted_address", "")
                        if formatted:
                            area = formatted.split(",")[0].strip()
                            logger.info(f"Reverse geocoded ({lat},{lon}) -> {area} (fallback)")
                            return area
        except Exception as e:
            logger.warning(f"Reverse geocode failed: {e}")
        return None

    async def _places_search_biased(self, shop_name: str, address: Optional[str],
                                    lat: float, lon: float, radius_m: int = 10000) -> Optional[Dict]:
        """
        Places API (New) text search, *biased* (not restricted) to a circle around the
        customer. Finds the right branch of a chain store. The returned place must
        share a name token with the OCR shop name, otherwise it is discarded.
        """
        if not self.google_api_key or not shop_name:
            return None

        query = f"{shop_name} {address}".strip() if address else shop_name
        body = {
            "textQuery": query[:200],
            "regionCode": "ZA",
            "maxResultCount": 3,
            "locationBias": {"circle": {
                "center": {"latitude": float(lat), "longitude": float(lon)},
                "radius": float(radius_m)
            }}
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.google_api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.types",
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(GOOGLE_PLACES_SEARCH_URL, headers=headers, json=body, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Places search failed ({response.status_code}): {response.text[:200]}")
                return None
            want = _name_tokens(shop_name)
            for place in response.json().get("places", []):
                got = _name_tokens((place.get("displayName") or {}).get("text", ""))
                if want and not (want & got):
                    continue
                loc = place.get("location") or {}
                if "latitude" not in loc:
                    continue
                logger.info(f"✅ Places (customer-biased) matched '{query}' -> {place.get('formattedAddress')}")
                return {
                    "latitude": loc["latitude"],
                    "longitude": loc["longitude"],
                    "formatted_address": place.get("formattedAddress", ""),
                    "source": "google_places",
                    "confidence": "high",
                    "precision": "biased",
                    "types": place.get("types", []),
                    "place_id": place.get("id"),
                    "note": "Matched via Places search biased to customer location",
                }
            logger.warning(f"Places search: no name-matching result for '{query}'")
        except Exception as e:
            logger.error(f"Places search error: {e}")
        return None

    async def geocode_shop(self, shop_name: str, address: str = None, receipt_text: str = None,
                           postal_code: str = None, customer_lat: float = None,
                           customer_lon: float = None) -> Optional[Dict]:
        """
        Resolve a shop's location. Every accepted result carries a `precision`.

        Order (independent evidence first, customer-derived evidence last):
          1. receipt address (± shop name)      → accept rooftop/street/suburb, and the
                                                  result must name a place the receipt names
          2. shop name + postal code            → accept rooftop/street/suburb (same check)
          3. Places search biased to customer   → precision "biased"
          4. postal code alone                  → precision "city", only if Google
                                                  agrees it is a postal code
        There is deliberately NO shop-name-only guess: for a chain that returns an
        arbitrary branch, which is worse than no location at all.
        """
        def ok(r, check_address=True):
            if not (r and r.get("precision") in GOOD_PRECISION):
                return False
            if check_address and address and r.get("source") == "google_maps" \
                    and not address_consistent(address, r.get("formatted_address")):
                logger.warning(f"Geocode rejected as inconsistent with receipt address "
                               f"{address!r}: {r.get('formatted_address')!r}")
                return False
            return True

        # 1. Receipt address (most specific evidence), must agree with itself
        if address:
            for query, name in ((address, shop_name), (f"{shop_name}, {address}", None) if shop_name else (None, None), (address, None)):
                if not query:
                    continue
                result = await self.geocode_address(query, name)
                if ok(result):
                    return result

        # 2. Shop name + postal code (good for small towns / when address is noisy)
        if postal_code and shop_name:
            query_with_postal = f"{shop_name}, {postal_code}, South Africa"
            logger.info(f"Geocoding with postal code: {query_with_postal}")
            result = await self.geocode_address(query_with_postal, None)
            if ok(result):
                result["note"] = f"Geocoded using postal code {postal_code}"
                return result

        # 3. Places search biased to the customer (marked precision="biased")
        if shop_name and customer_lat is not None and customer_lon is not None:
            result = await self._places_search_biased(shop_name, address, customer_lat, customer_lon)
            if result:
                return result

        if postal_code:
            result = await self.geocode_address(f"{postal_code}, South Africa", None)
            if result and "postal_code" in (result.get("types") or []):
                result["precision"] = "city"
                result["confidence"] = "low"
                result["note"] = f"Geocoded from postal code {postal_code} only"
                return result

        logger.warning(f"Could not resolve shop location: {shop_name!r} / {address!r} / {postal_code!r}")
        return None

    async def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Convert coordinates to address (useful for customer location context)
        """
        if not self.google_api_key:
            return None
        
        params = {
            "latlng": f"{lat},{lon}",
            "key": self.google_api_key,
            "result_type": "street_address|locality|sublocality"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    GOOGLE_GEOCODE_URL,
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("status") == "OK" and data.get("results"):
                        result = data["results"][0]
                        return {
                            "address": result.get("formatted_address"),
                            "place_id": result.get("place_id")
                        }
                        
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
        
        return None


# Singleton instance
_geocoding_service = None

def get_geocoding_service() -> GeocodingService:
    """Get or create the geocoding service singleton"""
    global _geocoding_service
    if _geocoding_service is None:
        _geocoding_service = GeocodingService()
    return _geocoding_service


async def geocode_shop_location(shop_name: str, address: str = None) -> Optional[Tuple[float, float]]:
    """Quick utility to geocode a shop and return just coordinates"""
    service = get_geocoding_service()
    result = await service.geocode_address(address, shop_name)
    if result:
        return (result["latitude"], result["longitude"])
    return None
