# Receipt-to-Win: Changelog

All notable changes to this project are documented here.

---

## [0.6.0] - 2026-03-04

### Changed
- **WhatsApp Production Setup**: Updated to new Meta Business profile
  - Business Portfolio: KlpIt Tech
  - App Name: ReceiptsProd2026
  - Phone Number: +27 65 561 5874 (955997190937092)
  - WABA ID: 2129214027857484
  - Template: receipts_welcome (approved)
  - Token: Permanent token (never expires)

### Verified
- Outbound WhatsApp messaging working
- Test message sent successfully to +27 76 969 5462

### Blocked
- Inbound WhatsApp messages (requires production webhook URL)

---

## [0.5.0] - 2026-02-10

### Added
- **Receipt Detail Modal**: "View" button on Customer Dashboard
  - Full receipt image display
  - Item list with quantity and unit price
  - Location data (shop coordinates, upload coordinates, distance)
  - Status badges and fraud information

- **WhatsApp Confirmation for Web Uploads**: Background task sends WhatsApp message after manual upload

### Changed
- Customer Dashboard redesigned with better receipt cards
- Receipt cards now show distance from shop

---

## [0.4.0] - 2026-02-09

### Added
- **HEIC Image Support**: iPhone receipt photos now automatically converted to JPEG
- **WebP Support**: Android receipt photos supported
- **Auto Location Request**: Upload page requests location on page load for fraud detection

### Changed
- **Geocoding Enhancement**: Postal code now prioritized in Google Maps queries
  - Postal code detected from entire receipt text
  - False positives filtered (phone numbers, VAT numbers, prices)
  - Much more accurate shop location (e.g., Blanko Constantia now correctly located)

- **Address Fallback**: If OCR address is garbage (contains "logo", "font", etc.), system uses geocoded address instead

### Fixed
- Phone number formatting on Customer Dashboard (auto-adds 27 country code)
- Receipt images now stored as converted JPEG (not original HEIC)
- Display issues for HEIC images in modals

---

## [0.3.0] - 2026-02-08

### Added
- **Granular Item Data**: Receipt items now include:
  - `quantity`: Number of units purchased
  - `unit_price`: Price per single unit
  - `total_price`: Total for line item
  - Inferred from 2-price columns when available

- **Schema-Based Extraction**: LandingAI `extract()` method used for structured data
- **Multi-Column Table Parsing**: Handles 2, 3, and 4 column receipt formats

### Changed
- Receipt processor refactored for better column handling
- HTML table parsing improved for various POS formats

---

## [0.2.0] - 2026-02-07

### Added
- **Google Maps Geocoding**: Replaced Nominatim with Google Maps API
  - Better accuracy for SA addresses
  - Region biasing to South Africa
  - Higher rate limits

- **Local SA Fallback Database**: Pre-defined coordinates for major suburbs
  - Cape Town suburbs (Constantia, Newlands, Claremont, etc.)
  - Johannesburg suburbs (Sandton, Rosebank, etc.)
  - Garden Route, Winelands, other regions

- **Geocoding Management APIs**:
  - Single shop geocoding
  - Batch geocoding
  - Geocoding statistics

### Fixed
- Shops without coordinates no longer assumed fraudulent

---

## [0.1.0] - 2026-02-06

### Added
- **WhatsApp Cloud API Integration**: Official Meta API
  - Webhook verification endpoint
  - Receive text and image messages
  - Download media files
  - Send text messages
  - Send receipt confirmations
  - Send winner notifications

- **Bot Commands**:
  - HELP: Welcome message
  - RECEIPTS: Recent uploads
  - WINS: Winning history
  - STATUS: Today's draw info
  - BALANCE: Total stats

- **Background Receipt Processing**: Image processing doesn't block webhook response

### Replaced
- Removed Baileys (unofficial WhatsApp library)

---

## [0.0.1] - 2026-02-05

### Initial Release

#### Backend
- FastAPI application with async endpoints
- MongoDB integration via Motor
- APScheduler for daily draws (midnight UTC)
- LandingAI ADE integration for OCR
- Qdrant vector store for semantic search

#### Frontend
- React 19 with Tailwind CSS
- Shadcn UI components
- Framer Motion animations
- Pages: Landing, Dashboard, Map, Draws, Analytics, Fraud

#### Features
- Customer registration (by phone number)
- Manual receipt upload
- Basic OCR extraction (shop, items, total)
- Daily random draw
- Fraud detection (distance-based)
- Analytics dashboard

#### Database
- Collections: customers, receipts, shops, draws
- Indexes on common query fields

---

## Migration Notes

### From 0.5.x to 0.6.x
No breaking changes. Update WhatsApp credentials in `.env`:
```env
WHATSAPP_PHONE_NUMBER_ID=955997190937092
WHATSAPP_WABA_ID=2129214027857484
WHATSAPP_ACCESS_TOKEN=<new_token>
WHATSAPP_VERIFY_TOKEN=receipts_verify_2026
WHATSAPP_API_VERSION=v20.0
```

### From 0.4.x to 0.5.x
No breaking changes. Receipt detail API added.

### From 0.3.x to 0.4.x
No breaking changes. HEIC support requires:
```bash
pip install pillow-heif
```

### From 0.2.x to 0.3.x
Receipt `items` schema enhanced:
```json
// Old
{"name": "Item", "price": 10.00}

// New
{"name": "Item", "quantity": 1, "unit_price": 10.00, "total_price": 10.00, "price": 10.00}
```
Backward compatible - `price` field preserved.

---

*For detailed technical changes, see git commit history.*
