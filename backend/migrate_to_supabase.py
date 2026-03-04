"""
MongoDB to Supabase Migration Script
Migrates all existing data from MongoDB to Supabase PostgreSQL

Usage:
    python migrate_to_supabase.py

Prerequisites:
    - MongoDB running with existing data
    - Supabase project created with schema.sql executed
    - Environment variables set:
        - MONGO_URL
        - DB_NAME
        - SUPABASE_URL
        - SUPABASE_KEY
"""

import os
import asyncio
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from supabase import create_client
import base64

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
load_dotenv()

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'test_database')
mongo_client = AsyncIOMotorClient(mongo_url)
mongo_db = mongo_client[db_name]

# Supabase connection
supabase_url = os.environ.get('SUPABASE_URL', '')
supabase_key = os.environ.get('SUPABASE_KEY', '')
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None


async def migrate_customers():
    """Migrate customers collection"""
    logger.info("📦 Migrating customers...")
    
    cursor = mongo_db.customers.find({})
    customers = await cursor.to_list(length=10000)
    
    if not customers:
        logger.info("  No customers to migrate")
        return 0
    
    migrated = 0
    for c in customers:
        try:
            customer_data = {
                'id': c.get('id'),
                'phone_number': c.get('phone_number'),
                'name': c.get('name'),
                'total_receipts': c.get('total_receipts', 0),
                'total_spent': float(c.get('total_spent', 0) or 0),
                'total_wins': c.get('total_wins', 0),
                'total_winnings': float(c.get('total_winnings', 0) or 0),
                'last_latitude': c.get('last_latitude'),
                'last_longitude': c.get('last_longitude'),
                'location_updated_at': c.get('location_updated_at'),
                'created_at': c.get('created_at')
            }
            
            supabase.table('customers').upsert(customer_data, on_conflict='id').execute()
            migrated += 1
            
        except Exception as e:
            logger.error(f"  Failed to migrate customer {c.get('phone_number')}: {e}")
    
    logger.info(f"  ✅ Migrated {migrated}/{len(customers)} customers")
    return migrated


async def migrate_shops():
    """Migrate shops collection"""
    logger.info("📦 Migrating shops...")
    
    cursor = mongo_db.shops.find({})
    shops = await cursor.to_list(length=10000)
    
    if not shops:
        logger.info("  No shops to migrate")
        return 0
    
    migrated = 0
    for s in shops:
        try:
            shop_data = {
                'id': s.get('id'),
                'name': s.get('name'),
                'address': s.get('address'),
                'latitude': s.get('latitude'),
                'longitude': s.get('longitude'),
                'geocoded_address': s.get('geocoded_address'),
                'geocode_confidence': s.get('geocode_confidence'),
                'geocoded_at': s.get('geocoded_at'),
                'receipt_count': s.get('receipt_count', 0),
                'total_sales': float(s.get('total_sales', 0) or 0),
                'created_at': s.get('created_at')
            }
            
            supabase.table('shops').upsert(shop_data, on_conflict='id').execute()
            migrated += 1
            
        except Exception as e:
            logger.error(f"  Failed to migrate shop {s.get('name')}: {e}")
    
    logger.info(f"  ✅ Migrated {migrated}/{len(shops)} shops")
    return migrated


async def migrate_receipts():
    """Migrate receipts collection"""
    logger.info("📦 Migrating receipts...")
    
    cursor = mongo_db.receipts.find({})
    receipts = await cursor.to_list(length=50000)
    
    if not receipts:
        logger.info("  No receipts to migrate")
        return 0
    
    migrated = 0
    items_migrated = 0
    images_uploaded = 0
    
    for r in receipts:
        try:
            receipt_id = r.get('id')
            
            # Handle image - upload to Supabase Storage
            image_url = None
            image_path = None
            image_data = r.get('image_data')
            
            if image_data:
                try:
                    # Decode and upload image
                    if ',' in image_data:
                        image_data = image_data.split(',')[1]
                    
                    image_bytes = base64.b64decode(image_data)
                    file_path = f"{receipt_id}.jpg"
                    
                    supabase.storage.from_('receipts').upload(
                        path=file_path,
                        file=image_bytes,
                        file_options={"content-type": "image/jpeg", "upsert": "true"}
                    )
                    
                    image_url = supabase.storage.from_('receipts').get_public_url(file_path)
                    image_path = file_path
                    images_uploaded += 1
                    
                except Exception as img_e:
                    logger.warning(f"  Could not upload image for receipt {receipt_id}: {img_e}")
            
            # Prepare receipt data
            receipt_data = {
                'id': receipt_id,
                'customer_id': r.get('customer_id'),
                'customer_phone': r.get('customer_phone'),
                'shop_id': r.get('shop_id'),
                'shop_name': r.get('shop_name'),
                'amount': float(r.get('amount', 0) or 0),
                'currency': r.get('currency', 'ZAR'),
                'image_url': image_url,
                'image_path': image_path,
                'raw_text': r.get('raw_text'),
                'upload_latitude': r.get('upload_latitude'),
                'upload_longitude': r.get('upload_longitude'),
                'upload_address': r.get('upload_address'),
                'shop_latitude': r.get('shop_latitude'),
                'shop_longitude': r.get('shop_longitude'),
                'shop_address': r.get('shop_address'),
                'distance_km': r.get('distance_km'),
                'fraud_flag': r.get('fraud_flag', 'valid'),
                'fraud_score': r.get('fraud_score', 0),
                'fraud_reason': r.get('fraud_reason'),
                'status': r.get('status', 'pending'),
                'processing_error': r.get('processing_error'),
                'grounding': r.get('grounding'),
                'created_at': r.get('created_at')
            }
            
            supabase.table('receipts').upsert(receipt_data, on_conflict='id').execute()
            migrated += 1
            
            # Migrate items to separate table
            items = r.get('items', [])
            if items:
                for item in items:
                    try:
                        import uuid
                        item_data = {
                            'id': str(uuid.uuid4()),
                            'receipt_id': receipt_id,
                            'name': item.get('name', ''),
                            'quantity': item.get('quantity', 1),
                            'unit_price': item.get('unit_price'),
                            'total_price': item.get('total_price') or item.get('price')
                        }
                        supabase.table('receipt_items').insert(item_data).execute()
                        items_migrated += 1
                    except Exception as item_e:
                        logger.warning(f"  Could not migrate item: {item_e}")
            
            if migrated % 100 == 0:
                logger.info(f"  Progress: {migrated} receipts, {items_migrated} items, {images_uploaded} images")
            
        except Exception as e:
            logger.error(f"  Failed to migrate receipt {r.get('id')}: {e}")
    
    logger.info(f"  ✅ Migrated {migrated}/{len(receipts)} receipts")
    logger.info(f"  ✅ Migrated {items_migrated} items")
    logger.info(f"  ✅ Uploaded {images_uploaded} images")
    return migrated


async def migrate_draws():
    """Migrate draws collection"""
    logger.info("📦 Migrating draws...")
    
    cursor = mongo_db.draws.find({})
    draws = await cursor.to_list(length=10000)
    
    if not draws:
        logger.info("  No draws to migrate")
        return 0
    
    migrated = 0
    for d in draws:
        try:
            draw_data = {
                'id': d.get('id'),
                'draw_date': d.get('draw_date'),
                'total_receipts': d.get('total_receipts', 0),
                'total_amount': float(d.get('total_amount', 0) or 0),
                'winner_receipt_id': d.get('winner_receipt_id'),
                'winner_customer_id': d.get('winner_customer_id'),
                'winner_customer_phone': d.get('winner_customer_phone'),
                'prize_amount': float(d.get('prize_amount', 0) or 0),
                'status': d.get('status', 'pending'),
                'created_at': d.get('created_at')
            }
            
            supabase.table('draws').upsert(draw_data, on_conflict='id').execute()
            migrated += 1
            
        except Exception as e:
            logger.error(f"  Failed to migrate draw {d.get('draw_date')}: {e}")
    
    logger.info(f"  ✅ Migrated {migrated}/{len(draws)} draws")
    return migrated


async def verify_migration():
    """Verify migration counts"""
    logger.info("🔍 Verifying migration...")
    
    # MongoDB counts
    mongo_customers = await mongo_db.customers.count_documents({})
    mongo_shops = await mongo_db.shops.count_documents({})
    mongo_receipts = await mongo_db.receipts.count_documents({})
    mongo_draws = await mongo_db.draws.count_documents({})
    
    # Supabase counts
    sb_customers = supabase.table('customers').select('*', count='exact').execute().count
    sb_shops = supabase.table('shops').select('*', count='exact').execute().count
    sb_receipts = supabase.table('receipts').select('*', count='exact').execute().count
    sb_draws = supabase.table('draws').select('*', count='exact').execute().count
    sb_items = supabase.table('receipt_items').select('*', count='exact').execute().count
    
    logger.info(f"  Customers: MongoDB={mongo_customers}, Supabase={sb_customers}")
    logger.info(f"  Shops: MongoDB={mongo_shops}, Supabase={sb_shops}")
    logger.info(f"  Receipts: MongoDB={mongo_receipts}, Supabase={sb_receipts}")
    logger.info(f"  Draws: MongoDB={mongo_draws}, Supabase={sb_draws}")
    logger.info(f"  Receipt Items (new): Supabase={sb_items}")
    
    return {
        'customers': {'mongo': mongo_customers, 'supabase': sb_customers},
        'shops': {'mongo': mongo_shops, 'supabase': sb_shops},
        'receipts': {'mongo': mongo_receipts, 'supabase': sb_receipts},
        'draws': {'mongo': mongo_draws, 'supabase': sb_draws},
        'items': {'supabase': sb_items}
    }


async def run_migration():
    """Run the full migration"""
    logger.info("=" * 60)
    logger.info("🚀 Starting MongoDB to Supabase Migration")
    logger.info("=" * 60)
    
    if not supabase:
        logger.error("❌ Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY")
        return
    
    start_time = datetime.now()
    
    # Run migrations in order (respecting foreign keys)
    await migrate_customers()
    await migrate_shops()
    await migrate_receipts()
    await migrate_draws()
    
    # Verify
    verification = await verify_migration()
    
    elapsed = datetime.now() - start_time
    logger.info("=" * 60)
    logger.info(f"✅ Migration complete in {elapsed}")
    logger.info("=" * 60)
    
    return verification


if __name__ == "__main__":
    asyncio.run(run_migration())
