"""
Database Abstraction Layer
Provides a unified interface for database operations
Currently supports: Supabase (PostgreSQL)
"""

import os
import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class Database:
    """
    Database abstraction layer using Supabase
    """
    
    def __init__(self):
        self.url = os.environ.get('SUPABASE_URL', '')
        self.key = os.environ.get('SUPABASE_KEY', '')
        self.client: Optional[Client] = None
        
        if self.url and self.key:
            try:
                self.client = create_client(self.url, self.key)
                logger.info("✅ Database connected (Supabase)")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Supabase: {e}")
        else:
            logger.warning("⚠️ Database credentials not configured")
    
    def _safe_get(self, result, default=None):
        """Safely extract data from Supabase response"""
        if result and result.data:
            return result.data
        return default
    
    # ==================== CUSTOMERS ====================
    
    async def customers_find_one(self, filter: Dict) -> Optional[Dict]:
        """Find a single customer"""
        try:
            query = self.client.table('customers').select('*')
            for key, value in filter.items():
                query = query.eq(key, value)
            result = query.limit(1).execute()
            data = self._safe_get(result, [])
            return data[0] if data else None
        except Exception as e:
            logger.error(f"customers_find_one error: {e}")
            return None
    
    async def customers_insert_one(self, doc: Dict) -> Dict:
        """Insert a new customer"""
        if 'id' not in doc:
            doc['id'] = str(uuid.uuid4())
        if 'created_at' not in doc:
            doc['created_at'] = datetime.now(timezone.utc).isoformat()
        
        result = self.client.table('customers').insert(doc).execute()
        return self._safe_get(result, [doc])[0]
    
    async def customers_update_one(self, filter: Dict, update: Dict):
        """Update a customer"""
        # Extract $set, $inc operations
        set_data = update.get('$set', {})
        inc_data = update.get('$inc', {})
        
        if inc_data:
            # Need to fetch current values for increment
            current = await self.customers_find_one(filter)
            if current:
                for key, delta in inc_data.items():
                    current_val = current.get(key, 0) or 0
                    new_val = current_val + delta
                    set_data[key] = int(new_val) if isinstance(delta, int) and isinstance(current_val, int) else new_val
        
        if set_data:
            query = self.client.table('customers').update(set_data)
            for key, value in filter.items():
                query = query.eq(key, value)
            query.execute()
    
    async def customers_find(self, filter: Dict = None, projection: Dict = None, 
                            sort: tuple = None, skip: int = 0, limit: int = 50) -> List[Dict]:
        """Find multiple customers"""
        query = self.client.table('customers').select('*')
        
        if filter:
            for key, value in filter.items():
                query = query.eq(key, value)
        
        if sort:
            field, direction = sort
            query = query.order(field, desc=(direction == -1))
        
        query = query.range(skip, skip + limit - 1)
        result = query.execute()
        return self._safe_get(result, [])
    
    async def customers_count(self, filter: Dict = None) -> int:
        """Count customers"""
        query = self.client.table('customers').select('*', count='exact')
        if filter:
            for key, value in filter.items():
                query = query.eq(key, value)
        result = query.execute()
        return result.count or 0
    
    async def customers_delete_many(self, filter: Dict = None):
        """Delete customers"""
        if filter is None or filter == {}:
            # Delete all
            self.client.table('customers').delete().neq('id', '').execute()
        else:
            query = self.client.table('customers').delete()
            for key, value in filter.items():
                query = query.eq(key, value)
            query.execute()
    
    # ==================== SHOPS ====================
    
    async def shops_find_one(self, filter: Dict) -> Optional[Dict]:
        """Find a single shop"""
        try:
            query = self.client.table('shops').select('*')
            
            for key, value in filter.items():
                if key == 'name' and isinstance(value, dict) and '$regex' in value:
                    # Handle case-insensitive name search
                    pattern = value['$regex'].replace('^', '').replace('$', '')
                    query = query.ilike('name', pattern)
                elif key == 'latitude' and isinstance(value, dict):
                    # Handle existence check
                    if '$ne' in value or '$exists' in value:
                        query = query.not_.is_('latitude', 'null')
                else:
                    query = query.eq(key, value)
            
            result = query.limit(1).execute()
            data = self._safe_get(result, [])
            return data[0] if data else None
        except Exception as e:
            logger.error(f"shops_find_one error: {e}")
            return None
    
    async def shops_insert_one(self, doc: Dict) -> Dict:
        """Insert a new shop"""
        if 'id' not in doc:
            doc['id'] = str(uuid.uuid4())
        if 'created_at' not in doc:
            doc['created_at'] = datetime.now(timezone.utc).isoformat()
        
        result = self.client.table('shops').insert(doc).execute()
        return self._safe_get(result, [doc])[0]
    
    async def shops_update_one(self, filter: Dict, update: Dict):
        """Update a shop"""
        set_data = update.get('$set', {})
        inc_data = update.get('$inc', {})
        
        if inc_data:
            current = await self.shops_find_one(filter)
            if current:
                for key, delta in inc_data.items():
                    current_val = current.get(key, 0) or 0
                    new_val = current_val + delta
                    set_data[key] = int(new_val) if isinstance(delta, int) and isinstance(current_val, int) else new_val
        
        if set_data:
            query = self.client.table('shops').update(set_data)
            for key, value in filter.items():
                query = query.eq(key, value)
            query.execute()
    
    async def shops_find(self, filter: Dict = None, projection: Dict = None,
                         sort: tuple = None, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Find multiple shops"""
        query = self.client.table('shops').select('*')
        
        if filter:
            for key, value in filter.items():
                if isinstance(value, dict):
                    if '$ne' in value:
                        query = query.neq(key, value['$ne'])
                    elif '$exists' in value and value['$exists']:
                        query = query.not_.is_(key, 'null')
                else:
                    query = query.eq(key, value)
        
        if sort:
            field, direction = sort
            query = query.order(field, desc=(direction == -1))
        
        query = query.range(skip, skip + limit - 1)
        result = query.execute()
        return self._safe_get(result, [])
    
    async def shops_count(self, filter: Dict = None) -> int:
        """Count shops"""
        query = self.client.table('shops').select('*', count='exact')
        if filter:
            for key, value in filter.items():
                if isinstance(value, dict):
                    if '$ne' in value:
                        query = query.neq(key, value['$ne'])
                    elif '$exists' in value and value['$exists']:
                        query = query.not_.is_(key, 'null')
                    elif '$in' in value:
                        query = query.in_(key, value['$in'])
                else:
                    query = query.eq(key, value)
        result = query.execute()
        return result.count or 0
    
    async def shops_delete_many(self, filter: Dict = None):
        """Delete shops"""
        if filter is None or filter == {}:
            self.client.table('shops').delete().neq('id', '').execute()
        else:
            query = self.client.table('shops').delete()
            for key, value in filter.items():
                query = query.eq(key, value)
            query.execute()
    
    # ==================== RECEIPTS ====================
    
    async def receipts_find_one(self, filter: Dict, projection: Dict = None) -> Optional[Dict]:
        """Find a single receipt"""
        try:
            # Determine what to select based on projection
            select_fields = '*'
            if projection:
                # If image_data/image_url is excluded, still select all (handled in response)
                pass
            
            query = self.client.table('receipts').select(select_fields)
            for key, value in filter.items():
                query = query.eq(key, value)
            
            result = query.limit(1).execute()
            data = self._safe_get(result, [])
            receipt = data[0] if data else None
            
            if receipt:
                # Fetch items
                items_result = self.client.table('receipt_items').select('*').eq('receipt_id', receipt['id']).execute()
                receipt['items'] = self._safe_get(items_result, [])
            
            return receipt
        except Exception as e:
            logger.error(f"receipts_find_one error: {e}")
            return None
    
    async def receipts_insert_one(self, doc: Dict) -> Dict:
        """Insert a new receipt"""
        if 'id' not in doc:
            doc['id'] = str(uuid.uuid4())
        if 'created_at' not in doc:
            doc['created_at'] = datetime.now(timezone.utc).isoformat()
        
        # Extract items for separate table
        items = doc.pop('items', [])
        
        # Handle image_data -> image will be stored separately later
        # For now, we don't store base64 in the database
        doc.pop('image_data', None)
        
        result = self.client.table('receipts').insert(doc).execute()
        receipt = self._safe_get(result, [doc])[0]
        
        # Insert items
        if items:
            items_data = []
            for item in items:
                items_data.append({
                    'id': str(uuid.uuid4()),
                    'receipt_id': receipt['id'],
                    'name': item.get('name', ''),
                    'quantity': item.get('quantity', 1),
                    'unit_price': item.get('unit_price'),
                    'total_price': item.get('total_price') or item.get('price')
                })
            if items_data:
                self.client.table('receipt_items').insert(items_data).execute()
        
        receipt['items'] = items
        return receipt
    
    async def receipts_update_one(self, filter: Dict, update: Dict):
        """Update a receipt"""
        set_data = update.get('$set', {})
        inc_data = update.get('$inc', {})
        
        if inc_data:
            current = await self.receipts_find_one(filter)
            if current:
                for key, delta in inc_data.items():
                    current_val = current.get(key, 0) or 0
                    new_val = current_val + delta
                    set_data[key] = int(new_val) if isinstance(delta, int) and isinstance(current_val, int) else new_val
        
        if set_data:
            query = self.client.table('receipts').update(set_data)
            for key, value in filter.items():
                query = query.eq(key, value)
            query.execute()
    
    async def receipts_find(self, filter: Dict = None, projection: Dict = None,
                           sort: tuple = None, skip: int = 0, limit: int = 50) -> List[Dict]:
        """Find multiple receipts"""
        query = self.client.table('receipts').select('*')
        
        if filter:
            for key, value in filter.items():
                if key == 'created_at' and isinstance(value, dict):
                    if '$gte' in value:
                        query = query.gte('created_at', value['$gte'])
                    if '$lte' in value:
                        query = query.lte('created_at', value['$lte'])
                elif key == 'status' and isinstance(value, dict) and '$ne' in value:
                    query = query.neq('status', value['$ne'])
                elif key == 'fraud_flag' and isinstance(value, dict) and '$in' in value:
                    query = query.in_('fraud_flag', value['$in'])
                elif isinstance(value, dict) and '$ne' in value:
                    query = query.neq(key, value['$ne'])
                else:
                    query = query.eq(key, value)
        
        if sort:
            field, direction = sort
            query = query.order(field, desc=(direction == -1))
        
        query = query.range(skip, skip + limit - 1)
        result = query.execute()
        receipts = self._safe_get(result, [])
        
        # Add has_image flag
        for r in receipts:
            r['has_image'] = bool(r.get('image_url'))
        
        return receipts
    
    async def receipts_count(self, filter: Dict = None) -> int:
        """Count receipts"""
        query = self.client.table('receipts').select('*', count='exact')
        if filter:
            for key, value in filter.items():
                if isinstance(value, dict):
                    if '$gte' in value:
                        query = query.gte(key, value['$gte'])
                    if '$lte' in value:
                        query = query.lte(key, value['$lte'])
                    if '$ne' in value:
                        query = query.neq(key, value['$ne'])
                    if '$in' in value:
                        query = query.in_(key, value['$in'])
                else:
                    query = query.eq(key, value)
        result = query.execute()
        return result.count or 0
    
    async def receipts_delete_many(self, filter: Dict = None):
        """Delete receipts"""
        if filter is None or filter == {}:
            self.client.table('receipt_items').delete().neq('id', '').execute()
            self.client.table('receipts').delete().neq('id', '').execute()
        else:
            query = self.client.table('receipts').delete()
            for key, value in filter.items():
                query = query.eq(key, value)
            query.execute()
    
    # ==================== DRAWS ====================
    
    async def draws_find_one(self, filter: Dict) -> Optional[Dict]:
        """Find a single draw"""
        try:
            query = self.client.table('draws').select('*')
            for key, value in filter.items():
                query = query.eq(key, value)
            result = query.limit(1).execute()
            data = self._safe_get(result, [])
            return data[0] if data else None
        except Exception as e:
            logger.error(f"draws_find_one error: {e}")
            return None
    
    async def draws_insert_one(self, doc: Dict) -> Dict:
        """Insert a new draw"""
        if 'id' not in doc:
            doc['id'] = str(uuid.uuid4())
        if 'created_at' not in doc:
            doc['created_at'] = datetime.now(timezone.utc).isoformat()
        
        result = self.client.table('draws').insert(doc).execute()
        return self._safe_get(result, [doc])[0]
    
    async def draws_find(self, filter: Dict = None, projection: Dict = None,
                        sort: tuple = None, skip: int = 0, limit: int = 30) -> List[Dict]:
        """Find multiple draws"""
        query = self.client.table('draws').select('*')
        
        if filter:
            for key, value in filter.items():
                query = query.eq(key, value)
        
        if sort:
            field, direction = sort
            query = query.order(field, desc=(direction == -1))
        
        query = query.range(skip, skip + limit - 1)
        result = query.execute()
        return self._safe_get(result, [])
    
    async def draws_count(self, filter: Dict = None) -> int:
        """Count draws"""
        query = self.client.table('draws').select('*', count='exact')
        if filter:
            for key, value in filter.items():
                query = query.eq(key, value)
        result = query.execute()
        return result.count or 0
    
    async def draws_delete_many(self, filter: Dict = None):
        """Delete draws"""
        if filter is None or filter == {}:
            self.client.table('draws').delete().neq('id', '').execute()
        else:
            query = self.client.table('draws').delete()
            for key, value in filter.items():
                query = query.eq(key, value)
            query.execute()
    
    # ==================== AGGREGATIONS ====================
    
    async def receipts_aggregate_sum(self, field: str) -> float:
        """Sum a field across all receipts"""
        result = self.client.table('receipts').select(field).execute()
        data = self._safe_get(result, [])
        return sum(float(r.get(field, 0) or 0) for r in data)
    
    async def customers_aggregate_sum(self, field: str) -> float:
        """Sum a field across all customers"""
        result = self.client.table('customers').select(field).execute()
        data = self._safe_get(result, [])
        return sum(float(r.get(field, 0) or 0) for r in data)
    
    async def get_daily_spending(self, days: int = 30) -> List[Dict]:
        """Get daily spending summary"""
        # Use SQL view or raw query
        result = self.client.table('daily_spending').select('*').limit(days).execute()
        return self._safe_get(result, [])
    
    async def get_hourly_distribution(self) -> List[Dict]:
        """Get hourly receipt distribution"""
        result = self.client.table('hourly_distribution').select('*').execute()
        return self._safe_get(result, [])
    
    # ==================== PENDING STATE (write-through cache) ====================

    async def pending_state_upsert(self, state_type: str, phone_number: str, data: dict, ttl_minutes: int = 15):
        """Upsert a pending state record (replace if exists for same type+phone)"""
        try:
            expires_at = (datetime.now(timezone.utc) + __import__('datetime').timedelta(minutes=ttl_minutes)).isoformat()
            # Delete existing first (upsert by type+phone)
            self.client.table('pending_state').delete().eq('state_type', state_type).eq('phone_number', phone_number).execute()
            # Insert new
            import json as _json
            self.client.table('pending_state').insert({
                'id': str(uuid.uuid4()),
                'state_type': state_type,
                'phone_number': phone_number,
                'data': _json.loads(_json.dumps(data, default=str)),
                'expires_at': expires_at
            }).execute()
        except Exception as e:
            logger.error(f"pending_state_upsert error: {e}")

    async def pending_state_get(self, state_type: str, phone_number: str) -> Optional[Dict]:
        """Get a pending state record (returns data JSONB or None)"""
        try:
            result = self.client.table('pending_state').select('data').eq(
                'state_type', state_type
            ).eq('phone_number', phone_number).gt(
                'expires_at', datetime.now(timezone.utc).isoformat()
            ).limit(1).execute()
            data = self._safe_get(result, [])
            return data[0]['data'] if data else None
        except Exception as e:
            logger.error(f"pending_state_get error: {e}")
            return None

    async def pending_state_delete(self, state_type: str, phone_number: str):
        """Delete a pending state record"""
        try:
            self.client.table('pending_state').delete().eq(
                'state_type', state_type
            ).eq('phone_number', phone_number).execute()
        except Exception as e:
            logger.error(f"pending_state_delete error: {e}")

    async def pending_state_cleanup(self):
        """Delete all expired pending state records"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            self.client.table('pending_state').delete().lt('expires_at', now).execute()
            logger.info("Cleaned up expired pending state records")
        except Exception as e:
            logger.error(f"pending_state_cleanup error: {e}")

    # ==================== BASKET ANALYTICS (SQL views) ====================

    async def get_top_items(self, limit: int = 20) -> List[Dict]:
        """Get top items by frequency from top_items view"""
        result = self.client.table('top_items').select('*').limit(limit).execute()
        return self._safe_get(result, [])

    async def get_item_pairs(self, limit: int = 20) -> List[Dict]:
        """Get frequently bought together item pairs from item_pairs view"""
        result = self.client.table('item_pairs').select('*').limit(limit).execute()
        return self._safe_get(result, [])

    async def get_basket_stats(self) -> List[Dict]:
        """Get basket size stats from basket_stats view"""
        result = self.client.table('basket_stats').select('*').limit(1000).execute()
        return self._safe_get(result, [])

    async def get_customer_behavior(self, limit: int = 50) -> List[Dict]:
        """Get customer shopping behavior from customer_behavior view"""
        result = self.client.table('customer_behavior').select('*').order(
            'total_spent', desc=True
        ).limit(limit).execute()
        return self._safe_get(result, [])

    # ==================== IMAGE STORAGE ====================
    
    async def upload_receipt_image(self, receipt_id: str, image_base64: str,
                                    mime_type: str = 'image/jpeg') -> Optional[str]:
        """Upload receipt image to storage"""
        try:
            import base64
            
            # Decode base64
            if ',' in image_base64:
                image_base64 = image_base64.split(',')[1]
            
            image_bytes = base64.b64decode(image_base64)
            file_path = f"{receipt_id}.jpg"
            
            # Upload to storage
            self.client.storage.from_('receipts').upload(
                path=file_path,
                file=image_bytes,
                file_options={"content-type": mime_type, "upsert": "true"}
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
        """Get image URL for a receipt"""
        try:
            result = self.client.table('receipts').select('image_url').eq('id', receipt_id).single().execute()
            return result.data.get('image_url') if result.data else None
        except Exception:
            return None


# Singleton instance
_database: Optional[Database] = None

def get_database() -> Database:
    """Get or create database singleton"""
    global _database
    if _database is None:
        _database = Database()
    return _database
