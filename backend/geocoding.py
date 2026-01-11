"""
Geocoding Service for Shop Location Resolution
Primary: Google Maps Geocoding API (accurate, good SA coverage)
Fallback: Local SA database for offline/rate-limited scenarios
"""

import os
import logging
import asyncio
from typing import Dict, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Fallback: Pre-defined coordinates for major SA locations
SA_LOCATIONS = {
    "brackenfell": {"lat": -33.8789, "lon": 18.6989},
    "bellville": {"lat": -33.9017, "lon": 18.6291},
    "sandton": {"lat": -26.1076, "lon": 28.0567},
    "rosebank": {"lat": -26.1452, "lon": 28.0445},
    "soweto": {"lat": -26.2485, "lon": 27.8540},
    "cape town": {"lat": -33.9249, "lon": 18.4241},
    "johannesburg": {"lat": -26.2041, "lon": 28.0473},
    "durban": {"lat": -29.8587, "lon": 31.0218},
    "pretoria": {"lat": -25.7461, "lon": 28.1881},
    "port elizabeth": {"lat": -33.9608, "lon": 25.6022},
    "gqeberha": {"lat": -33.9608, "lon": 25.6022},  # New name for PE
    "bloemfontein": {"lat": -29.0852, "lon": 26.1596},
    "east london": {"lat": -33.0153, "lon": 27.9116},
    "polokwane": {"lat": -23.9045, "lon": 29.4688},
    "nelspruit": {"lat": -25.4753, "lon": 30.9694},
    "mbombela": {"lat": -25.4753, "lon": 30.9694},  # New name for Nelspruit
    "kimberley": {"lat": -28.7282, "lon": 24.7499},
    "rustenburg": {"lat": -25.6670, "lon": 27.2420},
    "pietermaritzburg": {"lat": -29.6006, "lon": 30.3794},
    "centurion": {"lat": -25.8603, "lon": 28.1894},
    "midrand": {"lat": -25.9891, "lon": 28.1271},
}


class GeocodingService:
    """
    Geocoding service with Google Maps as primary and local fallback
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self.google_api_key = GOOGLE_MAPS_API_KEY
        
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
                        
                        # Determine confidence based on location_type
                        location_type = result["geometry"].get("location_type", "")
                        confidence_map = {
                            "ROOFTOP": "high",
                            "RANGE_INTERPOLATED": "high",
                            "GEOMETRIC_CENTER": "medium",
                            "APPROXIMATE": "low"
                        }
                        confidence = confidence_map.get(location_type, "medium")
                        
                        logger.info(f"✅ Google geocoded: {query} -> {location['lat']}, {location['lng']} ({confidence})")
                        
                        return {
                            "latitude": location["lat"],
                            "longitude": location["lng"],
                            "formatted_address": result.get("formatted_address", query),
                            "source": "google_maps",
                            "confidence": confidence,
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
                    "note": "Approximate location from local database"
                }
        
        return None
    
    async def geocode_shop(self, shop_name: str, address: str = None, receipt_text: str = None) -> Optional[Dict]:
        """
        Geocode a shop from available information
        """
        # Try with full address first
        if address:
            result = await self.geocode_address(address, shop_name)
            if result and result.get("confidence") in ["high", "medium"]:
                return result
        
        # Try shop name + address
        if shop_name and address:
            result = await self.geocode_address(f"{shop_name}, {address}", None)
            if result:
                return result
        
        # Try just shop name (will get approximate location)
        if shop_name:
            result = await self.geocode_address(shop_name, None)
            if result:
                result["confidence"] = "low"
                result["note"] = "Geocoded from shop name only - approximate location"
                return result
        
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
