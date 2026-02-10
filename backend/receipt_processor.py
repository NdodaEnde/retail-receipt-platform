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
        
        # Remove data URL prefix if present (e.g., "data:image/png;base64,")
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        
        # Decode image
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception as e:
            logger.error(f"Base64 decode error: {e}")
            result["error"] = "Invalid image data"
            return result
        
        # Track if we converted the image
        converted_image_base64 = None
        
        # Check if HEIC format (iPhone) and convert
        try:
            from PIL import Image
            import io
            
            # Check magic bytes for HEIC (ftypheic, ftypheix, etc.)
            if b'ftyp' in image_bytes[:20] and (b'heic' in image_bytes[:20] or b'heix' in image_bytes[:20] or b'mif1' in image_bytes[:20]):
                logger.info("Detected HEIC format, converting to JPEG...")
                try:
                    import pillow_heif
                    pillow_heif.register_heif_opener()
                except ImportError:
                    logger.warning("pillow-heif not installed, HEIC conversion may fail")
                
                img = Image.open(io.BytesIO(image_bytes))
                img = img.convert('RGB')
                
                # Resize if too large
                max_size = 2000
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Save to bytes
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=90)
                image_bytes = buffer.getvalue()
                mime_type = "image/jpeg"
                # Store the converted image as base64
                converted_image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                logger.info(f"Converted HEIC to JPEG ({len(image_bytes)} bytes)")
        except Exception as e:
            logger.warning(f"Image preprocessing warning: {e}")
        
        # Determine file suffix
        if "jpeg" in mime_type or "jpg" in mime_type:
            suffix = ".jpg"
        elif "png" in mime_type:
            suffix = ".png"
        else:
            suffix = ".jpg"
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            tmp_file.write(image_bytes)
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
                "converted_image": converted_image_base64,  # Return converted JPEG if HEIC was converted
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
        Handles both plain text and HTML table formats from LandingAI
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

        # Check if text contains HTML table (LandingAI format)
        if '<table>' in text.lower():
            result = self._parse_html_table(text, result)
        
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
        
        for line in lines[:10]:  # Check first 10 lines
            # Remove HTML tags for matching
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            line_lower = clean_line.lower()
            for retailer in sa_retailers:
                if retailer in line_lower:
                    result["shop_name"] = clean_line.upper() if len(clean_line) < 50 else retailer.upper()
                    break
            if result["shop_name"]:
                break
        
        # Fallback: use first meaningful line as shop name
        if not result["shop_name"] and lines:
            for line in lines[:5]:
                clean_line = re.sub(r'<[^>]+>', '', line).strip()
                if clean_line and len(clean_line) > 2 and not clean_line.startswith('<'):
                    result["shop_name"] = clean_line
                    break

        # --- Extract Address ---
        # Look for address patterns in receipt - common SA formats
        # Collect multiple address lines if found
        address_keywords = ['street', 'st.', 'road', 'rd.', 'rd', 'ave', 'avenue', 
                          'mall', 'centre', 'center', 'shop', 'store', 'cnr', 'corner',
                          'drive', 'dr.', 'lane', 'way', 'blvd', 'boulevard', 'park']
        
        # Also look for suburb/city names that indicate an address line
        sa_cities = ['cape town', 'johannesburg', 'durban', 'pretoria', 'bloemfontein',
                    'port elizabeth', 'gqeberha', 'sandton', 'centurion', 'midrand',
                    'brackenfell', 'bellville', 'soweto', 'umhlanga', 'ballito',
                    'randburg', 'rosebank', 'fourways', 'bryanston', 'morningside',
                    'greenside', 'parkhurst', 'melville', 'northcliff', 'linden']
        
        address_parts = []
        for line in lines[1:15]:
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            line_lower = clean_line.lower()
            
            # Skip if this is the shop name
            if result.get("shop_name") and clean_line.upper() == result["shop_name"].upper():
                continue
            
            # Skip phone numbers and tel lines
            if re.match(r'^tel\s|^\d{3}\s?\d{3}\s?\d{4}|^0\d{2}\s?\d{3}\s?\d{4}', line_lower):
                continue
            if 'tel' in line_lower and any(c.isdigit() for c in clean_line):
                continue
                
            # Check for address keywords
            if any(kw in line_lower for kw in address_keywords):
                address_parts.append(clean_line)
                continue
            
            # Check for SA city/suburb names
            if any(city in line_lower for city in sa_cities):
                address_parts.append(clean_line)
                continue
        
        # Combine address parts
        if address_parts:
            result["address"] = ", ".join(address_parts[:3])  # Max 3 lines

        # --- Extract Total Amount (if not found in table) ---
        if result["amount"] == 0:
            # Look for TOTAL/Amount Due patterns
            amount_patterns = [
                r'(?:TOTAL|AMOUNT\s*DUE|BALANCE\s*DUE|GRAND\s*TOTAL|SUBTOTAL)[:\s]*R?\s*(\d+[.,]\d{2})',
                r'(\d+[.,]\d{2})\s*$',  # Amount at end of line
                r'R\s*(\d+[.,]\d{2})',   # R followed by amount
                r'>R?(\d+[.,]\d{2})<',   # HTML format
            ]
            
            # First look for explicit TOTAL/Amount Due lines
            for line in lines:
                clean_line = re.sub(r'<[^>]+>', '', line).strip()
                line_lower = clean_line.lower()
                
                # Look for total/amount due keywords
                if any(kw in line_lower for kw in ['total', 'amount due', 'balance due', 'amount owing']):
                    if 'subtotal' in line_lower and 'total' not in line_lower.replace('subtotal', ''):
                        continue  # Skip subtotal unless there's also "total"
                    
                    for pattern in amount_patterns:
                        match = re.search(pattern, clean_line, re.IGNORECASE)
                        if match:
                            amount_str = match.group(1).replace(',', '.')
                            try:
                                amount = float(amount_str)
                                if amount > result["amount"]:  # Take the larger total
                                    result["amount"] = amount
                            except ValueError:
                                continue

        # --- Extract Items (if not found in table) ---
        if not result["items"]:
            item_pattern = r'^(.+?)\s+R?\s*(\d+[.,]\d{2})$'
            skip_keywords = ['total', 'subtotal', 'vat', 'tax', 'cash', 'change', 'card', 'balance', 'rate', 'payment']
            
            for line in lines:
                clean_line = re.sub(r'<[^>]+>', '', line).strip()
                if any(kw in clean_line.lower() for kw in skip_keywords):
                    continue
                
                match = re.match(item_pattern, clean_line)
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
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            for pattern in date_patterns:
                match = re.search(pattern, clean_line, re.IGNORECASE)
                if match:
                    result["date"] = match.group(1)
                    break
            if result["date"]:
                break

        return result

    def _parse_html_table(self, text: str, result: Dict) -> Dict:
        """Parse HTML table format from LandingAI OCR output"""
        try:
            # Extract table rows - handle IDs in td elements
            # Pattern matches: <tr><td id="...">content</td><td id="...">content</td></tr>
            row_pattern = r'<tr><td[^>]*>([^<]*)</td><td[^>]*>([^<]*)</td></tr>'
            rows = re.findall(row_pattern, text, re.IGNORECASE)
            
            skip_keywords = ['total', 'subtotal', 'vat', 'tax', 'cash', 'change', 
                           'card', 'balance', 'rate', 'payment', 'invoice', 'description',
                           'qty', 'item', 'price', 'value', 'tendered', 'tax%']
            
            for item_name, price_str in rows:
                item_name = item_name.strip()
                price_str = price_str.strip()
                
                # Decode HTML entities
                item_name = item_name.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                
                # Skip header rows and totals
                if not item_name or not price_str:
                    continue
                if any(kw in item_name.lower() for kw in skip_keywords):
                    # But extract the total amount
                    if ('total' in item_name.lower() or 'bill' in item_name.lower()) and 'subtotal' not in item_name.lower():
                        price_match = re.search(r'R?(\d+[.,]\d{2})', price_str)
                        if price_match:
                            try:
                                amount = float(price_match.group(1).replace(',', '.'))
                                if amount > result["amount"]:
                                    result["amount"] = amount
                            except ValueError:
                                pass
                    continue
                
                # Extract price
                price_match = re.search(r'R?(\d+[.,]\d{2})', price_str)
                if price_match and len(item_name) > 1:
                    try:
                        item_price = float(price_match.group(1).replace(',', '.'))
                        if item_price > 0:
                            result["items"].append({
                                "name": item_name,
                                "price": item_price,
                                "quantity": 1
                            })
                    except ValueError:
                        continue
            
            logger.info(f"Parsed HTML table: {len(result['items'])} items, total: R{result['amount']}")
            
        except Exception as e:
            logger.error(f"HTML table parsing error: {e}")
        
        return result


# Singleton instance
_processor = None

def get_receipt_processor() -> ReceiptProcessor:
    """Get or create the receipt processor singleton"""
    global _processor
    if _processor is None:
        _processor = ReceiptProcessor()
    return _processor
