from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="Retail Rewards Platform")

# Create router with /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Geocoder for reverse geocoding
geolocator = Nominatim(user_agent="retail_rewards_app")

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
    currency: str = "USD"
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
    # Status
    status: str = "pending"  # pending, processed, won
    processing_error: Optional[str] = None
    receipt_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
        await db.customers.insert_one(customer)
    return customer

async def get_or_create_shop(shop_name: str, address: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> dict:
    """Get existing shop or create new one"""
    # Try to find by name (case insensitive)
    shop = await db.shops.find_one({"name": {"$regex": f"^{re.escape(shop_name)}$", "$options": "i"}}, {"_id": 0})
    if not shop:
        shop_obj = Shop(name=shop_name, address=address, latitude=lat, longitude=lon)
        shop = shop_obj.model_dump()
        shop['created_at'] = shop['created_at'].isoformat()
        await db.shops.insert_one(shop)
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

# --- Receipt Endpoints ---

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
    
    await db.receipts.insert_one(receipt_dict)
    
    # Update customer stats
    await db.customers.update_one(
        {"id": customer["id"]},
        {"$inc": {"total_receipts": 1, "total_spent": parsed_data["amount"]}}
    )
    
    # Remove image_data from response (too large)
    response_receipt = {k: v for k, v in receipt_dict.items() if k != 'image_data'}
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
    status: Optional[str] = None
):
    query = {}
    if date:
        start = datetime.fromisoformat(f"{date}T00:00:00+00:00")
        end = datetime.fromisoformat(f"{date}T23:59:59+00:00")
        query["created_at"] = {"$gte": start.isoformat(), "$lte": end.isoformat()}
    if status:
        query["status"] = status
    
    receipts = await db.receipts.find(query, {"_id": 0, "image_data": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.receipts.count_documents(query)
    return {"receipts": receipts, "total": total}

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
    """Get WhatsApp QR code for authentication (placeholder)"""
    return {"qr": None, "connected": False, "message": "WhatsApp service not configured"}

@api_router.get("/whatsapp/status")
async def get_whatsapp_status():
    """Get WhatsApp connection status"""
    return {"connected": False, "message": "WhatsApp service integration pending"}

# --- Demo Data Endpoint ---

@api_router.post("/demo/seed")
async def seed_demo_data():
    """Seed demo data for testing"""
    # Clear existing data
    await db.customers.delete_many({})
    await db.receipts.delete_many({})
    await db.shops.delete_many({})
    await db.draws.delete_many({})
    
    # Demo shops with locations
    demo_shops = [
        {"name": "Walmart Supercenter", "address": "123 Main St, New York", "latitude": 40.7128, "longitude": -74.0060},
        {"name": "Target Store", "address": "456 Oak Ave, Los Angeles", "latitude": 34.0522, "longitude": -118.2437},
        {"name": "Costco Wholesale", "address": "789 Pine Rd, Chicago", "latitude": 41.8781, "longitude": -87.6298},
        {"name": "Whole Foods Market", "address": "321 Elm St, Houston", "latitude": 29.7604, "longitude": -95.3698},
        {"name": "Trader Joe's", "address": "654 Maple Dr, Phoenix", "latitude": 33.4484, "longitude": -112.0740},
        {"name": "Kroger", "address": "987 Cedar Ln, Philadelphia", "latitude": 39.9526, "longitude": -75.1652},
        {"name": "Safeway", "address": "147 Birch Blvd, San Antonio", "latitude": 29.4241, "longitude": -98.4936},
        {"name": "Publix", "address": "258 Willow Way, San Diego", "latitude": 32.7157, "longitude": -117.1611},
    ]
    
    shops = []
    for shop_data in demo_shops:
        shop = Shop(**shop_data)
        shop_dict = shop.model_dump()
        shop_dict['created_at'] = shop_dict['created_at'].isoformat()
        await db.shops.insert_one(shop_dict)
        shops.append(shop_dict)
    
    # Demo customers
    demo_customers = [
        {"phone_number": "+1234567890", "name": "John Doe"},
        {"phone_number": "+0987654321", "name": "Jane Smith"},
        {"phone_number": "+1122334455", "name": "Bob Johnson"},
        {"phone_number": "+5544332211", "name": "Alice Brown"},
        {"phone_number": "+6677889900", "name": "Charlie Wilson"},
    ]
    
    customers = []
    for cust_data in demo_customers:
        customer = Customer(**cust_data)
        cust_dict = customer.model_dump()
        cust_dict['created_at'] = cust_dict['created_at'].isoformat()
        await db.customers.insert_one(cust_dict)
        customers.append(cust_dict)
    
    # Generate demo receipts for the last 7 days
    receipt_count = 0
    for days_ago in range(7):
        date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        num_receipts = random.randint(5, 15)
        
        for _ in range(num_receipts):
            customer = random.choice(customers)
            shop = random.choice(shops)
            amount = round(random.uniform(10, 200), 2)
            
            # Random location near shop
            lat_offset = random.uniform(-0.01, 0.01)
            lon_offset = random.uniform(-0.01, 0.01)
            
            receipt = Receipt(
                customer_id=customer["id"],
                customer_phone=customer["phone_number"],
                shop_id=shop["id"],
                shop_name=shop["name"],
                amount=amount,
                items=[
                    {"name": "Item 1", "price": round(amount * 0.3, 2)},
                    {"name": "Item 2", "price": round(amount * 0.4, 2)},
                    {"name": "Item 3", "price": round(amount * 0.3, 2)}
                ],
                upload_latitude=shop["latitude"] + lat_offset,
                upload_longitude=shop["longitude"] + lon_offset,
                shop_latitude=shop["latitude"],
                shop_longitude=shop["longitude"],
                shop_address=shop["address"],
                status="processed"
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
    
    return {
        "success": True,
        "message": "Demo data seeded successfully",
        "counts": {
            "customers": len(customers),
            "shops": len(shops),
            "receipts": receipt_count
        }
    }

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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
