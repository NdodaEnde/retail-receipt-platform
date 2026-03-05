"""
Supabase Storage Helper
Handles receipt image uploads and retrieval
"""

import os
import logging
import base64
from typing import Optional, Tuple
from supabase import create_client, Client

logger = logging.getLogger(__name__)

BUCKET_NAME = 'receipts'


class StorageHelper:
    """
    Helper class for Supabase Storage operations
    """
    
    def __init__(self):
        self.url = os.environ.get('SUPABASE_URL', '')
        self.key = os.environ.get('SUPABASE_KEY', '')
        self.client: Optional[Client] = None
        
        if self.url and self.key:
            try:
                self.client = create_client(self.url, self.key)
                logger.info("✅ Supabase Storage initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Supabase Storage: {e}")
    
    def upload_image(self, receipt_id: str, image_base64: str, 
                     mime_type: str = 'image/jpeg') -> Tuple[Optional[str], Optional[str]]:
        """
        Upload a base64 image to Supabase Storage
        
        Returns:
            Tuple of (public_url, file_path) or (None, None) on failure
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            return None, None
        
        try:
            # Decode base64
            if ',' in image_base64:
                image_base64 = image_base64.split(',')[1]
            
            image_bytes = base64.b64decode(image_base64)
            
            # Determine extension
            ext = 'jpg'
            if 'png' in mime_type:
                ext = 'png'
            elif 'webp' in mime_type:
                ext = 'webp'
            
            file_path = f"{receipt_id}.{ext}"
            
            # Upload to bucket
            result = self.client.storage.from_(BUCKET_NAME).upload(
                path=file_path,
                file=image_bytes,
                file_options={"content-type": mime_type, "upsert": "true"}
            )
            
            # Get public URL
            public_url = self.client.storage.from_(BUCKET_NAME).get_public_url(file_path)
            
            logger.info(f"✅ Uploaded image: {file_path}")
            return public_url, file_path
            
        except Exception as e:
            logger.error(f"❌ Failed to upload image: {e}")
            return None, None
    
    def get_image_url(self, file_path: str) -> Optional[str]:
        """Get public URL for an image"""
        if not self.client or not file_path:
            return None
        
        try:
            return self.client.storage.from_(BUCKET_NAME).get_public_url(file_path)
        except Exception as e:
            logger.error(f"Failed to get image URL: {e}")
            return None
    
    def delete_image(self, file_path: str) -> bool:
        """Delete an image from storage"""
        if not self.client or not file_path:
            return False
        
        try:
            self.client.storage.from_(BUCKET_NAME).remove([file_path])
            logger.info(f"Deleted image: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete image: {e}")
            return False
    
    def download_image(self, file_path: str) -> Optional[bytes]:
        """Download an image as bytes"""
        if not self.client or not file_path:
            return None
        
        try:
            return self.client.storage.from_(BUCKET_NAME).download(file_path)
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            return None


# Singleton
_storage: Optional[StorageHelper] = None

def get_storage() -> StorageHelper:
    """Get or create storage helper singleton"""
    global _storage
    if _storage is None:
        _storage = StorageHelper()
    return _storage
