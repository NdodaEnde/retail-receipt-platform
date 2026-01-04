"""
Receipt Processor using LandingAI ADE
Extracts structured data from receipt images with grounding boxes
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import re
import base64
import tempfile

logger = logging.getLogger(__name__)

# Try to import landingai_ade
try:
    from landingai_ade import LandingAIADE
    LANDINGAI_AVAILABLE = True
    logger.info("✅ LandingAI ADE available")
except ImportError:
    LANDINGAI_AVAILABLE = False
    logger.warning("⚠️ landingai-ade not installed. Using fallback parser.")


class ReceiptProcessor:
    """
    Receipt processor using LandingAI ADE for extraction with grounding
    Extracts: shop name, address, items, total amount, date
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('LANDINGAI_API_KEY', '')
        self.client = None
        
        if LANDINGAI_AVAILABLE and self.api_key:
            try:
                self.client = LandingAIADE()
                logger.info("✅ Receipt Processor initialized with LandingAI ADE")
            except Exception as e:
                logger.error(f"❌ Failed to initialize LandingAI ADE: {e}")
                self.client = None
        else:
            logger.info("📝 Receipt Processor initialized (fallback mode)")

    def process_receipt_image(self, image_base64: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """
        Process a receipt image and extract structured data
        
        Args:
            image_base64: Base64 encoded image data
            mime_type: Image MIME type (image/jpeg, image/png, etc.)
            
        Returns:
            Dictionary with extracted data:
            {
                "success": bool,
                "shop_name": str,
                "shop_address": str,
                "amount": float,
                "currency": str,
                "items": [{"name": str, "price": float, "quantity": int}],
                "date": str,
                "raw_text": str,
                "grounding": {...},  # Bounding boxes for visual proof
                "chunks": [...],     # Raw chunks from LandingAI
                "error": str (if failed)
            }
        """
        result = {
            "success": False,
            "shop_name": None,
            "shop_address": None,
            "amount": 0.0,
            "currency": "ZAR",
            "items": [],
            "date": None,
            "raw_text": "",
            "grounding": {},
            "chunks": [],
            "error": None
        }

        try:
            if self.client:
                # Use LandingAI ADE for extraction
                result = self._process_with_landingai(image_base64, mime_type, result)
            else:
                # Use fallback parser
                result["error"] = "LandingAI not configured - manual entry required"
                result["success"] = True  # Allow manual entry
                
        except Exception as e:
            logger.error(f"❌ Receipt processing error: {e}")
            result["error"] = str(e)

        return result

    def _process_with_landingai(self, image_base64: str, mime_type: str, result: Dict) -> Dict:
        """Process receipt using LandingAI ADE"""
        
        start_time = datetime.utcnow()
        
        # Save image to temp file (LandingAI needs file path)
        suffix = ".jpg" if "jpeg" in mime_type else ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            tmp_file.write(base64.b64decode(image_base64))
            tmp_path = tmp_file.name

        try:
            # Parse with LandingAI ADE
            response = self.client.parse(
                document=Path(tmp_path),
                model="dpt-2-latest"
            )

            if not response or not response.chunks:
                result["error"] = "No data extracted from receipt"
                return result

            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ LandingAI extraction complete in {processing_time:.2f}s")

            # Extract chunks with grounding
            chunks = []
            all_text = []
            grounding_data = {}

            for i, chunk in enumerate(response.chunks):
                chunk_data = chunk.model_dump() if hasattr(chunk, 'model_dump') else dict(chunk)
                chunks.append(chunk_data)
                
                # Get text content
                text = chunk_data.get('markdown', '') or chunk_data.get('text', '')
                if text:
                    all_text.append(text)
                
                # Store grounding info
                grounding = chunk_data.get('grounding', {})
                if grounding:
                    chunk_id = chunk_data.get('id', f'chunk_{i}')
                    grounding_data[chunk_id] = {
                        'page': grounding.get('page', 0),
                        'box': grounding.get('box', {}),
                        'type': chunk_data.get('type', 'text'),
                        'text_preview': text[:100] if text else ''
                    }

            # Full markdown text
            full_text = response.markdown if hasattr(response, 'markdown') else '\n'.join(all_text)
            
            # Parse the extracted text
            parsed = self._parse_receipt_text(full_text, chunks)
            
            result.update({
                "success": True,
                "shop_name": parsed.get("shop_name"),
                "shop_address": parsed.get("address"),
                "amount": parsed.get("amount", 0.0),
                "currency": "ZAR",
                "items": parsed.get("items", []),
                "date": parsed.get("date"),
                "raw_text": full_text,
                "grounding": grounding_data,
                "chunks": chunks,
                "processing_time": round(processing_time, 2),
                "error": None
            })

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

        return result

    def _parse_receipt_text(self, text: str, chunks: List[Dict]) -> Dict:
        """
        Parse receipt text to extract structured data
        Works with South African receipt formats
        """
        result = {
            "shop_name": None,
            "address": None,
            "amount": 0.0,
            "items": [],
            "date": None
        }

        if not text:
            return result

        lines = text.strip().split('\n')
        lines = [l.strip() for l in lines if l.strip()]

        # --- Extract Shop Name ---
        # Usually first non-empty line or look for known SA retailers
        sa_retailers = [
            'checkers', 'pick n pay', 'woolworths', 'shoprite', 'spar',
            'dis-chem', 'clicks', 'engen', 'shell', 'bp', 'sasol',
            'game', 'makro', 'builders', 'cashbuild', 'pep', 'ackermans',
            'truworths', 'edgars', 'jet', 'mr price', 'foschini'
        ]
        
        for line in lines[:5]:  # Check first 5 lines
            line_lower = line.lower()
            for retailer in sa_retailers:
                if retailer in line_lower:
                    result["shop_name"] = line
                    break
            if result["shop_name"]:
                break
        
        # Fallback: use first line as shop name
        if not result["shop_name"] and lines:
            result["shop_name"] = lines[0]

        # --- Extract Address ---
        address_keywords = ['street', 'st.', 'road', 'rd.', 'ave', 'avenue', 
                          'mall', 'centre', 'center', 'shop', 'store']
        for line in lines[1:10]:
            if any(kw in line.lower() for kw in address_keywords):
                result["address"] = line
                break

        # --- Extract Total Amount ---
        # Look for patterns like "TOTAL R 123.45" or "AMOUNT DUE R123,45"
        amount_patterns = [
            r'(?:TOTAL|AMOUNT\s*DUE|BALANCE\s*DUE|GRAND\s*TOTAL|SUBTOTAL)[:\s]*R?\s*(\d+[.,]\d{2})',
            r'R\s*(\d+[.,]\d{2})\s*(?:TOTAL|DUE)?$',
            r'(\d+[.,]\d{2})\s*(?:ZAR|RAND)?$'
        ]
        
        for line in reversed(lines):  # Check from bottom up
            for pattern in amount_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    amount_str = match.group(1).replace(',', '.')
                    try:
                        result["amount"] = float(amount_str)
                        break
                    except ValueError:
                        continue
            if result["amount"] > 0:
                break

        # --- Extract Items ---
        # Look for lines with prices (R XX.XX pattern)
        item_pattern = r'^(.+?)\s+R?\s*(\d+[.,]\d{2})$'
        skip_keywords = ['total', 'subtotal', 'vat', 'tax', 'cash', 'change', 'card', 'balance']
        
        for line in lines:
            if any(kw in line.lower() for kw in skip_keywords):
                continue
            
            match = re.match(item_pattern, line.strip())
            if match:
                item_name = match.group(1).strip()
                try:
                    item_price = float(match.group(2).replace(',', '.'))
                    if item_price > 0 and len(item_name) > 2:
                        result["items"].append({
                            "name": item_name,
                            "price": item_price,
                            "quantity": 1
                        })
                except ValueError:
                    continue

        # --- Extract Date ---
        date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})'
        ]
        
        for line in lines:
            for pattern in date_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    result["date"] = match.group(1)
                    break
            if result["date"]:
                break

        return result


# Singleton instance
_processor = None

def get_receipt_processor() -> ReceiptProcessor:
    """Get or create the receipt processor singleton"""
    global _processor
    if _processor is None:
        _processor = ReceiptProcessor()
    return _processor
