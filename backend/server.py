from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import random
import base64
import json
import httpx
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import re
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Import custom modules for receipt processing
from receipt_processor import get_receipt_processor
from vector_store import get_receipt_vector_store
from whatsapp_cloud import get_whatsapp_client, parse_webhook_message, WHATSAPP_VERIFY_TOKEN
from geocoding import get_geocoding_service
from database import get_database

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Database (Supabase)
db = get_database()

# Scheduler for daily draws
scheduler = AsyncIOScheduler()

# LandingAI configuration
LANDINGAI_API_KEY = os.environ.get('LANDINGAI_API_KEY', '')

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting scheduler for daily draws...")
    scheduler.add_job(
        run_scheduled_daily_draw,
        CronTrigger(hour=0, minute=0),  # Run at midnight UTC
        id='daily_draw',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started - daily draw at midnight UTC")
    logger.info("✅ Using Supabase (PostgreSQL) database")
    yield
    # Shutdown
    scheduler.shutdown()

# Create the main app with lifespan
app = FastAPI(title="Retail Rewards Platform", lifespan=lifespan)

# Create router with /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Geocoder for reverse geocoding
geolocator = Nominatim(user_agent="retail_rewards_app")

# ============== DISTANCE & FRAUD DETECTION ==============

import math

def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two GPS coordinates using Haversine formula
    Returns distance in kilometers
    """
    if not all([lat1, lon1, lat2, lon2]):
        return None
    
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return round(R * c, 2)

def assess_fraud_risk(distance_km: float, amount: float = 0) -> dict:
    """
    Assess fraud risk based on distance between shop and upload location
    Returns fraud_flag, fraud_score, and fraud_reason
    """
    if distance_km is None:
        return {
            "fraud_flag": "review",
            "fraud_score": 30,
            "fraud_reason": "Location data incomplete - manual review required"
        }
    
    # Base scoring on distance
    if distance_km <= FRAUD_THRESHOLD_VALID:  # <50km
        return {
            "fraud_flag": "valid",
            "fraud_score": max(0, int(distance_km)),  # 0-50 score
            "fraud_reason": None
        }
    elif distance_km <= FRAUD_THRESHOLD_REVIEW:  # 50-100km
        return {
            "fraud_flag": "review",
            "fraud_score": 50 + int((distance_km - 50) * 0.5),  # 50-75 score
            "fraud_reason": f"Upload location {distance_km}km from shop - may need verification"
        }
    elif distance_km <= FRAUD_THRESHOLD_SUSPICIOUS:  # 100-200km
        return {
            "fraud_flag": "suspicious",
            "fraud_score": 75 + int((distance_km - 100) * 0.25),  # 75-100 score
            "fraud_reason": f"Upload location {distance_km}km from shop - suspicious distance"
        }
    else:  # >200km
        return {
            "fraud_flag": "flagged",
            "fraud_score": 100,
            "fraud_reason": f"Upload location {distance_km}km from shop - likely fraudulent"
        }

# ============== LANDINGAI ADE RECEIPT PROCESSING ==============

async def process_receipt_with_landingai(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    """
    Process receipt image using LandingAI ADE (Agentic Document Extraction)
    Returns extracted shop name, amount, items, and address
    """
    result = {
        "shop_name": None,
        "amount": 0.0,
        "items": [],
        "address": None,
        "raw_text": "",
        "success": False,
        "error": None
    }
    
    try:
        # Try to import landingai_ade
        try:
            from landingai_ade import ADEClient
            
            if not LANDINGAI_API_KEY:
                logger.warning("LANDINGAI_API_KEY not set, using fallback parser")
                raise ImportError("No API key")
            
            # Initialize LandingAI client
            ade_client = ADEClient(api_key=LANDINGAI_API_KEY)
            
            # Decode image
            image_bytes = base64.b64decode(image_base64)
            
            # Process with LandingAI - extract receipt data
            extraction_result = await asyncio.to_thread(
                ade_client.extract,
                image_bytes,
                document_type="receipt",
                extract_fields=["merchant_name", "total_amount", "items", "address", "date", "payment_method"]
            )
            
            # Parse LandingAI response
            if extraction_result:
                result["shop_name"] = extraction_result.get("merchant_name") or extraction_result.get("store_name")
                
                # Handle amount (could be string or number)
                amount_str = extraction_result.get("total_amount") or extraction_result.get("total") or "0"
                if isinstance(amount_str, str):
                    # Remove currency symbols and parse
                    amount_str = re.sub(r'[^\d.,]', '', amount_str).replace(',', '.')
                    result["amount"] = float(amount_str) if amount_str else 0.0
                else:
                    result["amount"] = float(amount_str)
                
                # Extract items
                items_data = extraction_result.get("items") or extraction_result.get("line_items") or []
                for item in items_data:
                    if isinstance(item, dict):
                        result["items"].append({
                            "name": item.get("name") or item.get("description", "Item"),
                            "price": float(item.get("price") or item.get("amount") or 0),
                            "quantity": int(item.get("quantity", 1))
                        })
                
                result["address"] = extraction_result.get("address") or extraction_result.get("store_address")
                result["raw_text"] = json.dumps(extraction_result)
                result["success"] = True
                
                logger.info(f"LandingAI extracted: {result['shop_name']}, ${result['amount']}, {len(result['items'])} items")
                return result
                
        except ImportError:
            logger.info("LandingAI not available, using fallback OCR")
        except Exception as e:
            logger.error(f"LandingAI error: {e}, using fallback")
        
        # Fallback: Use simple pattern matching on any OCR text provided
        # In production, you'd integrate with another OCR service here
        result["success"] = True
        result["error"] = "Using manual entry - LandingAI not configured"
        return result
        
    except Exception as e:
        logger.error(f"Receipt processing error: {e}")
        result["error"] = str(e)
        return result

async def geocode_shop_from_receipt(shop_name: str, address: str = None, postal_code: str = None) -> tuple:
    """
    Try to geocode a shop from its name, address, and/or postal code using improved geocoding service
    Returns (latitude, longitude, display_name, geocoded_address) or (None, None, shop_name, None)
    """
    try:
        geocoding_service = get_geocoding_service()
        result = await geocoding_service.geocode_shop(shop_name, address, postal_code=postal_code)
        
        if result:
            lat = result["latitude"]
            lon = result["longitude"]
            formatted = result.get("formatted_address", "")
            
            # Extract suburb/area from formatted address for display name
            display_name = shop_name
            if formatted:
                # Parse Google's formatted address to extract suburb
                # Format: "Street, Suburb, City, PostCode, South Africa"
                parts = [p.strip() for p in formatted.split(",")]
                if len(parts) >= 3:
                    # Try to find suburb (usually 2nd or 3rd part)
                    for part in parts[1:4]:
                        # Skip postal codes and "South Africa"
                        if part.isdigit() or "south africa" in part.lower():
                            continue
                        # Skip street names (contain "St", "Rd", etc.)
                        if any(x in part.lower() for x in [' st', ' rd', ' ave', ' dr', 'street', 'road']):
                            continue
                        # This is likely the suburb
                        suburb = part.strip()
                        if suburb and suburb.lower() not in shop_name.lower():
                            display_name = f"{shop_name} {suburb}"
                        break
            
            logger.info(f"Geocoded {shop_name}: {lat}, {lon} -> Display: {display_name}")
            return (lat, lon, display_name, formatted)
        else:
            logger.warning(f"Could not geocode shop: {shop_name}, {address}")
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
    
    return (None, None, shop_name, None)

# ============== SCHEDULED DRAW FUNCTION ==============

async def run_scheduled_daily_draw():
    """Run the daily draw at midnight - called by scheduler"""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info(f"Running scheduled daily draw for {today}")
        
        # Check if draw already completed
        existing = await db.draws_find_one({"draw_date": today, "status": "completed"})
        if existing:
            logger.info(f"Draw already completed for {today}")
            return
        
        # Get all receipts for today
        start = f"{today}T00:00:00"
        end = f"{today}T23:59:59"
        
        receipts = await db.receipts_find({
            "created_at": {"$gte": start, "$lte": end},
            "status": {"$ne": "won"},
            "fraud_flag": "valid"
        }, limit=10000)
        
        if not receipts:
            logger.info(f"No receipts for draw on {today}")
            return
        
        # Random selection
        winner_receipt = random.choice(receipts)
        prize_amount = winner_receipt["amount"]
        
        # Create draw record
        draw_id = str(uuid.uuid4())
        draw_dict = {
            "id": draw_id,
            "draw_date": today,
            "total_receipts": len(receipts),
            "total_amount": sum(float(r.get("amount", 0) or 0) for r in receipts),
            "winner_receipt_id": winner_receipt["id"],
            "winner_customer_id": winner_receipt["customer_id"],
            "winner_customer_phone": winner_receipt["customer_phone"],
            "prize_amount": prize_amount,
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.draws_insert_one(draw_dict)
        
        # Update receipt status
        await db.receipts_update_one(
            {"id": winner_receipt["id"]},
            {"$set": {"status": "won"}}
        )
        
        # Update customer stats
        await db.customers_update_one(
            {"id": winner_receipt["customer_id"]},
            {"$inc": {"total_wins": 1, "total_winnings": prize_amount}}
        )
        
        logger.info(f"Draw completed! Winner: {winner_receipt['customer_phone']}, Prize: R{prize_amount}")
        
        # Notify winner via WhatsApp Cloud API
        try:
            wa = get_whatsapp_client()
            await wa.send_winner_notification(
                winner_receipt["customer_phone"],
                prize_amount,
                today
            )
            logger.info(f"Winner notification sent to {winner_receipt['customer_phone']}")
        except Exception as e:
            logger.error(f"Failed to notify winner: {e}")
        
    except Exception as e:
        logger.error(f"Scheduled draw error: {e}")

# ============== MODELS ==============

class CustomerCreate(BaseModel):
    phone_number: str
    name: Optional[str] = None

class Customer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phone_number: str
    name: Optional[str] = None
    total_receipts: int = 0
    total_spent: float = 0.0
    total_wins: int = 0
    total_winnings: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Shop(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    receipt_count: int = 0
    total_sales: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Receipt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    customer_phone: str
    shop_id: Optional[str] = None
    shop_name: Optional[str] = None
    amount: float = 0.0
    currency: str = "ZAR"
    items: List[Dict[str, Any]] = []
    raw_text: Optional[str] = None
    image_data: Optional[str] = None  # Base64 encoded
    # Customer location when uploading
    upload_latitude: Optional[float] = None
    upload_longitude: Optional[float] = None
    upload_address: Optional[str] = None
    # Shop location extracted from receipt
    shop_latitude: Optional[float] = None
    shop_longitude: Optional[float] = None
    shop_address: Optional[str] = None
    # Fraud detection
    distance_km: Optional[float] = None  # Distance between shop and upload location
    fraud_flag: str = "valid"  # valid, review, suspicious, flagged
    fraud_score: int = 0  # 0-100, higher = more suspicious
    fraud_reason: Optional[str] = None
    # Status
    status: str = "pending"  # pending, processed, won, rejected
    processing_error: Optional[str] = None
    receipt_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Fraud detection thresholds (in km)
FRAUD_THRESHOLD_VALID = 50  # <50km = valid
FRAUD_THRESHOLD_REVIEW = 100  # 50-100km = review
FRAUD_THRESHOLD_SUSPICIOUS = 200  # 100-200km = suspicious
# >200km = flagged

class Draw(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    draw_date: str  # YYYY-MM-DD
    total_receipts: int = 0
    total_amount: float = 0.0
    winner_receipt_id: Optional[str] = None
    winner_customer_id: Optional[str] = None
    winner_customer_phone: Optional[str] = None
    prize_amount: float = 0.0
    status: str = "pending"  # pending, completed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== HELPER FUNCTIONS ==============

async def get_or_create_customer(phone_number: str, name: Optional[str] = None) -> dict:
    """Get existing customer or create new one"""
    customer = await db.customers_find_one({"phone_number": phone_number})
    if not customer:
        customer_obj = Customer(phone_number=phone_number, name=name)
        customer = customer_obj.model_dump()
        customer['created_at'] = customer['created_at'].isoformat()
        customer = await db.customers_insert_one(customer)
    return customer

async def get_or_create_shop(shop_name: str, address: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> dict:
    """Get existing shop or create new one"""
    # Try to find by name (case insensitive)
    shop = await db.shops_find_one({"name": {"$regex": f"^{re.escape(shop_name)}$", "$options": "i"}})
    if not shop:
        shop_obj = Shop(name=shop_name, address=address, latitude=lat, longitude=lon)
        shop = shop_obj.model_dump()
        shop['created_at'] = shop['created_at'].isoformat()
        shop = await db.shops_insert_one(shop)
    return shop

def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Get address from coordinates"""
    try:
        location = geolocator.reverse(f"{lat}, {lon}", timeout=10)
        return location.address if location else None
    except (GeocoderTimedOut, Exception) as e:
        logger.error(f"Geocoding error: {e}")
        return None

def parse_receipt_text(text: str) -> dict:
    """Parse receipt text to extract shop name, amount, items"""
    lines = text.strip().split('\n')
    result = {
        "shop_name": None,
        "amount": 0.0,
        "items": [],
        "date": None,
        "address": None
    }
    
    # First non-empty line is usually shop name
    for line in lines:
        if line.strip():
            result["shop_name"] = line.strip()
            break
    
    # Find total amount (look for patterns like TOTAL, Total, $XX.XX)
    amount_patterns = [
        r'(?:TOTAL|Total|GRAND TOTAL|Amount Due|AMOUNT|Balance Due)[:\s]*[\$]?(\d+[.,]\d{2})',
        r'[\$](\d+[.,]\d{2})\s*$',
        r'(\d+[.,]\d{2})\s*(?:USD|EUR|GBP)?$'
    ]
    
    for line in reversed(lines):
        for pattern in amount_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '.')
                result["amount"] = float(amount_str)
                break
        if result["amount"] > 0:
            break
    
    # Extract items (lines with prices)
    item_pattern = r'^(.+?)\s+[\$]?(\d+[.,]\d{2})$'
    for line in lines:
        match = re.match(item_pattern, line.strip())
        if match:
            item_name = match.group(1).strip()
            item_price = float(match.group(2).replace(',', '.'))
            if item_name.upper() not in ['TOTAL', 'SUBTOTAL', 'TAX', 'CASH', 'CHANGE']:
                result["items"].append({"name": item_name, "price": item_price})
    
    # Find date
    date_patterns = [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})'
    ]
    for line in lines:
        for pattern in date_patterns:
            match = re.search(pattern, line)
            if match:
                result["date"] = match.group(1)
                break
    
    # Find address (lines with common address keywords)
    address_keywords = ['street', 'st.', 'ave', 'road', 'rd.', 'blvd', 'suite', 'floor']
    for line in lines[1:6]:  # Check first few lines after shop name
        if any(kw in line.lower() for kw in address_keywords):
            result["address"] = line.strip()
            break
    
    return result

# ============== API ENDPOINTS ==============

@api_router.get("/")
async def root():
    return {"message": "Retail Rewards Platform API", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# --- Customer Endpoints ---

@api_router.post("/customers", response_model=dict)
async def create_customer(data: CustomerCreate):
    customer = await get_or_create_customer(data.phone_number, data.name)
    return customer

@api_router.get("/customers/{phone_number}")
async def get_customer(phone_number: str):
    customer = await db.customers_find_one({"phone_number": phone_number})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@api_router.get("/customers")
async def list_customers(skip: int = 0, limit: int = 50):
    customers = await db.customers_find({}, skip=skip, limit=limit)
    total = await db.customers_count({})
    return {"customers": customers, "total": total}

@api_router.post("/customers/location")
async def update_customer_location(data: dict):
    """Update customer's last known location"""
    phone_number = data.get("phone_number")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    
    if phone_number and latitude and longitude:
        await db.customers_update_one(
            {"phone_number": phone_number},
            {"$set": {
                "last_latitude": latitude,
                "last_longitude": longitude,
                "location_updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    return {"success": True}

# --- Receipt Endpoints ---

class ReceiptImageRequest(BaseModel):
    phone_number: str
    image_data: str  # Base64 encoded
    mime_type: str = "image/jpeg"
    latitude: Optional[float] = None
    longitude: Optional[float] = None

@api_router.post("/receipts/process-image")
async def process_receipt_image(request: ReceiptImageRequest):
    """
    Process a receipt image from WhatsApp using LandingAI ADE
    This is the main endpoint called by the WhatsApp service
    """
    try:
        # Get or create customer
        customer = await get_or_create_customer(request.phone_number)
        
        # Process image with LandingAI ADE (proper implementation)
        processor = get_receipt_processor()
        extracted = processor.process_receipt_image(request.image_data, request.mime_type)
        
        if not extracted["success"] and extracted.get("error") and "manual entry" not in extracted["error"].lower():
            return {"success": False, "error": extracted["error"]}
        
        # Get upload location address
        upload_address = None
        if request.latitude and request.longitude:
            upload_address = reverse_geocode(request.latitude, request.longitude)
        
        # Try to geocode shop if we have a name
        shop_lat, shop_lon = None, None
        shop_display_name = extracted.get("shop_name")
        shop_name = extracted.get("shop_name")
        shop_address = extracted.get("shop_address")
        postal_code = extracted.get("postal_code")  # Get postal code from OCR
        geocoded_address = None
        
        if shop_name:
            # Pass postal code to geocoding for better accuracy
            shop_lat, shop_lon, shop_display_name, geocoded_address = await geocode_shop_from_receipt(
                shop_name, 
                shop_address,
                postal_code=postal_code
            )
        
        # Use geocoded address if OCR address is missing or looks like garbage
        # (garbage = contains "logo", "font", "background", etc.)
        if geocoded_address:
            if not shop_address or any(word in shop_address.lower() for word in ['logo', 'font', 'background', 'features', 'distressed']):
                shop_address = geocoded_address
                logger.info(f"Using geocoded address: {geocoded_address}")
        
        # Note: Do NOT fallback to upload location for shop
        # We need separate locations for fraud detection
        
        # Get or create shop with display name (e.g., "Shoprite Brackenfell")
        shop = None
        if shop_display_name:
            shop = await get_or_create_shop(shop_display_name, shop_address, shop_lat, shop_lon)
            # Update shop stats
            await db.shops_update_one(
                {"id": shop["id"]},
                {"$inc": {"receipt_count": 1, "total_sales": extracted.get("amount", 0)}}
            )
        
        # Calculate distance between shop and upload location for fraud detection
        distance_km = None
        if shop_lat and shop_lon and request.latitude and request.longitude:
            distance_km = calculate_distance_km(shop_lat, shop_lon, request.latitude, request.longitude)
        
        # Assess fraud risk
        fraud_assessment = assess_fraud_risk(distance_km, extracted.get("amount", 0))
        
        # Determine which image to store (prefer converted JPEG for display)
        image_to_store = extracted.get("converted_image") or request.image_data
        
        # Determine receipt status based on fraud flag
        receipt_status = "processed"
        if fraud_assessment["fraud_flag"] == "flagged":
            receipt_status = "review"  # Flagged receipts need manual review before entering draw
        
        # Create receipt record with fraud data
        receipt = Receipt(
            customer_id=customer["id"],
            customer_phone=request.phone_number,
            shop_id=shop["id"] if shop else None,
            shop_name=shop_display_name,  # Use display name like "Shoprite Brackenfell"
            amount=extracted.get("amount", 0),
            currency="ZAR",
            items=extracted.get("items", []),
            raw_text=extracted.get("raw_text"),
            image_data=image_to_store,  # Store the converted JPEG if available
            upload_latitude=request.latitude,
            upload_longitude=request.longitude,
            upload_address=upload_address,
            shop_latitude=shop_lat,
            shop_longitude=shop_lon,
            shop_address=shop_address or (shop.get("address") if shop else None),
            distance_km=distance_km,
            fraud_flag=fraud_assessment["fraud_flag"],
            fraud_score=fraud_assessment["fraud_score"],
            fraud_reason=fraud_assessment["fraud_reason"],
            status=receipt_status
        )
        
        receipt_dict = receipt.model_dump()
        receipt_dict['created_at'] = receipt_dict['created_at'].isoformat()
        if receipt_dict.get('receipt_date'):
            receipt_dict['receipt_date'] = receipt_dict['receipt_date'].isoformat()
        
        # Store grounding data from LandingAI
        receipt_dict['grounding'] = extracted.get('grounding', {})
        receipt_dict['chunks'] = extracted.get('chunks', [])
        
        await db.receipts_insert_one(receipt_dict.copy())
        
        # Add to vector store for semantic search
        try:
            vector_store = get_receipt_vector_store()
            vector_store.add_receipt(receipt.id, {
                "shop_name": shop_name,
                "shop_address": shop_address,
                "amount": extracted.get("amount", 0),
                "items": extracted.get("items", []),
                "raw_text": extracted.get("raw_text", ""),
                "customer_phone": request.phone_number,
                "customer_id": customer["id"],
                "fraud_flag": fraud_assessment["fraud_flag"],
                "distance_km": distance_km,
                "grounding": extracted.get('grounding', {}),
                "created_at": receipt_dict['created_at']
            })
        except Exception as ve:
            logger.warning(f"Vector store indexing failed: {ve}")
        
        # Update customer stats
        await db.customers_update_one(
            {"id": customer["id"]},
            {"$inc": {"total_receipts": 1, "total_spent": extracted.get("amount", 0)}}
        )
        
        # Return response (exclude image data)
        response_receipt = {k: v for k, v in receipt_dict.items() if k not in ['image_data', '_id', 'chunks']}
        
        return {
            "success": True,
            "receipt": response_receipt,
            "extraction": {
                "shop_name": shop_name,
                "amount": extracted.get("amount", 0),
                "items_count": len(extracted.get("items", [])),
                "address_found": bool(shop_address),
                "has_grounding": bool(extracted.get('grounding'))
            }
        }
        
    except Exception as e:
        logger.error(f"Receipt processing error: {e}")
        return {"success": False, "error": str(e)}

@api_router.post("/receipts/upload")
async def upload_receipt(
    background_tasks: BackgroundTasks,
    phone_number: str = Form(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    image: Optional[UploadFile] = File(None),
    receipt_text: Optional[str] = Form(None),
    amount: Optional[float] = Form(None),
    shop_name: Optional[str] = Form(None)
):
    """Upload a receipt image or text with geolocation"""
    
    # Get or create customer
    customer = await get_or_create_customer(phone_number)
    
    # Process image if provided
    image_data = None
    if image:
        content = await image.read()
        image_data = base64.b64encode(content).decode('utf-8')
    
    # Get upload address from coordinates
    upload_address = None
    if latitude and longitude:
        upload_address = reverse_geocode(latitude, longitude)
    
    # Parse receipt text if provided
    parsed_data = {"shop_name": shop_name, "amount": amount or 0.0, "items": [], "address": None}
    if receipt_text:
        parsed_data = parse_receipt_text(receipt_text)
        if shop_name:
            parsed_data["shop_name"] = shop_name
        if amount:
            parsed_data["amount"] = amount
    
    # Get or create shop
    shop = None
    if parsed_data["shop_name"]:
        shop = await get_or_create_shop(
            parsed_data["shop_name"],
            parsed_data.get("address"),
            latitude,  # Use upload location as shop location if not known
            longitude
        )
        # Update shop stats
        await db.shops_update_one(
            {"id": shop["id"]},
            {"$inc": {"receipt_count": 1, "total_sales": parsed_data["amount"]}}
        )
    
    # Create receipt
    receipt = Receipt(
        customer_id=customer["id"],
        customer_phone=phone_number,
        shop_id=shop["id"] if shop else None,
        shop_name=parsed_data["shop_name"],
        amount=parsed_data["amount"],
        items=parsed_data["items"],
        raw_text=receipt_text,
        image_data=image_data,
        upload_latitude=latitude,
        upload_longitude=longitude,
        upload_address=upload_address,
        shop_latitude=shop.get("latitude") if shop else latitude,
        shop_longitude=shop.get("longitude") if shop else longitude,
        shop_address=parsed_data.get("address") or (shop.get("address") if shop else None),
        status="processed"
    )
    
    receipt_dict = receipt.model_dump()
    receipt_dict['created_at'] = receipt_dict['created_at'].isoformat()
    if receipt_dict.get('receipt_date'):
        receipt_dict['receipt_date'] = receipt_dict['receipt_date'].isoformat()
    
    await db.receipts_insert_one(receipt_dict.copy())  # Use copy to prevent _id mutation
    
    # Update customer stats
    await db.customers_update_one(
        {"id": customer["id"]},
        {"$inc": {"total_receipts": 1, "total_spent": parsed_data["amount"]}}
    )
    
    # Send WhatsApp confirmation in background (non-blocking)
    async def send_whatsapp_confirmation():
        try:
            wa = get_whatsapp_client()
            await wa.send_receipt_confirmation(
                phone_number,
                parsed_data["shop_name"] or "Unknown Shop",
                parsed_data["amount"],
                len(parsed_data["items"]),
                "valid"  # Web uploads are auto-approved
            )
            logger.info(f"WhatsApp confirmation sent to {phone_number}")
        except Exception as e:
            logger.warning(f"Failed to send WhatsApp confirmation: {e}")
    
    # Run WhatsApp notification in background
    background_tasks.add_task(send_whatsapp_confirmation)
    
    # Remove image_data and any _id from response
    response_receipt = {k: v for k, v in receipt_dict.items() if k not in ['image_data', '_id']}
    response_receipt['has_image'] = image_data is not None
    
    return {"success": True, "receipt": response_receipt}

@api_router.get("/receipts/customer/{phone_number}")
async def get_customer_receipts(phone_number: str, skip: int = 0, limit: int = 50):
    receipts = await db.receipts_find(
        {"customer_phone": phone_number},
        sort=("created_at", -1),
        skip=skip, 
        limit=limit
    )
    total = await db.receipts_count({"customer_phone": phone_number})
    return {"receipts": receipts, "total": total}

@api_router.get("/receipts/{receipt_id}")
async def get_receipt(receipt_id: str):
    receipt = await db.receipts_find_one({"id": receipt_id})
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt

@api_router.get("/receipts/{receipt_id}/full")
async def get_receipt_full(receipt_id: str):
    """Get full receipt details including image data and all items"""
    receipt = await db.receipts_find_one({"id": receipt_id})
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    # Get customer info
    customer = await db.customers_find_one(
        {"phone_number": receipt.get("customer_phone")}
    )
    
    # Get shop info
    shop = await db.shops_find_one(
        {"id": receipt.get("shop_id")}
    )
    
    return {
        "receipt": receipt,
        "customer": customer,
        "shop": shop
    }

@api_router.get("/receipts")
async def list_receipts(
    skip: int = 0, 
    limit: int = 50,
    date: Optional[str] = None,  # YYYY-MM-DD
    status: Optional[str] = None,
    fraud_flag: Optional[str] = None  # valid, review, suspicious, flagged
):
    query = {}
    if date:
        start = datetime.fromisoformat(f"{date}T00:00:00+00:00")
        end = datetime.fromisoformat(f"{date}T23:59:59+00:00")
        query["created_at"] = {"$gte": start.isoformat(), "$lte": end.isoformat()}
    if status:
        query["status"] = status
    if fraud_flag:
        query["fraud_flag"] = fraud_flag
    
    # Get receipts using new API
    receipts = await db.receipts_find(query, sort=("created_at", -1), skip=skip, limit=limit)
    
    total = await db.receipts_count(query)
    return {"receipts": receipts, "total": total}

# --- Semantic Search Endpoints ---

class SearchQuery(BaseModel):
    query: str
    customer_phone: Optional[str] = None
    shop_name: Optional[str] = None
    limit: int = 10

@api_router.post("/receipts/search")
async def search_receipts_semantic(search: SearchQuery):
    """
    Semantic search for receipts using vector store
    Examples: "milk purchases", "Woolworths receipts", "snacks in December"
    """
    try:
        vector_store = get_receipt_vector_store()
        results = vector_store.search_receipts(
            query=search.query,
            customer_phone=search.customer_phone,
            shop_name=search.shop_name,
            limit=search.limit
        )
        return {"results": results, "total": len(results), "query": search.query}
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {"results": [], "total": 0, "error": str(e)}

@api_router.get("/vector-store/stats")
async def get_vector_store_stats():
    """Get vector store statistics"""
    try:
        vector_store = get_receipt_vector_store()
        return vector_store.get_stats()
    except Exception as e:
        return {"available": False, "error": str(e)}

# --- Fraud Detection Endpoints ---

@api_router.get("/fraud/flagged")
async def get_flagged_receipts(skip: int = 0, limit: int = 50):
    """Get all receipts flagged for review or suspicious activity"""
    query = {"fraud_flag": {"$in": ["review", "suspicious", "flagged"]}}
    
    # Get receipts using new API
    receipts = await db.receipts_find(query, sort=("fraud_score", -1), skip=skip, limit=limit)
    
    total = await db.receipts_count(query)
    return {"receipts": receipts, "total": total}

@api_router.get("/fraud/stats")
async def get_fraud_stats():
    """Get fraud detection statistics"""
    total = await db.receipts_count({})
    valid = await db.receipts_count({"fraud_flag": "valid"})
    review = await db.receipts_count({"fraud_flag": "review"})
    suspicious = await db.receipts_count({"fraud_flag": "suspicious"})
    flagged = await db.receipts_count({"fraud_flag": "flagged"})
    
    return {
        "total_receipts": total,
        "valid": valid,
        "review": review,
        "suspicious": suspicious,
        "flagged": flagged,
        "fraud_rate": round((review + suspicious + flagged) / total * 100, 2) if total > 0 else 0
    }

@api_router.post("/fraud/review/{receipt_id}")
async def review_receipt(receipt_id: str, action: str, reason: Optional[str] = None):
    """Admin action on flagged receipt: approve, reject"""
    receipt = await db.receipts_find_one({"id": receipt_id})
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    if action == "approve":
        await db.receipts_update_one(
            {"id": receipt_id},
            {"$set": {
                "fraud_flag": "valid",
                "status": "processed",
                "fraud_reason": f"Manually approved: {reason}" if reason else "Manually approved by admin"
            }}
        )
        return {"success": True, "message": "Receipt approved and added to draw pool"}
    
    elif action == "reject":
        await db.receipts_update_one(
            {"id": receipt_id},
            {"$set": {
                "status": "rejected",
                "fraud_reason": f"Rejected: {reason}" if reason else "Rejected by admin - suspected fraud"
            }}
        )
        # Rollback customer stats
        await db.customers_update_one(
            {"id": receipt["customer_id"]},
            {"$inc": {"total_receipts": -1, "total_spent": -receipt["amount"]}}
        )
        return {"success": True, "message": "Receipt rejected and removed from draw pool"}
    
    else:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

@api_router.get("/fraud/thresholds")
async def get_fraud_thresholds():
    """Get current fraud detection thresholds"""
    return {
        "valid_km": FRAUD_THRESHOLD_VALID,
        "review_km": FRAUD_THRESHOLD_REVIEW,
        "suspicious_km": FRAUD_THRESHOLD_SUSPICIOUS,
        "description": {
            "valid": f"< {FRAUD_THRESHOLD_VALID}km - Auto-approved",
            "review": f"{FRAUD_THRESHOLD_VALID}-{FRAUD_THRESHOLD_REVIEW}km - Manual review suggested",
            "suspicious": f"{FRAUD_THRESHOLD_REVIEW}-{FRAUD_THRESHOLD_SUSPICIOUS}km - Suspicious, needs review",
            "flagged": f"> {FRAUD_THRESHOLD_SUSPICIOUS}km - Likely fraud, blocked from draw"
        }
    }

# --- Shop Endpoints ---

@api_router.get("/shops")
async def list_shops(skip: int = 0, limit: int = 100):
    shops = await db.shops_find({}, sort=("receipt_count", -1), skip=skip, limit=limit)
    total = await db.shops_count({})
    return {"shops": shops, "total": total}

@api_router.get("/shops/{shop_id}")
async def get_shop(shop_id: str):
    shop = await db.shops_find_one({"id": shop_id})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop

# --- Draw Endpoints ---

@api_router.post("/draws/run")
async def run_daily_draw(draw_date: Optional[str] = None):
    """Run daily draw for a specific date (defaults to today)"""
    if not draw_date:
        draw_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Check if draw already completed for this date
    existing_draw = await db.draws_find_one({"draw_date": draw_date, "status": "completed"})
    if existing_draw:
        return {"success": False, "message": "Draw already completed for this date", "draw": existing_draw}
    
    # Get all receipts for this date
    start = f"{draw_date}T00:00:00"
    end = f"{draw_date}T23:59:59"
    
    receipts = await db.receipts_find({
        "created_at": {"$gte": start, "$lte": end},
        "status": {"$ne": "won"},
        "fraud_flag": "valid"
    }, limit=10000)
    
    if not receipts:
        return {"success": False, "message": "No eligible receipts for this date"}
    
    # Random selection - one receipt wins
    winner_receipt = random.choice(receipts)
    prize_amount = float(winner_receipt.get("amount", 0) or 0)
    
    # Create draw record
    draw = Draw(
        draw_date=draw_date,
        total_receipts=len(receipts),
        total_amount=sum(float(r.get("amount", 0) or 0) for r in receipts),
        winner_receipt_id=winner_receipt["id"],
        winner_customer_id=winner_receipt["customer_id"],
        winner_customer_phone=winner_receipt["customer_phone"],
        prize_amount=prize_amount,
        status="completed"
    )
    
    draw_dict = draw.model_dump()
    draw_dict['created_at'] = draw_dict['created_at'].isoformat()
    await db.draws_insert_one(draw_dict)
    
    # Update receipt status
    await db.receipts_update_one(
        {"id": winner_receipt["id"]},
        {"$set": {"status": "won"}}
    )
    
    # Update customer stats
    await db.customers_update_one(
        {"id": winner_receipt["customer_id"]},
        {"$inc": {"total_wins": 1, "total_winnings": prize_amount}}
    )
    
    # Remove any _id that might have been added
    draw_response = {k: v for k, v in draw_dict.items() if k != '_id'}
    
    # Notify winner via WhatsApp Cloud API (async, don't block response)
    async def notify_winner():
        try:
            wa = get_whatsapp_client()
            await wa.send_winner_notification(
                winner_receipt["customer_phone"],
                prize_amount,
                draw_date
            )
            logger.info(f"Winner notification sent to {winner_receipt['customer_phone']}")
        except Exception as e:
            logger.error(f"Failed to notify winner via WhatsApp: {e}")
    
    # Run notification in background
    asyncio.create_task(notify_winner())
    
    return {
        "success": True,
        "draw": draw_response,
        "winner": {
            "phone": winner_receipt["customer_phone"],
            "receipt_id": winner_receipt["id"],
            "amount": prize_amount,
            "shop": winner_receipt.get("shop_name")
        }
    }

@api_router.get("/draws")
async def list_draws(skip: int = 0, limit: int = 30):
    draws = await db.draws_find({}, sort=("draw_date", -1), skip=skip, limit=limit)
    total = await db.draws_count({})
    return {"draws": draws, "total": total}

@api_router.get("/draws/{draw_date}")
async def get_draw(draw_date: str):
    draw = await db.draws_find_one({"draw_date": draw_date})
    if not draw:
        raise HTTPException(status_code=404, detail="Draw not found")
    return draw

@api_router.get("/draws/winner/{phone_number}")
async def get_customer_wins(phone_number: str):
    wins = await db.draws_find(
        {"winner_customer_phone": phone_number},
        sort=("draw_date", -1),
        limit=100
    )
    return {"wins": wins, "total": len(wins)}

# --- Map Data Endpoints ---

@api_router.get("/map/shops")
async def get_map_shops():
    """Get all shops with coordinates for map display"""
    shops = await db.shops_find(
        {"latitude": {"$ne": None, "$exists": True}},
        limit=1000
    )
    return {"shops": shops}

@api_router.get("/map/receipts")
async def get_map_receipts(date: Optional[str] = None):
    """Get receipt upload locations for map display"""
    query = {"upload_latitude": {"$ne": None}}
    if date:
        query["created_at"] = {"$gte": f"{date}T00:00:00", "$lte": f"{date}T23:59:59"}
    
    receipts = await db.receipts_find(query, limit=1000)
    return {"receipts": receipts}

# --- Analytics Endpoints ---

@api_router.get("/analytics/overview")
async def get_analytics_overview():
    """Get overall platform statistics"""
    total_customers = await db.customers_count({})
    total_receipts = await db.receipts_count({})
    total_shops = await db.shops_count({})
    total_draws = await db.draws_count({"status": "completed"})
    
    # Total spent and winnings - using aggregation
    total_spent = await db.customers_aggregate_sum('total_spent')
    total_winnings = await db.customers_aggregate_sum('total_winnings')
    
    return {
        "total_customers": total_customers,
        "total_receipts": total_receipts,
        "total_shops": total_shops,
        "total_draws": total_draws,
        "total_spent": total_spent,
        "total_winnings": total_winnings
    }

@api_router.get("/analytics/spending-by-day")
async def get_spending_by_day(days: int = 30):
    """Get daily spending for the last N days"""
    # Use the daily_spending view
    data = await db.get_daily_spending(days)
    return {"data": [{"date": r.get("date"), "amount": r.get("total_amount", 0), "receipts": r.get("receipt_count", 0)} for r in data]}

@api_router.get("/analytics/popular-shops")
async def get_popular_shops(limit: int = 10):
    """Get most popular shops by receipt count"""
    shops = await db.shops_find({}, sort=("receipt_count", -1), limit=limit)
    return {"shops": shops}

@api_router.get("/analytics/top-spenders")
async def get_top_spenders(limit: int = 10):
    """Get top spending customers"""
    customers = await db.customers_find({}, sort=("total_spent", -1), limit=limit)
    return {"customers": customers}

@api_router.get("/analytics/receipts-by-hour")
async def get_receipts_by_hour():
    """Get receipt count by hour of day"""
    data = await db.get_hourly_distribution()
    hour_data = {int(r.get("hour", 0)): int(r.get("receipt_count", 0)) for r in data}
    return {"data": [{"hour": h, "count": hour_data.get(h, 0)} for h in range(24)]}

@api_router.get("/analytics/spending-by-shop")
async def get_spending_by_shop(limit: int = 10):
    """Get total spending by shop"""
    shops = await db.shops_find({}, sort=("total_sales", -1), limit=limit)
    return {"data": [{"shop": s.get("name"), "total_spent": float(s.get("total_sales", 0) or 0), "receipt_count": s.get("receipt_count", 0)} for s in shops]}

# ============== GEOCODING ENDPOINTS ==============

@api_router.post("/geocode/shop/{shop_id}")
async def geocode_single_shop(shop_id: str):
    """Geocode a single shop by its ID"""
    shop = await db.shops_find_one({"id": shop_id})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    geocoding_service = get_geocoding_service()
    result = await geocoding_service.geocode_shop(shop["name"], shop.get("address"))
    
    if result:
        await db.shops_update_one(
            {"id": shop_id},
            {"$set": {
                "latitude": result["latitude"],
                "longitude": result["longitude"],
                "geocoded_address": result.get("formatted_address"),
                "geocode_confidence": result.get("confidence"),
                "geocoded_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return {
            "success": True,
            "shop_id": shop_id,
            "coordinates": {"latitude": result["latitude"], "longitude": result["longitude"]},
            "confidence": result.get("confidence"),
            "formatted_address": result.get("formatted_address")
        }
    else:
        return {
            "success": False,
            "shop_id": shop_id,
            "error": "Could not geocode shop location"
        }

@api_router.post("/geocode/shops/batch")
async def geocode_shops_batch(limit: int = 50):
    """Geocode all shops that don't have coordinates yet"""
    # Find shops without coordinates
    shops_without_coords = await db.shops_find(
        {"latitude": {"$exists": False}},
        limit=limit
    )
    
    # Also find shops with null latitude
    if not shops_without_coords:
        all_shops = await db.shops_find({}, limit=limit)
        shops_without_coords = [s for s in all_shops if s.get('latitude') is None]
    
    if not shops_without_coords:
        return {"message": "All shops already geocoded", "processed": 0}
    
    geocoding_service = get_geocoding_service()
    results = {"success": 0, "failed": 0, "details": []}
    
    for shop in shops_without_coords:
        result = await geocoding_service.geocode_shop(shop["name"], shop.get("address"))
        
        if result:
            await db.shops_update_one(
                {"id": shop["id"]},
                {"$set": {
                    "latitude": result["latitude"],
                    "longitude": result["longitude"],
                    "geocoded_address": result.get("formatted_address"),
                    "geocode_confidence": result.get("confidence"),
                    "geocoded_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            results["success"] += 1
            results["details"].append({
                "shop": shop["name"],
                "status": "success",
                "confidence": result.get("confidence")
            })
        else:
            results["failed"] += 1
            results["details"].append({
                "shop": shop["name"],
                "status": "failed"
            })
        
        # Rate limit to avoid hitting API limits (Nominatim: 1 req/sec)
        await asyncio.sleep(1.1)
    
    return results

@api_router.get("/geocode/stats")
async def get_geocoding_stats():
    """Get statistics on shop geocoding status"""
    total_shops = await db.shops_count({})
    geocoded = await db.shops_count({"latitude": {"$ne": None, "$exists": True}})
    not_geocoded = total_shops - geocoded
    
    # Count by confidence level
    high_confidence = await db.shops_count({"geocode_confidence": "high"})
    medium_confidence = await db.shops_count({"geocode_confidence": "medium"})
    low_confidence = await db.shops_count({"geocode_confidence": {"$in": ["low", "very_low"]}})
    
    return {
        "total_shops": total_shops,
        "geocoded": geocoded,
        "not_geocoded": not_geocoded,
        "geocoded_percentage": round(geocoded / total_shops * 100, 1) if total_shops > 0 else 0,
        "by_confidence": {
            "high": high_confidence,
            "medium": medium_confidence,
            "low": low_confidence
        }
    }

@api_router.post("/geocode/address")
async def geocode_address_endpoint(address: str = None, shop_name: str = None):
    """Test geocoding for a specific address"""
    if not address and not shop_name:
        raise HTTPException(status_code=400, detail="Either address or shop_name is required")
    
    geocoding_service = get_geocoding_service()
    result = await geocoding_service.geocode_address(address, shop_name)
    
    if result:
        return {
            "success": True,
            "coordinates": {"latitude": result["latitude"], "longitude": result["longitude"]},
            "formatted_address": result.get("formatted_address"),
            "confidence": result.get("confidence"),
            "source": result.get("source")
        }
    else:
        return {
            "success": False,
            "error": "Could not geocode address"
        }

# --- WhatsApp Cloud API Webhook Endpoints ---

# Store customer's last location temporarily (for when they send image after location)
customer_locations: Dict[str, Dict] = {}

@api_router.get("/whatsapp/webhook")
async def verify_whatsapp_webhook(request_args: dict = None):
    """
    Webhook verification endpoint for WhatsApp Cloud API
    Meta sends a GET request to verify the webhook URL
    """
    from fastapi import Request, Query
    # This will be called with query parameters
    # hub.mode, hub.verify_token, hub.challenge
    return {"status": "ok"}

@app.api_route("/api/whatsapp/webhook", methods=["GET", "HEAD"])
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """Verify webhook for WhatsApp Cloud API"""
    logger.info(f"Webhook verification: mode={hub_mode}, token={hub_verify_token}, challenge={hub_challenge}")
    
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully")
        # Meta expects plain text response with the challenge value
        return PlainTextResponse(content=hub_challenge or "OK")
    else:
        logger.warning("❌ Webhook verification failed")
        raise HTTPException(status_code=403, detail="Verification failed")

@api_router.post("/whatsapp/webhook")
async def whatsapp_webhook(data: dict, background_tasks: BackgroundTasks):
    """
    Handle incoming WhatsApp messages from Cloud API
    This is the main webhook endpoint that receives all messages
    """
    logger.info("📩 WhatsApp webhook received")
    
    # Parse the incoming webhook
    parsed = parse_webhook_message(data)
    
    if not parsed:
        # Could be a status update, not a message
        return {"status": "ok"}
    
    phone_number = parsed["phone_number"]
    message_type = parsed["message_type"]
    message_id = parsed["message_id"]
    content = parsed["content"]
    media_id = parsed["media_id"]
    location = parsed["location"]
    contact_name = parsed.get("contact_name")
    
    logger.info(f"📱 Message from {phone_number}: type={message_type}")
    
    # Get WhatsApp client
    wa = get_whatsapp_client()
    
    # Mark message as read
    await wa.mark_as_read(message_id)
    
    # Get or create customer
    customer = await get_or_create_customer(phone_number, contact_name)
    
    # Handle different message types
    if message_type == "image" and media_id:
        # Process receipt image
        background_tasks.add_task(
            process_receipt_from_whatsapp,
            phone_number, media_id, parsed.get("mime_type", "image/jpeg"), customer
        )
        await wa.send_text_message(phone_number, "📸 Receipt received! Processing with AI... Please wait.")
        
    elif message_type == "location" and location:
        # Store location for next image upload
        customer_locations[phone_number] = {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await wa.send_text_message(
            phone_number, 
            f"📍 Location saved! ({location['latitude']:.4f}, {location['longitude']:.4f})\n\nNow send your receipt photo!"
        )
        
    elif message_type == "text":
        # Handle text commands
        await handle_text_command(phone_number, content.lower().strip(), wa)
    
    else:
        await wa.send_text_message(phone_number, "Please send a receipt photo or type HELP for commands.")
    
    return {"status": "ok"}

async def process_receipt_from_whatsapp(phone_number: str, media_id: str, mime_type: str, customer: dict):
    """Background task to process receipt image from WhatsApp"""
    wa = get_whatsapp_client()
    
    try:
        # Download the image
        image_bytes = await wa.download_media(media_id)
        
        if not image_bytes:
            await wa.send_text_message(phone_number, "❌ Failed to download image. Please try again.")
            return
        
        # Convert to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Get stored location if available
        stored_location = customer_locations.pop(phone_number, None)
        latitude = stored_location["latitude"] if stored_location else None
        longitude = stored_location["longitude"] if stored_location else None
        
        # Process with LandingAI
        processor = get_receipt_processor()
        extracted = processor.process_receipt_image(image_base64, mime_type)
        
        shop_name = extracted.get("shop_name")
        shop_address = extracted.get("shop_address")
        amount = extracted.get("amount", 0)
        items = extracted.get("items", [])
        
        # Geocode shop
        shop_lat, shop_lon = None, None
        if shop_name:
            shop_lat, shop_lon = await geocode_shop_from_receipt(shop_name, shop_address)
        
        # Calculate fraud risk
        distance_km = None
        if shop_lat and shop_lon and latitude and longitude:
            distance_km = calculate_distance_km(shop_lat, shop_lon, latitude, longitude)
        
        fraud_assessment = assess_fraud_risk(distance_km, amount)
        
        # Create shop if needed
        shop = None
        if shop_name:
            shop = await get_or_create_shop(shop_name, shop_address, shop_lat, shop_lon)
            await db.shops_update_one(
                {"id": shop["id"]},
                {"$inc": {"receipt_count": 1, "total_sales": amount}}
            )
        
        # Determine status
        receipt_status = "processed" if fraud_assessment["fraud_flag"] != "flagged" else "review"
        
        # Create receipt
        receipt = Receipt(
            customer_id=customer["id"],
            customer_phone=phone_number,
            shop_id=shop["id"] if shop else None,
            shop_name=shop_name,
            amount=amount,
            currency="ZAR",
            items=items,
            raw_text=extracted.get("raw_text"),
            image_data=image_base64,
            upload_latitude=latitude,
            upload_longitude=longitude,
            shop_latitude=shop_lat,
            shop_longitude=shop_lon,
            shop_address=shop_address,
            distance_km=distance_km,
            fraud_flag=fraud_assessment["fraud_flag"],
            fraud_score=fraud_assessment["fraud_score"],
            fraud_reason=fraud_assessment["fraud_reason"],
            status=receipt_status
        )
        
        receipt_dict = receipt.model_dump()
        receipt_dict['created_at'] = receipt_dict['created_at'].isoformat()
        receipt_dict['grounding'] = extracted.get('grounding', {})
        
        await db.receipts_insert_one(receipt_dict.copy())
        
        # Update customer stats
        await db.customers_update_one(
            {"id": customer["id"]},
            {"$inc": {"total_receipts": 1, "total_spent": amount}}
        )
        
        # Add to vector store
        try:
            vector_store = get_receipt_vector_store()
            vector_store.add_receipt(receipt.id, receipt_dict)
        except Exception as e:
            logger.warning(f"Vector store error: {e}")
        
        # Send confirmation
        await wa.send_receipt_confirmation(
            phone_number, 
            shop_name or "Unknown Shop", 
            amount, 
            len(items),
            fraud_assessment["fraud_flag"]
        )
        
        logger.info(f"✅ Receipt processed for {phone_number}: {shop_name}, R{amount}")
        
    except Exception as e:
        logger.error(f"❌ Receipt processing failed: {e}")
        await wa.send_text_message(
            phone_number, 
            "❌ Sorry, we couldn't process your receipt. Please try again with a clearer photo."
        )

async def handle_text_command(phone_number: str, command: str, wa):
    """Handle text commands from WhatsApp"""
    
    if command in ["help", "hi", "hello", "start", "menu"]:
        await wa.send_welcome_message(phone_number)
        
    elif command == "receipts":
        receipts = await db.receipts_find(
            {"customer_phone": phone_number},
            sort=("created_at", -1),
            limit=5
        )
        
        if receipts:
            msg = "📋 *Your Recent Receipts:*\n\n"
            for i, r in enumerate(receipts, 1):
                status = "✅" if r.get("status") == "processed" else "🏆" if r.get("status") == "won" else "⏳"
                msg += f"{i}. {status} {r.get('shop_name', 'Unknown')} - R{float(r.get('amount', 0) or 0):.2f}\n"
            await wa.send_text_message(phone_number, msg)
        else:
            await wa.send_text_message(phone_number, "No receipts yet. Send a receipt photo to get started!")
            
    elif command == "wins":
        wins = await db.draws_find(
            {"winner_customer_phone": phone_number},
            sort=("draw_date", -1),
            limit=5
        )
        
        if wins:
            total_won = sum(float(w.get("prize_amount", 0) or 0) for w in wins)
            msg = f"🏆 *Your Winnings: R{total_won:.2f}*\n\n"
            for w in wins:
                msg += f"• {w['draw_date']}: R{float(w.get('prize_amount', 0) or 0):.2f}\n"
            await wa.send_text_message(phone_number, msg)
        else:
            await wa.send_text_message(phone_number, "No wins yet. Keep uploading receipts for a chance to win!")
            
    elif command == "status":
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        draw = await db.draws_find_one({"draw_date": today})
        
        if draw and draw["status"] == "completed":
            if draw["winner_customer_phone"] == phone_number:
                msg = f"🎉 *YOU WON TODAY!*\n\n💰 Prize: R{draw['prize_amount']:.2f}\n\nCongratulations! 🎊"
            else:
                msg = f"📊 *Today's Draw Complete*\n\n🎟️ Entries: {draw['total_receipts']}\n💰 Prize Pool: R{draw['total_amount']:.2f}\n🏆 Winner notified!"
            await wa.send_text_message(phone_number, msg)
        else:
            today_receipts = await db.receipts_count({
                "created_at": {"$gte": f"{today}T00:00:00", "$lte": f"{today}T23:59:59"}
            })
            msg = f"🎰 *Today's Draw Status*\n\n🎟️ Entries so far: {today_receipts}\n⏰ Draw time: Midnight UTC\n\nSend more receipts for more chances!"
            await wa.send_text_message(phone_number, msg)
            
    elif command == "balance":
        customer = await db.customers_find_one({"phone_number": phone_number})
        if customer:
            msg = (
                f"📊 *Your Stats*\n\n"
                f"📋 Receipts: {customer.get('total_receipts', 0)}\n"
                f"💵 Total Spent: R{customer.get('total_spent', 0):.2f}\n"
                f"🏆 Wins: {customer.get('total_wins', 0)}\n"
                f"💰 Won Back: R{customer.get('total_winnings', 0):.2f}"
            )
            await wa.send_text_message(phone_number, msg)
        else:
            await wa.send_text_message(phone_number, "No stats yet. Send your first receipt to get started!")
    
    else:
        await wa.send_text_message(
            phone_number, 
            "I didn't understand that. Send *HELP* for commands or send a receipt photo!"
        )

@api_router.get("/whatsapp/status")
async def get_whatsapp_status():
    """Get WhatsApp Cloud API connection status"""
    wa = get_whatsapp_client()
    
    token_configured = wa.access_token and wa.access_token != 'YOUR_ACCESS_TOKEN_HERE'
    
    return {
        "connected": token_configured,
        "status": "configured" if token_configured else "not_configured",
        "phone_number_id": wa.phone_number_id,
        "api_version": wa.api_version,
        "type": "WhatsApp Cloud API (Official)"
    }

@api_router.post("/whatsapp/send")
async def send_whatsapp_message(data: dict):
    """Send message via WhatsApp Cloud API"""
    wa = get_whatsapp_client()
    
    phone_number = data.get("phone_number", "").replace("+", "")
    message = data.get("message", "")
    
    if not phone_number or not message:
        raise HTTPException(status_code=400, detail="phone_number and message required")
    
    result = await wa.send_text_message(phone_number, message)
    return result

@api_router.post("/whatsapp/test")
async def test_whatsapp_connection(phone_number: str):
    """Test WhatsApp connection by sending a test message"""
    wa = get_whatsapp_client()
    result = await wa.send_text_message(phone_number, "🎰 Test message from Retail Rewards SA!")
    return result

# --- Demo Data Endpoint ---

@api_router.post("/demo/seed")
async def seed_demo_data():
    """Seed demo data for testing"""
    # Clear existing data
    await db.customers_delete_many({})
    await db.receipts_delete_many({})
    await db.shops_delete_many({})
    await db.draws_delete_many({})
    
    # Demo shops with South African locations
    demo_shops = [
        # Johannesburg
        {"name": "Checkers Sandton City", "address": "Sandton City Mall, Rivonia Rd, Sandton, Johannesburg", "latitude": -26.1076, "longitude": 28.0567},
        {"name": "Pick n Pay Rosebank", "address": "The Zone @ Rosebank, Oxford Rd, Rosebank, Johannesburg", "latitude": -26.1452, "longitude": 28.0436},
        {"name": "Woolworths Melrose Arch", "address": "Melrose Arch, Melrose, Johannesburg", "latitude": -26.1340, "longitude": 28.0690},
        {"name": "Shoprite Soweto", "address": "Maponya Mall, Chris Hani Rd, Soweto", "latitude": -26.2678, "longitude": 27.8893},
        # Cape Town
        {"name": "Pick n Pay V&A Waterfront", "address": "V&A Waterfront, Cape Town", "latitude": -33.9036, "longitude": 18.4208},
        {"name": "Checkers Canal Walk", "address": "Canal Walk Shopping Centre, Century City, Cape Town", "latitude": -33.8941, "longitude": 18.5123},
        {"name": "Woolworths Cavendish", "address": "Cavendish Square, Claremont, Cape Town", "latitude": -33.9833, "longitude": 18.4614},
        # Durban
        {"name": "Pick n Pay Gateway", "address": "Gateway Theatre of Shopping, Umhlanga, Durban", "latitude": -29.7294, "longitude": 31.0693},
        {"name": "Checkers Pavilion", "address": "The Pavilion, Westville, Durban", "latitude": -29.8494, "longitude": 30.9278},
        # Pretoria
        {"name": "Woolworths Menlyn", "address": "Menlyn Park Shopping Centre, Pretoria", "latitude": -25.7823, "longitude": 28.2756},
        {"name": "Spar Brooklyn Mall", "address": "Brooklyn Mall, Pretoria", "latitude": -25.7714, "longitude": 28.2378},
        # Port Elizabeth
        {"name": "Checkers Walmer Park", "address": "Walmer Park Shopping Centre, Port Elizabeth", "latitude": -33.9756, "longitude": 25.6051},
    ]
    
    shops = []
    for shop_data in demo_shops:
        shop = Shop(**shop_data)
        shop_dict = shop.model_dump()
        shop_dict['created_at'] = shop_dict['created_at'].isoformat()
        await db.shops_insert_one(shop_dict)
        shops.append(shop_dict)
    
    # Demo customers with South African phone numbers
    demo_customers = [
        {"phone_number": "+27821234567", "name": "Thabo Mokoena"},
        {"phone_number": "+27839876543", "name": "Naledi Dlamini"},
        {"phone_number": "+27724567890", "name": "Sipho Nkosi"},
        {"phone_number": "+27845551234", "name": "Lerato Molefe"},
        {"phone_number": "+27716789012", "name": "Mandla Zulu"},
        {"phone_number": "+27823456789", "name": "Nomvula Khumalo"},
    ]
    
    customers = []
    for cust_data in demo_customers:
        customer = Customer(**cust_data)
        cust_dict = customer.model_dump()
        cust_dict['created_at'] = cust_dict['created_at'].isoformat()
        await db.customers_insert_one(cust_dict)
        customers.append(cust_dict)
    
    # Generate demo receipts for the last 7 days with fraud scenarios
    receipt_count = 0
    fraud_scenarios = [
        {"type": "valid", "distance_range": (0, 30), "weight": 70},  # 70% legitimate local purchases
        {"type": "review", "distance_range": (50, 90), "weight": 15},  # 15% slightly far
        {"type": "suspicious", "distance_range": (100, 180), "weight": 10},  # 10% suspicious
        {"type": "flagged", "distance_range": (500, 1400), "weight": 5},  # 5% likely fraud
    ]
    
    for days_ago in range(7):
        date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        num_receipts = random.randint(8, 18)
        
        for _ in range(num_receipts):
            customer = random.choice(customers)
            shop = random.choice(shops)
            # South African Rand amounts (R50 - R2000)
            amount = round(random.uniform(50, 2000), 2)
            
            # Select fraud scenario based on weights
            rand = random.randint(1, 100)
            if rand <= 70:
                scenario = fraud_scenarios[0]  # valid
            elif rand <= 85:
                scenario = fraud_scenarios[1]  # review
            elif rand <= 95:
                scenario = fraud_scenarios[2]  # suspicious
            else:
                scenario = fraud_scenarios[3]  # flagged
            
            # Generate upload location based on scenario
            distance_km = random.uniform(*scenario["distance_range"])
            
            # Calculate offset in degrees (rough approximation: 1 degree ≈ 111km)
            angle = random.uniform(0, 2 * 3.14159)
            lat_offset = (distance_km / 111) * math.cos(angle)
            lon_offset = (distance_km / 111) * math.sin(angle)
            
            upload_lat = shop["latitude"] + lat_offset
            upload_lon = shop["longitude"] + lon_offset
            
            # Assess fraud
            actual_distance = calculate_distance_km(shop["latitude"], shop["longitude"], upload_lat, upload_lon)
            fraud_assessment = assess_fraud_risk(actual_distance, amount)
            
            # Determine status
            receipt_status = "processed" if fraud_assessment["fraud_flag"] != "flagged" else "review"
            
            receipt = Receipt(
                customer_id=customer["id"],
                customer_phone=customer["phone_number"],
                shop_id=shop["id"],
                shop_name=shop["name"],
                amount=amount,
                currency="ZAR",
                items=[
                    {"name": "Groceries", "price": round(amount * 0.4, 2)},
                    {"name": "Household", "price": round(amount * 0.35, 2)},
                    {"name": "Personal Care", "price": round(amount * 0.25, 2)}
                ],
                upload_latitude=upload_lat,
                upload_longitude=upload_lon,
                shop_latitude=shop["latitude"],
                shop_longitude=shop["longitude"],
                shop_address=shop["address"],
                distance_km=actual_distance,
                fraud_flag=fraud_assessment["fraud_flag"],
                fraud_score=fraud_assessment["fraud_score"],
                fraud_reason=fraud_assessment["fraud_reason"],
                status=receipt_status
            )
            
            receipt_dict = receipt.model_dump()
            receipt_dict['created_at'] = date.replace(
                hour=random.randint(8, 22),
                minute=random.randint(0, 59)
            ).isoformat()
            
            await db.receipts_insert_one(receipt_dict)
            receipt_count += 1
            
            # Update stats
            await db.customers_update_one(
                {"id": customer["id"]},
                {"$inc": {"total_receipts": 1, "total_spent": amount}}
            )
            await db.shops_update_one(
                {"id": shop["id"]},
                {"$inc": {"receipt_count": 1, "total_sales": amount}}
            )
    
    # Get fraud stats for response
    fraud_stats = {
        "valid": await db.receipts_count({"fraud_flag": "valid"}),
        "review": await db.receipts_count({"fraud_flag": "review"}),
        "suspicious": await db.receipts_count({"fraud_flag": "suspicious"}),
        "flagged": await db.receipts_count({"fraud_flag": "flagged"})
    }
    
    return {
        "success": True,
        "message": "Demo data seeded successfully with fraud scenarios",
        "counts": {
            "customers": len(customers),
            "shops": len(shops),
            "receipts": receipt_count
        },
        "fraud_breakdown": fraud_stats
    }

# Scheduler status endpoint
@api_router.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler status and next run times"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    return {
        "running": scheduler.running,
        "jobs": jobs
    }

@api_router.post("/scheduler/trigger-draw")
async def trigger_draw_now():
    """Manually trigger the daily draw (for testing)"""
    await run_scheduled_daily_draw()
    return {"success": True, "message": "Draw triggered"}

# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
