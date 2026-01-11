"""
Geocoding Service for Shop Location Resolution
Uses OpenStreetMap Nominatim (free) with fallback options
Optimized for South African addresses
"""

import os
import logging
import asyncio
from typing import Dict, Optional, Tuple
from functools import lru_cache
import httpx

logger = logging.getLogger(__name__)

# South Africa bounding box for better geocoding accuracy
SA_BOUNDS = {
    "viewbox": "16.3,-34.9,33.0,-22.1",  # SW to NE corners of SA
    "bounded": 1,
    "countrycodes": "za"
}

class GeocodingService:
    """
    Geocoding service to convert addresses to coordinates
    Primary: OpenStreetMap Nominatim (free, no API key)
    """
    
    def __init__(self):
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"
        self.user_agent = "RetailRewardsSA/1.0 (contact@retailrewards.co.za)"
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
        if not address:
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
        
        # Clean and prepare the address
        search_query = self._prepare_search_query(address, shop_name)
        
        try:
            result = await self._nominatim_search(search_query)
            if result:
                self._cache[cache_key] = (result["latitude"], result["longitude"])
                return result
                
            # Fallback: try with just the address
            if shop_name:
                result = await self._nominatim_search(address)
                if result:
                    self._cache[cache_key] = (result["latitude"], result["longitude"])
                    return result
                    
            # Fallback: try to extract suburb/city and geocode that
            simplified = self._extract_location_hint(address)
            if simplified and simplified != address:
                result = await self._nominatim_search(simplified)
                if result:
                    result["confidence"] = "low"  # Less precise
                    self._cache[cache_key] = (result["latitude"], result["longitude"])
                    return result
                    
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            
        return None
    
    def _prepare_search_query(self, address: str, shop_name: str = None) -> str:
        """Prepare address for geocoding"""
        # Common SA address abbreviations
        replacements = {
            "Cnr": "Corner",
            "Cnr.": "Corner",
            "St.": "Street",
            "St": "Street",
            "Rd": "Road",
            "Rd.": "Road",
            "Ave": "Avenue",
            "Ave.": "Avenue",
            "Blvd": "Boulevard",
            "Dr": "Drive",
            "Dr.": "Drive",
        }
        
        query = address
        for abbr, full in replacements.items():
            query = query.replace(f" {abbr} ", f" {full} ")
            query = query.replace(f" {abbr},", f" {full},")
        
        # Add South Africa if not present
        if "south africa" not in query.lower() and "sa" not in query.lower():
            query = f"{query}, South Africa"
            
        # Optionally prepend shop name for better matching
        if shop_name and shop_name.lower() not in query.lower():
            # Don't prepend generic names
            generic_names = ["shoprite", "checkers", "pick n pay", "woolworths", "spar"]
            if shop_name.lower() not in generic_names:
                query = f"{shop_name}, {query}"
                
        return query
    
    def _extract_location_hint(self, address: str) -> Optional[str]:
        """Extract suburb/city from address for fallback geocoding"""
        # Common SA cities/areas
        sa_locations = [
            "johannesburg", "cape town", "durban", "pretoria", "port elizabeth",
            "bloemfontein", "east london", "nelspruit", "polokwane", "kimberley",
            "sandton", "rosebank", "midrand", "centurion", "randburg", "fourways",
            "brackenfell", "bellville", "stellenbosch", "paarl", "somerset west",
            "umhlanga", "ballito", "pinetown", "westville", "hillcrest",
            "soweto", "alexandra", "tembisa", "khayelitsha", "mitchells plain",
            "waterfront", "v&a", "melrose", "menlyn", "gateway"
        ]
        
        address_lower = address.lower()
        for location in sa_locations:
            if location in address_lower:
                return f"{location}, South Africa"
                
        return None
    
    async def _nominatim_search(self, query: str) -> Optional[Dict]:
        """Search using OpenStreetMap Nominatim"""
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
            **SA_BOUNDS
        }
        
        headers = {
            "User-Agent": self.user_agent
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.nominatim_url,
                    params=params,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    results = response.json()
                    if results and len(results) > 0:
                        result = results[0]
                        return {
                            "latitude": float(result["lat"]),
                            "longitude": float(result["lon"]),
                            "formatted_address": result.get("display_name", query),
                            "source": "nominatim",
                            "confidence": "high" if float(result.get("importance", 0)) > 0.3 else "medium",
                            "place_type": result.get("type"),
                            "osm_id": result.get("osm_id")
                        }
                else:
                    logger.warning(f"Nominatim returned {response.status_code}")
                    
        except httpx.TimeoutException:
            logger.warning("Nominatim request timed out")
        except Exception as e:
            logger.error(f"Nominatim error: {e}")
            
        return None
    
    async def geocode_shop(self, shop_name: str, address: str = None, receipt_text: str = None) -> Optional[Dict]:
        """
        Geocode a shop from available information
        
        Args:
            shop_name: Name of the shop (e.g., "Shoprite")
            address: Extracted address if available
            receipt_text: Raw receipt text for additional context
        """
        # Try with address first
        if address:
            result = await self.geocode_address(address, shop_name)
            if result:
                return result
        
        # Try to extract address from receipt text
        if receipt_text:
            # Look for address patterns in receipt
            import re
            
            # Common patterns in SA receipts
            patterns = [
                r'(?:Cnr|Corner|Cor)\s+[A-Za-z\s]+(?:&|and)\s+[A-Za-z\s]+(?:Rd|Road|St|Street|Ave)',
                r'\d+\s+[A-Za-z\s]+(?:Road|Street|Avenue|Drive|Rd|St|Ave|Dr)',
                r'[A-Za-z\s]+(?:Mall|Centre|Center|Shopping)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, receipt_text, re.IGNORECASE)
                if match:
                    extracted_address = match.group(0)
                    result = await self.geocode_address(extracted_address, shop_name)
                    if result:
                        result["address_extracted_from"] = "receipt_text"
                        return result
        
        # Last resort: try just the shop name with SA
        if shop_name:
            result = await self._nominatim_search(f"{shop_name}, South Africa")
            if result:
                result["confidence"] = "very_low"
                result["note"] = "Geocoded from shop name only"
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
    
    Returns:
        Tuple of (latitude, longitude) or None
    """
    service = get_geocoding_service()
    result = await service.geocode_address(address, shop_name)
    if result:
        return (result["latitude"], result["longitude"])
    return None
