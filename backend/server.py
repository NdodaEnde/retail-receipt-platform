from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Scheduler for daily draws
scheduler = AsyncIOScheduler()

# WhatsApp service URL
WHATSAPP_SERVICE_URL = os.environ.get('WHATSAPP_SERVICE_URL', 'http://localhost:3001')

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
    yield
    # Shutdown
    scheduler.shutdown()
    client.close()

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

async def geocode_shop_from_receipt(shop_name: str, address: str = None) -> tuple:
    """
    Try to geocode a shop from its name and/or address
    Returns (latitude, longitude) or (None, None)
    """
    try:
        search_query = f"{shop_name}"
        if address:
            search_query = f"{shop_name}, {address}"
        
        location = await asyncio.to_thread(
            geolocator.geocode,
            search_query,
            timeout=10
        )
        
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
    
    return (None, None)

# ============== SCHEDULED DRAW FUNCTION ==============

async def run_scheduled_daily_draw():
    """Run the daily draw at midnight - called by scheduler"""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info(f"Running scheduled daily draw for {today}")
        
        # Check if draw already completed
        existing = await db.draws.find_one({"draw_date": today, "status": "completed"})
        if existing:
            logger.info(f"Draw already completed for {today}")
            return
        
        # Get all receipts for today
        start = f"{today}T00:00:00"
        end = f"{today}T23:59:59"
        
        receipts = await db.receipts.find({
            "created_at": {"$gte": start, "$lte": end},
            "status": {"$ne": "won"}
        }, {"_id": 0, "image_data": 0}).to_list(10000)
        
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
            "total_amount": sum(r["amount"] for r in receipts),
            "winner_receipt_id": winner_receipt["id"],
            "winner_customer_id": winner_receipt["customer_id"],
            "winner_customer_phone": winner_receipt["customer_phone"],
            "prize_amount": prize_amount,
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.draws.insert_one(draw_dict.copy())
        
        # Update receipt status
        await db.receipts.update_one(
            {"id": winner_receipt["id"]},
            {"$set": {"status": "won"}}
        )
        
        # Update customer stats
        await db.customers.update_one(
            {"id": winner_receipt["customer_id"]},
            {"$inc": {"total_wins": 1, "total_winnings": prize_amount}}
        )
        
        logger.info(f"Draw completed! Winner: {winner_receipt['customer_phone']}, Prize: ${prize_amount}")
        
        # Notify winner via WhatsApp
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{WHATSAPP_SERVICE_URL}/notify-winner",
                    json={
                        "phone_number": winner_receipt["customer_phone"],
                        "prize_amount": prize_amount,
                        "draw_date": today
                    },
                    timeout=30
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
    customer = await db.customers.find_one({"phone_number": phone_number}, {"_id": 0})
    if not customer:
        customer_obj = Customer(phone_number=phone_number, name=name)
        customer = customer_obj.model_dump()
        customer['created_at'] = customer['created_at'].isoformat()
        await db.customers.insert_one(customer.copy())  # Use copy to prevent _id mutation
    return customer

async def get_or_create_shop(shop_name: str, address: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> dict:
    """Get existing shop or create new one"""
    # Try to find by name (case insensitive)
    shop = await db.shops.find_one({"name": {"$regex": f"^{re.escape(shop_name)}$", "$options": "i"}}, {"_id": 0})
    if not shop:
        shop_obj = Shop(name=shop_name, address=address, latitude=lat, longitude=lon)
        shop = shop_obj.model_dump()
        shop['created_at'] = shop['created_at'].isoformat()
        await db.shops.insert_one(shop.copy())  # Use copy to prevent _id mutation
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
    customer = await db.customers.find_one({"phone_number": phone_number}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@api_router.get("/customers")
async def list_customers(skip: int = 0, limit: int = 50):
    customers = await db.customers.find({}, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.customers.count_documents({})
    return {"customers": customers, "total": total}

@api_router.post("/customers/location")
async def update_customer_location(data: dict):
    """Update customer's last known location"""
    phone_number = data.get("phone_number")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    
    if phone_number and latitude and longitude:
        await db.customers.update_one(
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
        shop_name = extracted.get("shop_name")
        shop_address = extracted.get("shop_address")
        
        if shop_name:
            shop_lat, shop_lon = await geocode_shop_from_receipt(shop_name, shop_address)
        
        # Note: Do NOT fallback to upload location for shop
        # We need separate locations for fraud detection
        
        # Get or create shop
        shop = None
        if shop_name:
            shop = await get_or_create_shop(shop_name, shop_address, shop_lat, shop_lon)
            # Update shop stats
            await db.shops.update_one(
                {"id": shop["id"]},
                {"$inc": {"receipt_count": 1, "total_sales": extracted.get("amount", 0)}}
            )
        
        # Calculate distance between shop and upload location for fraud detection
        distance_km = None
        if shop_lat and shop_lon and request.latitude and request.longitude:
            distance_km = calculate_distance_km(shop_lat, shop_lon, request.latitude, request.longitude)
        
        # Assess fraud risk
        fraud_assessment = assess_fraud_risk(distance_km, extracted.get("amount", 0))
        
        # Determine receipt status based on fraud flag
        receipt_status = "processed"
        if fraud_assessment["fraud_flag"] == "flagged":
            receipt_status = "review"  # Flagged receipts need manual review before entering draw
        
        # Create receipt record with fraud data
        receipt = Receipt(
            customer_id=customer["id"],
            customer_phone=request.phone_number,
            shop_id=shop["id"] if shop else None,
            shop_name=shop_name,
            amount=extracted.get("amount", 0),
            currency="ZAR",
            items=extracted.get("items", []),
            raw_text=extracted.get("raw_text"),
            image_data=request.image_data,  # Store the image
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
        
        await db.receipts.insert_one(receipt_dict.copy())
        
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
        await db.customers.update_one(
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
        await db.shops.update_one(
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
    
    await db.receipts.insert_one(receipt_dict.copy())  # Use copy to prevent _id mutation
    
    # Update customer stats
    await db.customers.update_one(
        {"id": customer["id"]},
        {"$inc": {"total_receipts": 1, "total_spent": parsed_data["amount"]}}
    )
    
    # Remove image_data and any _id from response
    response_receipt = {k: v for k, v in receipt_dict.items() if k not in ['image_data', '_id']}
    response_receipt['has_image'] = image_data is not None
    
    return {"success": True, "receipt": response_receipt}

@api_router.get("/receipts/customer/{phone_number}")
async def get_customer_receipts(phone_number: str, skip: int = 0, limit: int = 50):
    receipts = await db.receipts.find(
        {"customer_phone": phone_number},
        {"_id": 0, "image_data": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.receipts.count_documents({"customer_phone": phone_number})
    return {"receipts": receipts, "total": total}

@api_router.get("/receipts/{receipt_id}")
async def get_receipt(receipt_id: str):
    receipt = await db.receipts.find_one({"id": receipt_id}, {"_id": 0, "image_data": 0})
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt

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
    
    receipts = await db.receipts.find(query, {"_id": 0, "image_data": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.receipts.count_documents(query)
    return {"receipts": receipts, "total": total}

# --- Fraud Detection Endpoints ---

@api_router.get("/fraud/flagged")
async def get_flagged_receipts(skip: int = 0, limit: int = 50):
    """Get all receipts flagged for review or suspicious activity"""
    query = {"fraud_flag": {"$in": ["review", "suspicious", "flagged"]}}
    receipts = await db.receipts.find(query, {"_id": 0, "image_data": 0}).sort("fraud_score", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.receipts.count_documents(query)
    return {"receipts": receipts, "total": total}

@api_router.get("/fraud/stats")
async def get_fraud_stats():
    """Get fraud detection statistics"""
    total = await db.receipts.count_documents({})
    valid = await db.receipts.count_documents({"fraud_flag": "valid"})
    review = await db.receipts.count_documents({"fraud_flag": "review"})
    suspicious = await db.receipts.count_documents({"fraud_flag": "suspicious"})
    flagged = await db.receipts.count_documents({"fraud_flag": "flagged"})
    
    # Average distance for each category
    pipeline = [
        {"$match": {"distance_km": {"$ne": None}}},
        {"$group": {
            "_id": "$fraud_flag",
            "avg_distance": {"$avg": "$distance_km"},
            "max_distance": {"$max": "$distance_km"},
            "count": {"$sum": 1}
        }}
    ]
    distance_stats = await db.receipts.aggregate(pipeline).to_list(10)
    
    return {
        "total_receipts": total,
        "valid": valid,
        "review": review,
        "suspicious": suspicious,
        "flagged": flagged,
        "fraud_rate": round((review + suspicious + flagged) / total * 100, 2) if total > 0 else 0,
        "distance_stats": {d["_id"]: {"avg": round(d["avg_distance"], 2), "max": round(d["max_distance"], 2), "count": d["count"]} for d in distance_stats}
    }

@api_router.post("/fraud/review/{receipt_id}")
async def review_receipt(receipt_id: str, action: str, reason: Optional[str] = None):
    """Admin action on flagged receipt: approve, reject"""
    receipt = await db.receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    if action == "approve":
        await db.receipts.update_one(
            {"id": receipt_id},
            {"$set": {
                "fraud_flag": "valid",
                "status": "processed",
                "fraud_reason": f"Manually approved: {reason}" if reason else "Manually approved by admin"
            }}
        )
        return {"success": True, "message": "Receipt approved and added to draw pool"}
    
    elif action == "reject":
        await db.receipts.update_one(
            {"id": receipt_id},
            {"$set": {
                "status": "rejected",
                "fraud_reason": f"Rejected: {reason}" if reason else "Rejected by admin - suspected fraud"
            }}
        )
        # Rollback customer stats
        await db.customers.update_one(
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
    shops = await db.shops.find({}, {"_id": 0}).sort("receipt_count", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.shops.count_documents({})
    return {"shops": shops, "total": total}

@api_router.get("/shops/{shop_id}")
async def get_shop(shop_id: str):
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
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
    existing_draw = await db.draws.find_one({"draw_date": draw_date, "status": "completed"}, {"_id": 0})
    if existing_draw:
        return {"success": False, "message": "Draw already completed for this date", "draw": existing_draw}
    
    # Get all receipts for this date
    start = f"{draw_date}T00:00:00"
    end = f"{draw_date}T23:59:59"
    
    receipts = await db.receipts.find({
        "created_at": {"$gte": start, "$lte": end},
        "status": {"$ne": "won"}  # Exclude already won receipts
    }, {"_id": 0, "image_data": 0}).to_list(10000)
    
    if not receipts:
        return {"success": False, "message": "No eligible receipts for this date"}
    
    # Random selection - one receipt wins
    winner_receipt = random.choice(receipts)
    prize_amount = winner_receipt["amount"]
    
    # Create draw record
    draw = Draw(
        draw_date=draw_date,
        total_receipts=len(receipts),
        total_amount=sum(r["amount"] for r in receipts),
        winner_receipt_id=winner_receipt["id"],
        winner_customer_id=winner_receipt["customer_id"],
        winner_customer_phone=winner_receipt["customer_phone"],
        prize_amount=prize_amount,
        status="completed"
    )
    
    draw_dict = draw.model_dump()
    draw_dict['created_at'] = draw_dict['created_at'].isoformat()
    await db.draws.insert_one(draw_dict.copy())  # Use copy to prevent _id mutation
    
    # Update receipt status
    await db.receipts.update_one(
        {"id": winner_receipt["id"]},
        {"$set": {"status": "won"}}
    )
    
    # Update customer stats
    await db.customers.update_one(
        {"id": winner_receipt["customer_id"]},
        {"$inc": {"total_wins": 1, "total_winnings": prize_amount}}
    )
    
    # Remove any _id that might have been added
    draw_response = {k: v for k, v in draw_dict.items() if k != '_id'}
    
    # Notify winner via WhatsApp (async, don't block response)
    async def notify_winner():
        try:
            async with httpx.AsyncClient() as http_client:
                await http_client.post(
                    f"{WHATSAPP_SERVICE_URL}/notify-winner",
                    json={
                        "phone_number": winner_receipt["customer_phone"],
                        "prize_amount": prize_amount,
                        "draw_date": draw_date
                    },
                    timeout=30
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
    draws = await db.draws.find({}, {"_id": 0}).sort("draw_date", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.draws.count_documents({})
    return {"draws": draws, "total": total}

@api_router.get("/draws/{draw_date}")
async def get_draw(draw_date: str):
    draw = await db.draws.find_one({"draw_date": draw_date}, {"_id": 0})
    if not draw:
        raise HTTPException(status_code=404, detail="Draw not found")
    return draw

@api_router.get("/draws/winner/{phone_number}")
async def get_customer_wins(phone_number: str):
    wins = await db.draws.find(
        {"winner_customer_phone": phone_number},
        {"_id": 0}
    ).sort("draw_date", -1).to_list(100)
    return {"wins": wins, "total": len(wins)}

# --- Map Data Endpoints ---

@api_router.get("/map/shops")
async def get_map_shops():
    """Get all shops with coordinates for map display"""
    shops = await db.shops.find(
        {"latitude": {"$ne": None}, "longitude": {"$ne": None}},
        {"_id": 0}
    ).to_list(1000)
    return {"shops": shops}

@api_router.get("/map/receipts")
async def get_map_receipts(date: Optional[str] = None):
    """Get receipt upload locations for map display"""
    query = {"upload_latitude": {"$ne": None}, "upload_longitude": {"$ne": None}}
    if date:
        query["created_at"] = {"$gte": f"{date}T00:00:00", "$lte": f"{date}T23:59:59"}
    
    receipts = await db.receipts.find(query, {
        "_id": 0,
        "id": 1,
        "customer_phone": 1,
        "shop_name": 1,
        "amount": 1,
        "upload_latitude": 1,
        "upload_longitude": 1,
        "created_at": 1
    }).to_list(1000)
    return {"receipts": receipts}

# --- Analytics Endpoints ---

@api_router.get("/analytics/overview")
async def get_analytics_overview():
    """Get overall platform statistics"""
    total_customers = await db.customers.count_documents({})
    total_receipts = await db.receipts.count_documents({})
    total_shops = await db.shops.count_documents({})
    total_draws = await db.draws.count_documents({"status": "completed"})
    
    # Total spent and winnings
    pipeline = [
        {"$group": {
            "_id": None,
            "total_spent": {"$sum": "$total_spent"},
            "total_winnings": {"$sum": "$total_winnings"}
        }}
    ]
    result = await db.customers.aggregate(pipeline).to_list(1)
    totals = result[0] if result else {"total_spent": 0, "total_winnings": 0}
    
    return {
        "total_customers": total_customers,
        "total_receipts": total_receipts,
        "total_shops": total_shops,
        "total_draws": total_draws,
        "total_spent": totals.get("total_spent", 0),
        "total_winnings": totals.get("total_winnings", 0)
    }

@api_router.get("/analytics/spending-by-day")
async def get_spending_by_day(days: int = 30):
    """Get daily spending for the last N days"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    pipeline = [
        {"$addFields": {
            "date_str": {"$substr": ["$created_at", 0, 10]}
        }},
        {"$group": {
            "_id": "$date_str",
            "total": {"$sum": "$amount"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}},
        {"$limit": days}
    ]
    
    result = await db.receipts.aggregate(pipeline).to_list(days)
    return {"data": [{"date": r["_id"], "amount": r["total"], "receipts": r["count"]} for r in result]}

@api_router.get("/analytics/popular-shops")
async def get_popular_shops(limit: int = 10):
    """Get most popular shops by receipt count"""
    shops = await db.shops.find({}, {"_id": 0}).sort("receipt_count", -1).limit(limit).to_list(limit)
    return {"shops": shops}

@api_router.get("/analytics/top-spenders")
async def get_top_spenders(limit: int = 10):
    """Get top spending customers"""
    customers = await db.customers.find({}, {"_id": 0}).sort("total_spent", -1).limit(limit).to_list(limit)
    return {"customers": customers}

@api_router.get("/analytics/receipts-by-hour")
async def get_receipts_by_hour():
    """Get receipt count by hour of day"""
    pipeline = [
        {"$addFields": {
            "hour": {"$hour": {"$dateFromString": {"dateString": "$created_at"}}}
        }},
        {"$group": {
            "_id": "$hour",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    result = await db.receipts.aggregate(pipeline).to_list(24)
    # Fill missing hours with 0
    hour_data = {r["_id"]: r["count"] for r in result}
    return {"data": [{"hour": h, "count": hour_data.get(h, 0)} for h in range(24)]}

@api_router.get("/analytics/spending-by-shop")
async def get_spending_by_shop(limit: int = 10):
    """Get spending distribution by shop"""
    shops = await db.shops.find({}, {"_id": 0, "name": 1, "total_sales": 1, "receipt_count": 1}).sort("total_sales", -1).limit(limit).to_list(limit)
    return {"shops": shops}

# --- WhatsApp Webhook Endpoints ---

@api_router.post("/whatsapp/webhook")
async def whatsapp_webhook(data: dict):
    """Handle incoming WhatsApp messages"""
    logger.info(f"WhatsApp webhook received: {json.dumps(data)}")
    
    # Extract message details
    phone_number = data.get("phone_number", "")
    message_type = data.get("type", "text")
    message_content = data.get("content", "")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    image_data = data.get("image_data")  # Base64 encoded image
    
    # Get or create customer
    customer = await get_or_create_customer(phone_number)
    
    response_message = ""
    
    if message_type == "image" and image_data:
        # Process receipt image
        # In production, this would call LandingAI ADE for OCR
        response_message = "📸 Receipt received! Processing... We'll notify you once it's registered for today's draw."
        
        # Create placeholder receipt (in production, OCR would extract details)
        receipt = Receipt(
            customer_id=customer["id"],
            customer_phone=phone_number,
            image_data=image_data,
            upload_latitude=latitude,
            upload_longitude=longitude,
            status="pending"
        )
        receipt_dict = receipt.model_dump()
        receipt_dict['created_at'] = receipt_dict['created_at'].isoformat()
        await db.receipts.insert_one(receipt_dict)
        
    elif message_type == "location":
        response_message = f"📍 Location received: {latitude}, {longitude}. Now send your receipt photo!"
        
    elif message_content.lower() in ["help", "hi", "hello", "start"]:
        response_message = """🎰 Welcome to Retail Rewards!

📸 Send a photo of your receipt to enter today's draw
📍 Share your location first for better tracking
🏆 Daily winners announced at midnight
💰 Win back what you spent!

Commands:
• RECEIPTS - View your receipts
• WINS - View your winnings
• STATUS - Check today's draw"""
        
    elif message_content.lower() == "receipts":
        receipts = await db.receipts.find(
            {"customer_phone": phone_number},
            {"_id": 0, "image_data": 0}
        ).sort("created_at", -1).limit(5).to_list(5)
        
        if receipts:
            response_message = "📋 Your recent receipts:\n\n"
            for i, r in enumerate(receipts, 1):
                status_emoji = "✅" if r["status"] == "processed" else "🏆" if r["status"] == "won" else "⏳"
                response_message += f"{i}. {r.get('shop_name', 'Unknown')} - ${r.get('amount', 0):.2f} {status_emoji}\n"
        else:
            response_message = "No receipts yet. Send a receipt photo to get started!"
            
    elif message_content.lower() == "wins":
        wins = await db.draws.find(
            {"winner_customer_phone": phone_number},
            {"_id": 0}
        ).sort("draw_date", -1).limit(5).to_list(5)
        
        if wins:
            total_won = sum(w["prize_amount"] for w in wins)
            response_message = f"🏆 Your winnings: ${total_won:.2f}\n\n"
            for w in wins:
                response_message += f"• {w['draw_date']}: ${w['prize_amount']:.2f}\n"
        else:
            response_message = "No wins yet. Keep uploading receipts for a chance to win!"
            
    elif message_content.lower() == "status":
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        draw = await db.draws.find_one({"draw_date": today}, {"_id": 0})
        
        if draw and draw["status"] == "completed":
            if draw["winner_customer_phone"] == phone_number:
                response_message = f"🎉 YOU WON TODAY! Prize: ${draw['prize_amount']:.2f}"
            else:
                response_message = f"Today's draw is complete. Winner has been notified.\nTotal entries: {draw['total_receipts']}"
        else:
            today_receipts = await db.receipts.count_documents({
                "created_at": {"$gte": f"{today}T00:00:00", "$lte": f"{today}T23:59:59"}
            })
            response_message = f"🎰 Today's draw status:\nTotal entries: {today_receipts}\nDraw at midnight!"
    else:
        response_message = "Send a receipt photo or type HELP for commands."
    
    return {"reply": response_message, "success": True}

@api_router.get("/whatsapp/qr")
async def get_whatsapp_qr():
    """Get WhatsApp QR code from Baileys service"""
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(f"{WHATSAPP_SERVICE_URL}/qr", timeout=10)
            return response.json()
    except Exception as e:
        logger.error(f"Failed to get WhatsApp QR: {e}")
        return {"qr": None, "connected": False, "error": str(e)}

@api_router.get("/whatsapp/status")
async def get_whatsapp_status():
    """Get WhatsApp connection status from Baileys service"""
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(f"{WHATSAPP_SERVICE_URL}/status", timeout=10)
            return response.json()
    except Exception as e:
        logger.error(f"Failed to get WhatsApp status: {e}")
        return {"connected": False, "status": "service_unavailable", "error": str(e)}

@api_router.post("/whatsapp/send")
async def send_whatsapp_message(data: dict):
    """Send message via WhatsApp service"""
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                f"{WHATSAPP_SERVICE_URL}/send",
                json=data,
                timeout=30
            )
            return response.json()
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return {"success": False, "error": str(e)}

# --- Demo Data Endpoint ---

@api_router.post("/demo/seed")
async def seed_demo_data():
    """Seed demo data for testing"""
    # Clear existing data
    await db.customers.delete_many({})
    await db.receipts.delete_many({})
    await db.shops.delete_many({})
    await db.draws.delete_many({})
    
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
        await db.shops.insert_one(shop_dict)
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
        await db.customers.insert_one(cust_dict)
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
            
            await db.receipts.insert_one(receipt_dict)
            receipt_count += 1
            
            # Update stats
            await db.customers.update_one(
                {"id": customer["id"]},
                {"$inc": {"total_receipts": 1, "total_spent": amount}}
            )
            await db.shops.update_one(
                {"id": shop["id"]},
                {"$inc": {"receipt_count": 1, "total_sales": amount}}
            )
    
    # Get fraud stats for response
    fraud_stats = {
        "valid": await db.receipts.count_documents({"fraud_flag": "valid"}),
        "review": await db.receipts.count_documents({"fraud_flag": "review"}),
        "suspicious": await db.receipts.count_documents({"fraud_flag": "suspicious"}),
        "flagged": await db.receipts.count_documents({"fraud_flag": "flagged"})
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
