"""
Geocoding Service for Shop Location Resolution
Uses multiple providers with fallbacks
Optimized for South African addresses
"""

import os
import logging
import asyncio
from typing import Dict, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

# Pre-defined coordinates for major SA retail chains
# These are approximate central locations that will be refined when actual addresses are provided
SA_KNOWN_SHOPS = {
    # Major retailer headquarters/common locations in SA
    "shoprite": {"lat": -33.9249, "lon": 18.4241, "city": "Cape Town"},  # HQ in Cape Town
    "checkers": {"lat": -33.9249, "lon": 18.4241, "city": "Cape Town"},
    "pick n pay": {"lat": -26.1076, "lon": 28.0567, "city": "Johannesburg"},
    "woolworths": {"lat": -33.9249, "lon": 18.4241, "city": "Cape Town"},
    "spar": {"lat": -29.8587, "lon": 31.0218, "city": "Durban"},
    "game": {"lat": -26.1076, "lon": 28.0567, "city": "Johannesburg"},
    "makro": {"lat": -26.1076, "lon": 28.0567, "city": "Johannesburg"},
    "dis-chem": {"lat": -26.1076, "lon": 28.0567, "city": "Johannesburg"},
    "clicks": {"lat": -33.9249, "lon": 18.4241, "city": "Cape Town"},
}

# SA suburb/area coordinates for address matching
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
    "bloemfontein": {"lat": -29.0852, "lon": 26.1596},
    "centurion": {"lat": -25.8603, "lon": 28.1894},
    "midrand": {"lat": -25.9891, "lon": 28.1271},
    "randburg": {"lat": -26.0936, "lon": 28.0061},
    "fourways": {"lat": -26.0145, "lon": 28.0064},
    "melrose arch": {"lat": -26.1341, "lon": 28.0694},
    "v&a waterfront": {"lat": -33.9036, "lon": 18.4208},
    "gateway": {"lat": -29.7276, "lon": 31.0699},
    "umhlanga": {"lat": -29.7276, "lon": 31.0699},
    "menlyn": {"lat": -25.7823, "lon": 28.2756},
    "eastgate": {"lat": -26.1809, "lon": 28.1179},
    "cresta": {"lat": -26.1186, "lon": 27.9644},
    "clearwater": {"lat": -26.1089, "lon": 27.9089},
    "the glen": {"lat": -26.2600, "lon": 28.0511},
    "mall of africa": {"lat": -25.9891, "lon": 28.1069},
    "pavilion": {"lat": -29.8197, "lon": 30.9306},
    "canal walk": {"lat": -33.8940, "lon": 18.5117},
    "tyger valley": {"lat": -33.8725, "lon": 18.6347},
    "somerset west": {"lat": -34.0824, "lon": 18.8430},
    "stellenbosch": {"lat": -33.9321, "lon": 18.8602},
    "paarl": {"lat": -33.7244, "lon": 18.9622},
    "khayelitsha": {"lat": -34.0389, "lon": 18.6819},
    "mitchells plain": {"lat": -34.0492, "lon": 18.6181},
}


class GeocodingService:
    """
    Geocoding service to convert addresses to coordinates
    Uses local lookup for SA addresses with fallback to external APIs
    """
    
    def __init__(self):
        self._cache: Dict[str, Tuple[float, float]] = {}
        
    async def geocode_address(self, address: str, shop_name: str = None) -> Optional[Dict]:
        """
        Geocode an address to lat/long coordinates
        
        Args:
            address: Street address or location description
            shop_name: Optional shop name to help with search
            
        Returns:
            Dict with latitude, longitude, formatted_address, confidence
        """
        if not address and not shop_name:
            return None
            
        # Check cache first
        cache_key = f"{shop_name}:{address}".lower()
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return {
                "latitude": cached[0],
                "longitude": cached[1],
                "source": "cache",
                "confidence": "high"
            }
        
        # Try local SA location lookup first
        result = self._local_lookup(address, shop_name)
        if result:
            self._cache[cache_key] = (result["latitude"], result["longitude"])
            return result
        
        # Try geopy with alternative providers
        result = await self._geopy_geocode(address, shop_name)
        if result:
            self._cache[cache_key] = (result["latitude"], result["longitude"])
            return result
                    
        return None
    
    def _local_lookup(self, address: str, shop_name: str = None) -> Optional[Dict]:
        """Look up location from local SA database"""
        combined = f"{shop_name or ''} {address or ''}".lower()
        
        # Check for known suburbs/areas in the address
        for location, coords in SA_LOCATIONS.items():
            if location in combined:
                return {
                    "latitude": coords["lat"],
                    "longitude": coords["lon"],
                    "formatted_address": f"{location.title()}, South Africa",
                    "source": "local_db",
                    "confidence": "medium",
                    "matched_location": location
                }
        
        # Check for known shop chains
        if shop_name:
            shop_lower = shop_name.lower()
            for chain, coords in SA_KNOWN_SHOPS.items():
                if chain in shop_lower:
                    return {
                        "latitude": coords["lat"],
                        "longitude": coords["lon"],
                        "formatted_address": f"{shop_name}, {coords['city']}, South Africa",
                        "source": "local_db",
                        "confidence": "low",
                        "note": "Approximate location based on chain headquarters"
                    }
        
        return None
    
    async def _geopy_geocode(self, address: str, shop_name: str = None) -> Optional[Dict]:
        """Try geocoding using geopy library"""
        try:
            from geopy.geocoders import Nominatim
            from geopy.exc import GeocoderTimedOut, GeocoderServiceError
            
            geolocator = Nominatim(user_agent="RetailRewardsSA/1.0")
            
            search_query = address
            if shop_name and shop_name.lower() not in address.lower():
                search_query = f"{shop_name}, {address}"
            
            # Add South Africa if not present
            if "south africa" not in search_query.lower():
                search_query = f"{search_query}, South Africa"
            
            # Run geocoding in thread pool
            location = await asyncio.to_thread(
                geolocator.geocode,
                search_query,
                timeout=10
            )
            
            if location:
                return {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "formatted_address": location.address,
                    "source": "nominatim",
                    "confidence": "high"
                }
                
        except Exception as e:
            logger.debug(f"Geopy geocoding failed: {e}")
            
        return None

    async def geocode_shop(self, shop_name: str, address: str = None, receipt_text: str = None) -> Optional[Dict]:
        """
        Geocode a shop from available information
        """
        # Try with address first
        if address:
            result = await self.geocode_address(address, shop_name)
            if result:
                return result
        
        # Try just shop name
        if shop_name:
            result = await self.geocode_address(None, shop_name)
            if result:
                return result
                
        return None


# Singleton instance
_geocoding_service = None

def get_geocoding_service() -> GeocodingService:
    """Get or create the geocoding service singleton"""
    global _geocoding_service
    if _geocoding_service is None:
        _geocoding_service = GeocodingService()
    return _geocoding_service


# Utility function for direct use
async def geocode_shop_location(shop_name: str, address: str = None) -> Optional[Tuple[float, float]]:
    """
    Quick utility to geocode a shop and return just coordinates
    """
    service = get_geocoding_service()
    result = await service.geocode_address(address, shop_name)
    if result:
        return (result["latitude"], result["longitude"])
    return None
