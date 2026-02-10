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
        
        # Normalize and convert all mobile image formats to JPEG for consistent display
        # Supports: HEIC/HEIF (iPhone), WebP (Android), PNG, JPEG
        try:
            from PIL import Image
            import io
            
            needs_conversion = False
            format_name = "unknown"
            
            # Check magic bytes for HEIC (iPhone default since iOS 11)
            if b'ftyp' in image_bytes[:20] and (b'heic' in image_bytes[:20] or b'heix' in image_bytes[:20] or b'mif1' in image_bytes[:20]):
                format_name = "HEIC"
                needs_conversion = True
                try:
                    import pillow_heif
                    pillow_heif.register_heif_opener()
                except ImportError:
                    logger.warning("pillow-heif not installed, HEIC conversion may fail")
            
            # Check for WebP (some Android devices)
            elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
                format_name = "WebP"
                needs_conversion = True
            
            # Check for PNG (screenshots)
            elif image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                format_name = "PNG"
                needs_conversion = True  # Convert to JPEG for smaller size
            
            # JPEG is already good - just check if resizing needed
            elif image_bytes[:2] == b'\xff\xd8':
                format_name = "JPEG"
                # Check if image is too large (>5MB) and needs compression
                if len(image_bytes) > 5 * 1024 * 1024:
                    needs_conversion = True
            
            if needs_conversion:
                logger.info(f"Processing {format_name} image, converting to optimized JPEG...")
                
                img = Image.open(io.BytesIO(image_bytes))
                
                # Handle RGBA (PNG with transparency) - convert to RGB
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background for transparent images
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if too large (max 2000px on longest side)
                max_size = 2000
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Resized image to {new_size}")
                
                # Save as optimized JPEG
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85, optimize=True)
                image_bytes = buffer.getvalue()
                mime_type = "image/jpeg"
                converted_image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                logger.info(f"Converted {format_name} to JPEG ({len(image_bytes)} bytes)")
            else:
                logger.info(f"Image format {format_name} - no conversion needed")
                
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
            "date": None,
            "postal_code": None  # Track detected postal code for geocoding
        }

        if not text:
            return result

        # Check if text contains HTML table (LandingAI format)
        if '<table>' in text.lower():
            result = self._parse_html_table(text, result)
        
        lines = text.strip().split('\n')
        lines = [l.strip() for l in lines if l.strip()]
        
        # --- First pass: Scan ENTIRE text for SA postal codes ---
        # SA postal codes are 4 digits, typically appearing alone or with suburb name
        # They should NOT be part of phone numbers, VAT numbers, or prices
        
        def is_valid_sa_postal(code_str, line_context):
            """Check if a 4-digit number is likely a postal code, not phone/VAT/price"""
            try:
                code = int(code_str)
                line_lower = line_context.lower()
                
                # Exclude if in phone number context
                if 'tel' in line_lower or 'phone' in line_lower or 'cell' in line_lower:
                    return False
                if re.search(r'0\d{2}\s?\d{3}\s?' + code_str, line_context):  # Part of phone number
                    return False
                    
                # Exclude if part of VAT number
                if 'vat' in line_lower:
                    return False
                    
                # Exclude if looks like a year
                if code >= 1900 and code <= 2100:
                    return False
                    
                # Exclude if appears with R (price) or decimal
                if re.search(r'R\s*' + code_str, line_context) or re.search(code_str + r'[.,]\d{2}', line_context):
                    return False
                
                # Valid SA postal codes are between 0001-9999
                # Most commonly 7000-7999 for Western Cape, 2000-2999 for Gauteng, etc.
                if code < 1 or code > 9999:
                    return False
                
                # Prefer codes that appear alone on a line or with suburb context
                # e.g., "Constantia 7848" or just "7848"
                clean_line = re.sub(r'[^\w\s]', '', line_context).strip()
                words = clean_line.split()
                if code_str in words:
                    return True
                    
                return False
            except:
                return False
        
        # Search each line for potential postal codes
        for line in lines:
            potential_codes = re.findall(r'\b(\d{4})\b', line)
            for code in potential_codes:
                if is_valid_sa_postal(code, line):
                    result["postal_code"] = code
                    logger.info(f"Detected SA postal code: {code} from line: {line[:50]}")
                    break
            if result["postal_code"]:
                break

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
                          'drive', 'dr.', 'lane', 'way', 'blvd', 'boulevard', 'park',
                          'plaza', 'square', 'complex']
        
        # Also look for suburb/city names that indicate an address line
        sa_cities = ['cape town', 'johannesburg', 'durban', 'pretoria', 'bloemfontein',
                    'port elizabeth', 'gqeberha', 'sandton', 'centurion', 'midrand',
                    'brackenfell', 'bellville', 'soweto', 'umhlanga', 'ballito',
                    'randburg', 'rosebank', 'fourways', 'bryanston', 'morningside',
                    'greenside', 'parkhurst', 'melville', 'northcliff', 'linden',
                    'constantia', 'newlands', 'claremont', 'wynberg', 'kenilworth',
                    'tokai', 'kirstenhof', 'bergvliet', 'meadowridge', 'plumstead',
                    'rondebosch', 'mowbray', 'observatory', 'woodstock', 'gardens',
                    'sea point', 'green point', 'camps bay', 'clifton', 'bantry bay',
                    'hout bay', 'llandudno', 'noordhoek', 'fish hoek', 'simons town',
                    'muizenberg', 'kalk bay', 'st james', 'retreat', 'steenberg',
                    'durbanville', 'kraaifontein', 'kuils river', 'blue downs',
                    'mitchell\'s plain', 'khayelitsha', 'philippi', 'athlone', 'pinelands',
                    'edenvale', 'bedfordview', 'germiston', 'kempton park', 'boksburg',
                    'benoni', 'springs', 'alberton', 'roodepoort', 'krugersdorp',
                    'george', 'knysna', 'plettenberg bay', 'mossel bay', 'stellenbosch',
                    'paarl', 'franschhoek', 'somerset west', 'strand', 'gordons bay']
        
        # SA postal code to suburb mapping (for better geocoding)
        sa_postal_codes = {
            '7848': 'Constantia, Cape Town',
            '7806': 'Newlands, Cape Town',
            '7708': 'Claremont, Cape Town',
            '7800': 'Rondebosch, Cape Town',
            '7405': 'Wynberg, Cape Town',
            '7945': 'Tokai, Cape Town',
            '7441': 'Durbanville, Cape Town',
            '7550': 'Bellville, Cape Town',
            '7530': 'Brackenfell, Cape Town',
            '7560': 'Kraaifontein, Cape Town',
            '2196': 'Sandton, Johannesburg',
            '2057': 'Rosebank, Johannesburg',
            '2191': 'Fourways, Johannesburg',
            '2021': 'Bryanston, Johannesburg',
            '0157': 'Centurion, Pretoria',
            '0181': 'Midrand, Johannesburg',
        }
        
        address_parts = []
        detected_postal_code = None
        detected_suburb = None
        
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
            
            # Check for SA postal code (4 digits)
            postal_match = re.search(r'\b(\d{4})\b', clean_line)
            if postal_match:
                code = postal_match.group(1)
                if code in sa_postal_codes:
                    detected_postal_code = code
                    detected_suburb = sa_postal_codes[code]
                    logger.info(f"Detected postal code {code} -> {detected_suburb}")
                
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
        
        # If we detected a postal code but no address, use the postal code mapping
        if detected_suburb and not result.get("address"):
            result["address"] = detected_suburb
            logger.info(f"Using postal code for address: {detected_suburb}")

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
                    
                    # Skip gratuity/tip lines
                    if 'gratuity' in line_lower or 'tip' in line_lower:
                        continue
                    
                    for pattern in amount_patterns:
                        match = re.search(pattern, clean_line, re.IGNORECASE)
                        if match:
                            amount_str = match.group(1).replace(',', '.')
                            try:
                                amount = float(amount_str)
                                # Sanity check - amount should be reasonable (> R50 for a restaurant)
                                if amount > result["amount"] and amount > 50:
                                    result["amount"] = amount
                                    logger.info(f"Found amount: R{amount} from: {clean_line[:50]}")
                            except ValueError:
                                continue
            
            # Also look for "Amount due ZAR X,XXX.X" format (specific to some POS systems)
            amount_due_pattern = r'Amount\s+due\s+(?:ZAR|R)?\s*([\d,]+\.?\d*)'
            for line in lines:
                clean_line = re.sub(r'<[^>]+>', '', line).strip()
                match = re.search(amount_due_pattern, clean_line, re.IGNORECASE)
                if match:
                    try:
                        amount = float(match.group(1).replace(',', ''))
                        if amount > result["amount"]:
                            result["amount"] = amount
                            logger.info(f"Found Amount due: R{amount}")
                    except ValueError:
                        pass

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
        """Parse HTML table format from LandingAI OCR output - handles 2, 3, or 4 column tables"""
        try:
            # Find all table rows
            row_pattern = r'<tr>(.*?)</tr>'
            rows = re.findall(row_pattern, text, re.IGNORECASE | re.DOTALL)
            
            skip_keywords = ['total', 'subtotal', 'vat', 'tax', 'cash', 'change', 
                           'card', 'balance', 'rate', 'payment', 'invoice', 'description',
                           'qty', 'item', 'price', 'value', 'tendered', 'tax%', 'tai',
                           'gratuity', 'tip', 'service', 'amount due']
            
            logger.info(f"Parsing HTML table with {len(rows)} rows")
            
            for row in rows:
                # Extract all cells from this row
                cell_pattern = r'<td[^>]*>([^<]*)</td>'
                cells = re.findall(cell_pattern, row)
                cells = [c.strip() for c in cells]
                
                if not cells:
                    continue
                
                # Determine table format and extract item name + price
                item_name = None
                item_price = None
                quantity = 1
                
                # Skip empty rows or header rows
                if all(not c for c in cells):
                    continue
                
                # Check if this is a header row or total row
                row_text = ' '.join(cells).lower()
                if any(kw in row_text for kw in skip_keywords):
                    # Extract total amount if present
                    if 'total' in row_text or 'amount due' in row_text or 'tai' in row_text:
                        for cell in cells:
                            price_match = re.search(r'(\d+[.,]\d{2})$', cell.strip())
                            if price_match:
                                try:
                                    amount = float(price_match.group(1).replace(',', '.'))
                                    if amount > result["amount"] and amount > 100:  # Sanity check
                                        result["amount"] = amount
                                        logger.info(f"Found total amount: R{amount}")
                                except ValueError:
                                    pass
                    continue
                
                # Handle different column formats:
                if len(cells) == 2:
                    # Format: [item_name, price]
                    item_name = cells[0]
                    price_str = cells[1]
                    
                elif len(cells) == 3:
                    # Format: [qty, item_name, price] or [item_name, unit_price, total_price]
                    if cells[0].isdigit():
                        quantity = int(cells[0])
                        item_name = cells[1]
                        price_str = cells[2]
                    else:
                        item_name = cells[0]
                        price_str = cells[2]  # Use total price
                        
                elif len(cells) == 4:
                    # Format: [qty, item_name, unit_price, total_price]
                    # Take item name from column 2, price from last column (total)
                    if cells[0].isdigit():
                        quantity = int(cells[0]) if cells[0] else 1
                    item_name = cells[1]
                    price_str = cells[3]  # Last column is usually total
                    
                    # If last column is empty, try third column
                    if not price_str or not re.search(r'\d', price_str):
                        price_str = cells[2]
                else:
                    # Unknown format - try to extract name and price from available cells
                    for i, cell in enumerate(cells):
                        if cell and not cell.isdigit() and len(cell) > 2:
                            if not any(c.isdigit() for c in cell):
                                item_name = cell
                            elif re.match(r'^\d+[.,]\d{2}$', cell.strip()):
                                price_str = cell
                    if not price_str:
                        price_str = cells[-1] if cells else ""
                
                # Clean up item name
                if item_name:
                    item_name = item_name.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                    item_name = item_name.strip()
                
                # Skip if item name is too short or looks like a number
                if not item_name or len(item_name) < 2:
                    continue
                if item_name.replace('.', '').replace(',', '').isdigit():
                    continue
                    
                # Extract price
                if price_str:
                    price_match = re.search(r'(\d+[.,]\d{2})$', price_str.strip())
                    if not price_match:
                        price_match = re.search(r'(\d+)[.,](\d{2})', price_str)
                    if price_match:
                        try:
                            price_text = price_match.group(0).replace(',', '.')
                            item_price = float(price_text)
                        except ValueError:
                            continue
                
                # Add valid item
                if item_name and item_price and item_price > 0:
                    result["items"].append({
                        "name": item_name,
                        "price": item_price,
                        "quantity": quantity
                    })
                    logger.debug(f"Extracted item: {item_name} x{quantity} = R{item_price}")
            
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
