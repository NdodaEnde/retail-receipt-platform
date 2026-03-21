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
import json

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
            plain_preview = re.sub(r'<[^>]+>', ' ', full_text)
            plain_preview = re.sub(r'\s+', ' ', plain_preview).strip()
            logger.info(f"Raw OCR text: {plain_preview[:800]}")

            # Parse the extracted text
            parsed = self._parse_receipt_text(full_text, chunks)

            # Schema extraction: use LandingAI extract() on the markdown text
            # This gives structured shop_name, address, items, amount
            line_items_from_schema = []
            schema_shop_name = None
            schema_shop_address = None
            schema_total_amount = None
            try:
                items_schema = json.dumps({
                    "type": "object",
                    "properties": {
                    "line_items": {
                        "type": "array",
                        "description": "List of items purchased on the receipt",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_name": {"type": "string", "description": "Name of the item"},
                                "quantity": {"type": "number", "description": "Number of units purchased"},
                                "unit_price": {"type": "number", "description": "Price per single unit"},
                                "total_price": {"type": "number", "description": "Total price for this line item including tax"}
                            }
                        }
                    },
                    "total_amount": {"type": "number", "description": "Final total amount due on the receipt including tax"},
                    "shop_name": {"type": "string", "description": "Name of the shop, store, or business (not slogans, version numbers, or taglines)"},
                    "shop_address": {"type": "string", "description": "Street address or location of the shop"}
                    }
                })

                extract_response = self.client.extract(
                    markdown=full_text,
                    schema=items_schema,
                    model="extract-latest"
                )

                if extract_response and hasattr(extract_response, 'extraction'):
                    extracted_data = extract_response.extraction
                    logger.info(f"Schema extraction result: {json.dumps(extracted_data)[:500]}")
                    if 'line_items' in extracted_data:
                        for item in extracted_data['line_items']:
                            if item.get('item_name'):
                                line_items_from_schema.append({
                                    'name': item.get('item_name', ''),
                                    'quantity': int(item.get('quantity', 1)) if item.get('quantity') else 1,
                                    'unit_price': float(item.get('unit_price', 0)) if item.get('unit_price') else None,
                                    'total_price': float(item.get('total_price', 0)) if item.get('total_price') else None
                                })
                        logger.info(f"Schema extraction found {len(line_items_from_schema)} items")
                    if extracted_data.get('shop_name'):
                        schema_shop_name = extracted_data['shop_name']
                        logger.info(f"Schema shop_name: {schema_shop_name}")
                    if extracted_data.get('shop_address'):
                        schema_shop_address = extracted_data['shop_address']
                        logger.info(f"Schema shop_address: {schema_shop_address}")
                    if extracted_data.get('total_amount'):
                        schema_total_amount = float(extracted_data['total_amount'])
                        logger.info(f"Schema total_amount: {schema_total_amount}")
            except Exception as e:
                logger.warning(f"Schema extraction failed: {e}")

            # Prefer schema-extracted items if available and better quality
            final_items = parsed.get("items", [])
            if line_items_from_schema:
                # Check if schema items have better data (unit prices)
                schema_has_unit_prices = any(item.get('unit_price') for item in line_items_from_schema)
                parsed_has_unit_prices = any(item.get('unit_price') != item.get('total_price') for item in final_items)
                
                if schema_has_unit_prices or len(line_items_from_schema) > len(final_items):
                    # Use schema items, fill in missing prices
                    for item in line_items_from_schema:
                        if item.get('total_price') and not item.get('unit_price'):
                            item['unit_price'] = item['total_price']
                        if item.get('unit_price') and not item.get('total_price'):
                            item['total_price'] = item['unit_price'] * item.get('quantity', 1)
                        # Add price field for backward compatibility
                        item['price'] = item.get('total_price', 0)
                    final_items = line_items_from_schema
                    logger.info(f"Using schema-extracted items ({len(final_items)} items)")
            
            # Schema extraction is primary, text parser is fallback
            final_shop_name = schema_shop_name or parsed.get("shop_name")
            final_address = schema_shop_address or parsed.get("address")
            final_amount = schema_total_amount or parsed.get("amount", 0.0)

            logger.info(f"Final shop_name: {final_shop_name} (schema: {schema_shop_name}, parsed: {parsed.get('shop_name')})")
            logger.info(f"Final address: {final_address} (schema: {schema_shop_address}, parsed: {parsed.get('address')})")
            logger.info(f"Final amount: {final_amount} (schema: {schema_total_amount}, parsed: {parsed.get('amount')})")

            result.update({
                "success": True,
                "shop_name": final_shop_name,
                "shop_address": final_address,
                "postal_code": parsed.get("postal_code"),  # Include postal code for geocoding
                "amount": final_amount,
                "currency": "ZAR",
                "items": final_items,
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

        def clean_ocr_text(text):
            """Remove OCR markup like <::LOGO: ..., description::> and HTML tags"""
            text = re.sub(r'<::LOGO:\s*([^,>]+)[^>]*::>', r'\1', text)
            text = re.sub(r'<::[^>]*::>', '', text)
            text = re.sub(r'<[^>]+>', '', text)
            return text.strip()

        # Check if text contains HTML table (LandingAI format)
        if '<table' in text.lower():
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
                if any(kw in line_lower for kw in ['tel', 'phone', 'cell', 'care line', 'customer care', 'call', 'helpline', 'hotline']):
                    return False
                if re.search(r'0\d{2}\s?\d{3}\s?' + code_str, line_context):  # Part of phone number
                    return False
                # Exclude toll-free style numbers (0800, 0860, 0861, etc.)
                if code >= 800 and code <= 899:
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
            clean_line = clean_ocr_text(line)
            line_lower = clean_line.lower()
            for retailer in sa_retailers:
                if retailer in line_lower:
                    result["shop_name"] = retailer.upper()
                    break
            if result["shop_name"]:
                break

        # Fallback: use first meaningful line as shop name
        if not result["shop_name"] and lines:
            for line in lines[:5]:
                clean_line = clean_ocr_text(line)
                if clean_line and len(clean_line) > 2 and not clean_line.startswith('<'):
                    result["shop_name"] = clean_line
                    break

        # --- Extract Address ---
        # Receipt header always starts at the top: shop name, suburb, street, phone.
        # The OCR text begins with this header regardless of format.
        # Strategy: take the START of the plain text, cut at the first transactional
        # keyword, strip the shop name and phone numbers. What remains is the address.
        # Let Google Maps figure out what's a real place.

        plain_text = re.sub(r'<::[^>]*::>', ' ', text)  # Strip OCR markup first
        plain_text = re.sub(r'<[^>]+>', ' ', plain_text)  # Strip HTML tags
        plain_text = re.sub(r'\s+', ' ', plain_text).strip()

        address_text = None
        if result.get("shop_name"):
            # The header is at the START of the text — not where the shop name
            # appears (it could match in the footer like "Thank you for shopping at...")
            # Cut the text at the first transactional keyword to isolate the header
            cut_patterns = r'(?i)\b(TAX INVOICE|VAT\s*(?:NO|:|\d)|INVOICE|CASHIER|TILL|TXN|RECEIPT NO|TABLE:|WAITER|ITEM\s|QTY\s|TOTAL|SUBTOTAL|SMART SHOPPER|LOYALTY|CUSTOMER CARE|Liquor Lic)\b'
            cut_match = re.search(cut_patterns, plain_text)
            header = plain_text[:cut_match.start()].strip() if cut_match else plain_text[:100]
            logger.info(f"Address extraction — header: '{header[:150]}'")

            # Remove the shop name from the header to leave just the address
            addr = re.sub(re.escape(result["shop_name"]), '', header, flags=re.IGNORECASE).strip()
            # Strip phone numbers (SA format: 0XX XXX XXXX or 011 XXX XXXX)
            addr = re.sub(r'0\d{2}[\s-]?\d{3}[\s-]?\d{4}', '', addr).strip()
            # Strip email addresses
            addr = re.sub(r'\S+@\S+\.\S+', '', addr).strip()
            # Strip VAT numbers (e.g. "VAT No 4920269612")
            addr = re.sub(r'(?i)VAT\s*(?:No\.?|:)?\s*\d+', '', addr).strip()
            # Strip "Ver X.X" version numbers from logo text
            addr = re.sub(r'(?i)\bVer\s+\d+(\.\d+)?\b', '', addr).strip()
            # Strip common logo fragments
            addr = re.sub(r'(?i)\bKeep Swimming\b', '', addr).strip()
            # Strip leading/trailing punctuation and whitespace
            addr = re.sub(r'^[\s,.\-:]+|[\s,.\-:]+$', '', addr).strip()
            logger.info(f"Address extraction — after cleanup: '{addr}'")

            if addr and len(addr) >= 3:
                address_text = addr

        if address_text:
            result["address"] = address_text
            logger.info(f"Extracted address: {result['address']}")
        else:
            logger.info(f"No address extracted from receipt header")

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
        # SA receipts commonly print many date formats:
        #   15/03/2026, 15-03-2026, 15.03.26, 2026/03/15,
        #   15 Mar 2026, Mar 13/26, 15/03/26, 2026-03-15
        date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',          # 15/03/2026 or 15-03-2026
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',           # 2026/03/15 or 2026-03-15
            r'(\d{1,2}\.\d{1,2}\.\d{2,4})',             # 19.03.26 or 19.03.2026 (dot separator)
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2})(?!\d)',     # 15/03/26 (2-digit year, not part of longer number)
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}[/-]\d{2,4})',  # Mar 13/26 or Mar 13/2026
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4})',  # 15 Mar 2026
            r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
        ]

        # Keywords that commonly appear before or on the same line as the date
        date_keywords = ('date', 'datum', 'tyd', 'time', 'dt:', 'date:', 'tax invoice', 'vat invoice')

        for line in lines:
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            # Prioritise lines that mention date-related keywords
            line_lower = clean_line.lower()
            is_date_line = any(kw in line_lower for kw in date_keywords)
            for pattern in date_patterns:
                match = re.search(pattern, clean_line, re.IGNORECASE)
                if match:
                    # Accept immediately if it's a labelled date line; otherwise keep looking
                    if is_date_line or not result["date"]:
                        result["date"] = match.group(1)
                    if is_date_line:
                        break
            if result["date"] and is_date_line:
                break
        # Fall back: accept the first match found even without a keyword label
        if not result["date"]:
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
        """Parse HTML table format from LandingAI OCR output - handles 2, 3, or 4 column tables
        
        Extracts granular item data for SKU-level analytics:
        - name: Item/product name
        - quantity: Number of units purchased
        - unit_price: Price per single unit
        - total_price: Total for this line (qty × unit_price)
        """
        try:
            # Find all table rows
            row_pattern = r'<tr>(.*?)</tr>'
            rows = re.findall(row_pattern, text, re.IGNORECASE | re.DOTALL)
            
            skip_keywords = ['total', 'subtotal', 'vat', 'tax', 'cash', 'change',
                           'card', 'balance', 'rate', 'payment', 'invoice',
                           'tendered', 'tax%', 'tai',
                           'gratuity', 'tip', 'service', 'amount due']

            # Detect column order from header row (e.g., ITEM, QTY, PRICE, VALUE)
            col_order = None  # None = default (qty, name, unit, total)
            for row in rows:
                cell_pattern = r'<td[^>]*>([^<]*)</td>'
                cells = [c.strip().lower() for c in re.findall(cell_pattern, row)]
                if len(cells) >= 3 and any(h in cells for h in ['item', 'description', 'qty', 'quantity']):
                    # This is a header row - detect column positions
                    col_order = {}
                    for i, c in enumerate(cells):
                        if c in ('item', 'description', 'product', 'name'):
                            col_order['name'] = i
                        elif c in ('qty', 'quantity', 'qnt'):
                            col_order['qty'] = i
                        elif c in ('price', 'unit price', 'unit'):
                            col_order['unit_price'] = i
                        elif c in ('value', 'total', 'amount', 'ext', 'extended'):
                            col_order['total_price'] = i
                    logger.info(f"Detected column order from header: {col_order}")
                    break

            logger.info(f"Parsing HTML table with {len(rows)} rows")

            for row in rows:
                # Extract all cells from this row
                cell_pattern = r'<td[^>]*>([^<]*)</td>'
                cells = re.findall(cell_pattern, row)
                cells = [c.strip() for c in cells]

                logger.info(f"Table row cells: {cells}")

                if not cells:
                    continue
                
                # Initialize item data
                item_name = None
                unit_price = None
                total_price = None
                quantity = 1
                
                # Skip empty rows or header rows
                if all(not c for c in cells):
                    continue
                
                # Check if this is a header row or total row
                row_text = ' '.join(cells).lower()
                header_keywords = ['item', 'qty', 'quantity', 'description', 'product']
                if all(any(h in c.lower() for h in header_keywords + ['price', 'value', 'amount', 'unit']) for c in cells if c):
                    logger.info(f"Skipping header row: {row_text[:80]}")
                    continue
                if any(kw in row_text for kw in skip_keywords):
                    logger.info(f"Skipping row (keyword match): {row_text[:80]}")
                    # Extract total amount if present
                    if 'total' in row_text or 'amount due' in row_text or 'tai' in row_text:
                        for cell in cells:
                            price_match = re.search(r'(\d+[.,]\d{2})$', cell.strip())
                            if price_match:
                                try:
                                    amount = float(price_match.group(1).replace(',', '.'))
                                    if amount > result["amount"] and amount > 0:  # Accept any positive total
                                        result["amount"] = amount
                                        logger.info(f"Found total amount: R{amount}")
                                except ValueError:
                                    pass
                    continue
                
                # Helper to extract price from string
                def extract_price(s):
                    if not s:
                        return None
                    match = re.search(r'(\d+[.,]\d{2})$', s.strip())
                    if not match:
                        match = re.search(r'(\d+)[.,](\d{2})', s)
                    if match:
                        try:
                            return float(match.group(0).replace(',', '.'))
                        except:
                            return None
                    return None
                
                # Handle different column formats:
                if len(cells) == 2:
                    # Format: [item_name, price] or [item_name, "unit_price total_price"]
                    item_name = cells[0]
                    price_cell = cells[1]
                    
                    # Check if price cell contains TWO prices (unit and total)
                    # Pattern: "45.00 90.00" or "45.00  90.00" or "R45.00 R90.00"
                    two_prices = re.findall(r'(\d+[.,]\d{2})', price_cell)
                    
                    if len(two_prices) >= 2:
                        # We have both unit price and total - can infer quantity!
                        unit_price = float(two_prices[0].replace(',', '.'))
                        total_price = float(two_prices[1].replace(',', '.'))
                        
                        # Infer quantity: qty = total / unit
                        if unit_price > 0 and total_price >= unit_price:
                            quantity = round(total_price / unit_price)
                            if quantity < 1:
                                quantity = 1
                            logger.info(f"Inferred quantity for {item_name}: {total_price}/{unit_price} = {quantity}")
                    else:
                        # Only one price - cannot infer quantity, assume 1
                        total_price = extract_price(price_cell)
                        unit_price = total_price
                        quantity = 1
                    
                elif len(cells) == 3:
                    # Format: [qty, item_name, price] or [item_name, unit_price, total_price]
                    if cells[0].isdigit():
                        quantity = int(cells[0])
                        item_name = cells[1]
                        total_price = extract_price(cells[2])
                        # Calculate unit price if we have quantity
                        if total_price and quantity > 0:
                            unit_price = round(total_price / quantity, 2)
                    else:
                        item_name = cells[0]
                        unit_price = extract_price(cells[1])
                        total_price = extract_price(cells[2])
                        # Calculate quantity if we have both prices
                        if unit_price and total_price and unit_price > 0:
                            quantity = max(1, round(total_price / unit_price))
                        
                elif len(cells) == 4:
                    # Detect column mapping from header or use defaults
                    if col_order and 'name' in col_order:
                        # Use detected column order (e.g., ITEM, QTY, PRICE, VALUE)
                        name_idx = col_order.get('name', 0)
                        qty_idx = col_order.get('qty', 1)
                        up_idx = col_order.get('unit_price', 2)
                        tp_idx = col_order.get('total_price', 3)
                    else:
                        # Default: [qty, item_name, unit_price, total_price]
                        # Auto-detect: if cells[0] can't be parsed as a number, swap to [name, qty, price, value]
                        try:
                            int(float(cells[0].strip()))
                            name_idx, qty_idx, up_idx, tp_idx = 1, 0, 2, 3
                        except (ValueError, AttributeError):
                            name_idx, qty_idx, up_idx, tp_idx = 0, 1, 2, 3

                    item_name = cells[name_idx]

                    qty_from_ocr = None
                    if cells[qty_idx] and cells[qty_idx].strip():
                        try:
                            qty_from_ocr = int(float(cells[qty_idx].strip()))
                        except:
                            qty_from_ocr = None

                    price_col_up = extract_price(cells[up_idx])
                    price_col_tp = extract_price(cells[tp_idx])

                    if price_col_up and price_col_tp:
                        unit_price = price_col_up
                        total_price = price_col_tp
                        if qty_from_ocr:
                            quantity = qty_from_ocr
                        elif unit_price > 0:
                            quantity = round(total_price / unit_price)
                        else:
                            quantity = 1

                    elif price_col_up and not price_col_tp:
                        unit_price = price_col_up
                        quantity = qty_from_ocr if qty_from_ocr else 1
                        total_price = round(unit_price * quantity, 2)

                    elif price_col_tp and not price_col_up:
                        total_price = price_col_tp
                        unit_price = total_price
                        quantity = 1

                    else:
                        continue
                        
                else:
                    # Unknown format - try to extract name and price from available cells
                    for i, cell in enumerate(cells):
                        if cell and not cell.isdigit() and len(cell) > 2:
                            if not any(c.isdigit() for c in cell):
                                item_name = cell
                            elif re.match(r'^\d+[.,]\d{2}$', cell.strip()):
                                total_price = extract_price(cell)
                    if not total_price and cells:
                        total_price = extract_price(cells[-1])
                    unit_price = total_price
                
                # Clean up item name
                if item_name:
                    item_name = item_name.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                    item_name = item_name.strip()
                
                # Skip if item name is too short or looks like a number
                if not item_name or len(item_name) < 2:
                    continue
                if item_name.replace('.', '').replace(',', '').isdigit():
                    continue
                
                # Add valid item with granular pricing data
                if item_name and total_price and total_price > 0:
                    item_data = {
                        "name": item_name,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": total_price,
                        # Keep 'price' for backward compatibility
                        "price": total_price
                    }
                    result["items"].append(item_data)
                    logger.debug(f"Extracted item: {item_name} x{quantity} @ R{unit_price} = R{total_price}")
            
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
