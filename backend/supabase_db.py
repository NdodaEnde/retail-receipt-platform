"""
Supabase Database Client
Handles all database operations for the Receipt-to-Win platform
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

logger = logging.getLogger(__name__)


class SupabaseDB:
    """
    Supabase database client with methods matching the existing MongoDB operations
    """
    
    def __init__(self):
        self.url = os.environ.get('SUPABASE_URL', '')
        self.key = os.environ.get('SUPABASE_KEY', '')  # Use service_role key for backend
        self.client: Optional[Client] = None
        
        if self.url and self.key:
            try:
                self.client = create_client(self.url, self.key)
                logger.info("✅ Supabase client initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Supabase: {e}")
        else:
            logger.warning("⚠️ Supabase credentials not configured")
    
    # ==================== CUSTOMERS ====================
    
    async def get_customer(self, phone_number: str) -> Optional[Dict]:
        """Get customer by phone number"""
        try:
            result = self.client.table('customers').select('*').eq('phone_number', phone_number).single().execute()
            return result.data
        except Exception as e:
            if 'No rows' in str(e) or 'PGRST116' in str(e):
                return None
            logger.error(f"Error getting customer: {e}")
            return None
    
    async def create_customer(self, phone_number: str, name: Optional[str] = None) -> Dict:
        """Create a new customer"""
        customer_data = {
            'id': str(uuid.uuid4()),
            'phone_number': phone_number,
            'name': name,
            'total_receipts': 0,
            'total_spent': 0.0,
            'total_wins': 0,
            'total_winnings': 0.0
        }
        result = self.client.table('customers').insert(customer_data).execute()
        return result.data[0] if result.data else customer_data
    
    async def get_or_create_customer(self, phone_number: str, name: Optional[str] = None) -> Dict:
        """Get existing customer or create new one"""
        customer = await self.get_customer(phone_number)
        if not customer:
            customer = await self.create_customer(phone_number, name)
        return customer
    
    async def update_customer_stats(self, customer_id: str, receipts_delta: int = 0, 
                                     spent_delta: float = 0, wins_delta: int = 0, 
                                     winnings_delta: float = 0):
        """Update customer statistics"""
        # Get current values first
        result = self.client.table('customers').select('total_receipts, total_spent, total_wins, total_winnings').eq('id', customer_id).single().execute()
        if result.data:
            current = result.data
            self.client.table('customers').update({
                'total_receipts': current['total_receipts'] + receipts_delta,
                'total_spent': float(current['total_spent'] or 0) + spent_delta,
                'total_wins': current['total_wins'] + wins_delta,
                'total_winnings': float(current['total_winnings'] or 0) + winnings_delta
            }).eq('id', customer_id).execute()
    
    async def update_customer_location(self, phone_number: str, latitude: float, longitude: float):
        """Update customer's last known location"""
        self.client.table('customers').update({
            'last_latitude': latitude,
            'last_longitude': longitude,
            'location_updated_at': datetime.now(timezone.utc).isoformat()
        }).eq('phone_number', phone_number).execute()
    
    async def list_customers(self, skip: int = 0, limit: int = 50) -> Dict:
        """List customers with pagination"""
        result = self.client.table('customers').select('*', count='exact').order('created_at', desc=True).range(skip, skip + limit - 1).execute()
        return {'customers': result.data, 'total': result.count}
    
    # ==================== SHOPS ====================
    
    async def get_shop_by_name(self, name: str) -> Optional[Dict]:
        """Get shop by name (case insensitive)"""
        try:
            result = self.client.table('shops').select('*').ilike('name', name).single().execute()
            return result.data
        except Exception as e:
            if 'No rows' in str(e) or 'PGRST116' in str(e):
                return None
            logger.error(f"Error getting shop: {e}")
            return None
    
    async def create_shop(self, name: str, address: Optional[str] = None, 
                          latitude: Optional[float] = None, longitude: Optional[float] = None) -> Dict:
        """Create a new shop"""
        shop_data = {
            'id': str(uuid.uuid4()),
            'name': name,
            'address': address,
            'latitude': latitude,
            'longitude': longitude,
            'receipt_count': 0,
            'total_sales': 0.0
        }
        result = self.client.table('shops').insert(shop_data).execute()
        return result.data[0] if result.data else shop_data
    
    async def get_or_create_shop(self, name: str, address: Optional[str] = None,
                                  latitude: Optional[float] = None, longitude: Optional[float] = None) -> Dict:
        """Get existing shop or create new one"""
        shop = await self.get_shop_by_name(name)
        if not shop:
            shop = await self.create_shop(name, address, latitude, longitude)
        return shop
    
    async def update_shop_stats(self, shop_id: str, receipts_delta: int = 0, sales_delta: float = 0):
        """Update shop statistics"""
        result = self.client.table('shops').select('receipt_count, total_sales').eq('id', shop_id).single().execute()
        if result.data:
            current = result.data
            self.client.table('shops').update({
                'receipt_count': current['receipt_count'] + receipts_delta,
                'total_sales': float(current['total_sales'] or 0) + sales_delta
            }).eq('id', shop_id).execute()
    
    async def update_shop_geocoding(self, shop_id: str, latitude: float, longitude: float,
                                     geocoded_address: str, confidence: str):
        """Update shop geocoding data"""
        self.client.table('shops').update({
            'latitude': latitude,
            'longitude': longitude,
            'geocoded_address': geocoded_address,
            'geocode_confidence': confidence,
            'geocoded_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', shop_id).execute()
    
    async def list_shops(self, skip: int = 0, limit: int = 100) -> Dict:
        """List shops with pagination"""
        result = self.client.table('shops').select('*', count='exact').order('receipt_count', desc=True).range(skip, skip + limit - 1).execute()
        return {'shops': result.data, 'total': result.count}
    
    async def get_shop(self, shop_id: str) -> Optional[Dict]:
        """Get shop by ID"""
        try:
            result = self.client.table('shops').select('*').eq('id', shop_id).single().execute()
            return result.data
        except:
            return None
    
    async def get_shops_without_coords(self, limit: int = 50) -> List[Dict]:
        """Get shops without geocoding"""
        result = self.client.table('shops').select('*').is_('latitude', 'null').limit(limit).execute()
        return result.data
    
    async def get_map_shops(self) -> List[Dict]:
        """Get all shops with coordinates for map display"""
        result = self.client.table('shops').select('*').not_.is_('latitude', 'null').not_.is_('longitude', 'null').execute()
        return result.data
    
    # ==================== RECEIPTS ====================
    
    async def create_receipt(self, receipt_data: Dict) -> Dict:
        """Create a new receipt"""
        if 'id' not in receipt_data:
            receipt_data['id'] = str(uuid.uuid4())
        
        # Extract items for separate table
        items = receipt_data.pop('items', [])
        
        # Insert receipt
        result = self.client.table('receipts').insert(receipt_data).execute()
        receipt = result.data[0] if result.data else receipt_data
        
        # Insert items
        if items:
            items_data = [
                {
                    'id': str(uuid.uuid4()),
                    'receipt_id': receipt['id'],
                    'name': item.get('name', ''),
                    'quantity': item.get('quantity', 1),
                    'unit_price': item.get('unit_price'),
                    'total_price': item.get('total_price') or item.get('price')
                }
                for item in items
            ]
            self.client.table('receipt_items').insert(items_data).execute()
        
        receipt['items'] = items
        return receipt
    
    async def get_receipt(self, receipt_id: str, include_image: bool = False) -> Optional[Dict]:
        """Get receipt by ID"""
        try:
            columns = '*' if include_image else '*, !image_url'  # Adjust based on needs
            result = self.client.table('receipts').select('*').eq('id', receipt_id).single().execute()
            receipt = result.data
            
            if receipt:
                # Get items
                items_result = self.client.table('receipt_items').select('*').eq('receipt_id', receipt_id).execute()
                receipt['items'] = items_result.data
            
            return receipt
        except:
            return None
    
    async def get_receipt_full(self, receipt_id: str) -> Optional[Dict]:
        """Get full receipt with customer and shop info"""
        receipt = await self.get_receipt(receipt_id, include_image=True)
        if not receipt:
            return None
        
        customer = await self.get_customer(receipt['customer_phone'])
        shop = await self.get_shop(receipt['shop_id']) if receipt.get('shop_id') else None
        
        return {
            'receipt': receipt,
            'customer': customer,
            'shop': shop
        }
    
    async def get_customer_receipts(self, phone_number: str, skip: int = 0, limit: int = 50) -> Dict:
        """Get receipts for a customer"""
        result = self.client.table('receipts').select('*, receipt_items(*)', count='exact').eq('customer_phone', phone_number).order('created_at', desc=True).range(skip, skip + limit - 1).execute()
        
        # Format response
        receipts = []
        for r in result.data:
            r['items'] = r.pop('receipt_items', [])
            r['has_image'] = bool(r.get('image_url'))
            receipts.append(r)
        
        return {'receipts': receipts, 'total': result.count}
    
    async def list_receipts(self, skip: int = 0, limit: int = 50, 
                            date: Optional[str] = None, status: Optional[str] = None,
                            fraud_flag: Optional[str] = None) -> Dict:
        """List receipts with filters"""
        query = self.client.table('receipts').select('*', count='exact')
        
        if date:
            query = query.gte('created_at', f"{date}T00:00:00").lte('created_at', f"{date}T23:59:59")
        if status:
            query = query.eq('status', status)
        if fraud_flag:
            query = query.eq('fraud_flag', fraud_flag)
        
        result = query.order('created_at', desc=True).range(skip, skip + limit - 1).execute()
        
        receipts = []
        for r in result.data:
            r['has_image'] = bool(r.get('image_url'))
            receipts.append(r)
        
        return {'receipts': receipts, 'total': result.count}
    
    async def update_receipt_status(self, receipt_id: str, status: str, fraud_flag: Optional[str] = None,
                                     fraud_reason: Optional[str] = None):
        """Update receipt status"""
        update_data = {'status': status}
        if fraud_flag:
            update_data['fraud_flag'] = fraud_flag
        if fraud_reason:
            update_data['fraud_reason'] = fraud_reason
        
        self.client.table('receipts').update(update_data).eq('id', receipt_id).execute()
    
    async def get_flagged_receipts(self, skip: int = 0, limit: int = 50) -> Dict:
        """Get receipts flagged for review"""
        result = self.client.table('receipts').select('*', count='exact').in_('fraud_flag', ['review', 'suspicious', 'flagged']).order('fraud_score', desc=True).range(skip, skip + limit - 1).execute()
        
        receipts = []
        for r in result.data:
            r['has_image'] = bool(r.get('image_url'))
            receipts.append(r)
        
        return {'receipts': receipts, 'total': result.count}
    
    async def get_receipts_for_draw(self, draw_date: str) -> List[Dict]:
        """Get all receipts eligible for a draw date"""
        result = self.client.table('receipts').select('*').gte('created_at', f"{draw_date}T00:00:00").lte('created_at', f"{draw_date}T23:59:59").neq('status', 'won').neq('status', 'rejected').eq('fraud_flag', 'valid').execute()
        return result.data
    
    async def get_map_receipts(self, date: Optional[str] = None) -> List[Dict]:
        """Get receipt locations for map display"""
        query = self.client.table('receipts').select('id, customer_phone, shop_name, amount, upload_latitude, upload_longitude, created_at').not_.is_('upload_latitude', 'null').not_.is_('upload_longitude', 'null')
        
        if date:
            query = query.gte('created_at', f"{date}T00:00:00").lte('created_at', f"{date}T23:59:59")
        
        result = query.execute()
        return result.data
    
    # ==================== DRAWS ====================
    
    async def get_draw(self, draw_date: str) -> Optional[Dict]:
        """Get draw by date"""
        try:
            result = self.client.table('draws').select('*').eq('draw_date', draw_date).single().execute()
            return result.data
        except:
            return None
    
    async def create_draw(self, draw_data: Dict) -> Dict:
        """Create a new draw record"""
        if 'id' not in draw_data:
            draw_data['id'] = str(uuid.uuid4())
        
        result = self.client.table('draws').insert(draw_data).execute()
        return result.data[0] if result.data else draw_data
    
    async def list_draws(self, skip: int = 0, limit: int = 30) -> Dict:
        """List draws with pagination"""
        result = self.client.table('draws').select('*', count='exact').order('draw_date', desc=True).range(skip, skip + limit - 1).execute()
        return {'draws': result.data, 'total': result.count}
    
    async def get_customer_wins(self, phone_number: str) -> Dict:
        """Get all wins for a customer"""
        result = self.client.table('draws').select('*').eq('winner_customer_phone', phone_number).order('draw_date', desc=True).execute()
        return {'wins': result.data, 'total': len(result.data)}
    
    # ==================== ANALYTICS ====================
    
    async def get_analytics_overview(self) -> Dict:
        """Get platform overview statistics"""
        customers = self.client.table('customers').select('*', count='exact').execute()
        receipts = self.client.table('receipts').select('*', count='exact').execute()
        shops = self.client.table('shops').select('*', count='exact').execute()
        draws = self.client.table('draws').select('*', count='exact').eq('status', 'completed').execute()
        
        # Get totals
        totals = self.client.table('customers').select('total_spent.sum(), total_winnings.sum()').execute()
        total_data = totals.data[0] if totals.data else {}
        
        return {
            'total_customers': customers.count,
            'total_receipts': receipts.count,
            'total_shops': shops.count,
            'total_draws': draws.count,
            'total_spent': float(total_data.get('sum', 0) or 0),
            'total_winnings': float(total_data.get('sum', 0) or 0)
        }
    
    async def get_spending_by_day(self, days: int = 30) -> List[Dict]:
        """Get daily spending for analytics"""
        result = self.client.rpc('get_daily_spending', {'days_count': days}).execute()
        return result.data if result.data else []
    
    async def get_popular_shops(self, limit: int = 10) -> List[Dict]:
        """Get most popular shops"""
        result = self.client.table('shops').select('*').order('receipt_count', desc=True).limit(limit).execute()
        return result.data
    
    async def get_top_spenders(self, limit: int = 10) -> List[Dict]:
        """Get top spending customers"""
        result = self.client.table('customers').select('*').order('total_spent', desc=True).limit(limit).execute()
        return result.data
    
    async def get_fraud_stats(self) -> Dict:
        """Get fraud detection statistics"""
        total = self.client.table('receipts').select('*', count='exact').execute().count
        valid = self.client.table('receipts').select('*', count='exact').eq('fraud_flag', 'valid').execute().count
        review = self.client.table('receipts').select('*', count='exact').eq('fraud_flag', 'review').execute().count
        suspicious = self.client.table('receipts').select('*', count='exact').eq('fraud_flag', 'suspicious').execute().count
        flagged = self.client.table('receipts').select('*', count='exact').eq('fraud_flag', 'flagged').execute().count
        
        return {
            'total_receipts': total,
            'valid': valid,
            'review': review,
            'suspicious': suspicious,
            'flagged': flagged,
            'fraud_rate': round((review + suspicious + flagged) / total * 100, 2) if total > 0 else 0
        }
    
    async def get_geocoding_stats(self) -> Dict:
        """Get geocoding statistics"""
        total = self.client.table('shops').select('*', count='exact').execute().count
        geocoded = self.client.table('shops').select('*', count='exact').not_.is_('latitude', 'null').execute().count
        
        return {
            'total_shops': total,
            'geocoded': geocoded,
            'not_geocoded': total - geocoded,
            'geocoded_percentage': round(geocoded / total * 100, 1) if total > 0 else 0
        }
    
    # ==================== STORAGE ====================
    
    async def upload_receipt_image(self, receipt_id: str, image_bytes: bytes, 
                                    content_type: str = 'image/jpeg') -> Optional[str]:
        """Upload receipt image to Supabase Storage"""
        try:
            file_path = f"receipts/{receipt_id}.jpg"
            
            # Upload to storage
            self.client.storage.from_('receipts').upload(
                file_path,
                image_bytes,
                file_options={"content-type": content_type}
            )
            
            # Get public URL
            url = self.client.storage.from_('receipts').get_public_url(file_path)
            
            # Update receipt with image URL
            self.client.table('receipts').update({
                'image_url': url,
                'image_path': file_path
            }).eq('id', receipt_id).execute()
            
            return url
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            return None
    
    async def get_receipt_image_url(self, receipt_id: str) -> Optional[str]:
        """Get the image URL for a receipt"""
        try:
            result = self.client.table('receipts').select('image_url').eq('id', receipt_id).single().execute()
            return result.data.get('image_url') if result.data else None
        except:
            return None


# Singleton instance
_db: Optional[SupabaseDB] = None

def get_db() -> SupabaseDB:
    """Get or create the database singleton"""
    global _db
    if _db is None:
        _db = SupabaseDB()
    return _db
