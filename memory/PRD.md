# Retail Rewards Platform - PRD

## Original Problem Statement
Create a retail module where customers buy items from retail shops (any retail) by cash/credit card, take a picture of the receipt slip, and upload it via WhatsApp. The system captures receipt data to the database, geo-locates the shop they bought from, and geo-locates the point when they upload the receipt. As an incentive, daily customers stand a chance to win back their spend through a random draw.

## Complete Workflow
1. **Customer uploads receipt photo via WhatsApp** 
2. **WhatsApp Cloud API webhook receives image + optional location**
3. **LandingAI ADE extracts: shop name, amount, items, address**
4. **Receipt image stored + structured data saved to MongoDB**
5. **Geolocate shop from receipt data**
6. **Geolocate customer's upload position (from WhatsApp location share)**
7. **Fraud detection: Calculate distance between shop and upload location**
8. **Receipt enters daily draw pool (if not flagged)**
9. **Midnight UTC: Scheduler runs random draw**
10. **Winner notified via WhatsApp Cloud API**

## User Personas
1. **Retail Customer**: Shops at various retail stores, sends receipt photos via WhatsApp
2. **Platform Admin**: Manages draws, views analytics, monitors fraud, reviews flagged receipts
3. **Business Analyst**: Uses aggregated data for market research

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + Leaflet Maps + Recharts
- **Backend**: FastAPI (Python) with async endpoints + APScheduler
- **Database**: MongoDB (customers, receipts, shops, draws)
- **WhatsApp**: Meta WhatsApp Cloud API (Official)
- **OCR**: LandingAI ADE + Qdrant vector search
- **Fraud Detection**: Haversine distance calculation

## What's Been Implemented (January 10, 2026)

### ✅ WhatsApp Cloud API Integration (COMPLETE)
- Full migration from Baileys to official Meta WhatsApp Cloud API
- Webhook for receiving messages (`/api/whatsapp/webhook`)
- Send text messages, receipt confirmations, winner notifications
- Download media (receipt images) from WhatsApp
- Bot commands: HELP, RECEIPTS, WINS, STATUS, BALANCE
- Message read receipts

### ✅ Backend APIs
- Customer CRUD endpoints + location tracking
- Receipt upload (manual form + WhatsApp) with geolocation
- Receipt image processing endpoint (`/api/receipts/process-image`)
- LandingAI ADE integration (needs API key for full OCR)
- Shop auto-detection, creation, and geocoding
- Daily random draw system with WhatsApp winner notification
- **APScheduler** - automated daily draw at midnight UTC
- Analytics endpoints (overview, spending, shops, customers, time)
- Map data endpoints
- Semantic search via Qdrant vector store

### ✅ Fraud Detection System
- Haversine distance calculation between shop and upload location
- Fraud risk thresholds: Valid (<50km), Review (50-100km), Suspicious (100-200km), Flagged (>200km)
- Admin review page for flagged receipts
- Approve/reject workflow

### ✅ Frontend Pages
- Landing page with stats
- Customer dashboard with receipts
- Interactive map (Leaflet, centered on South Africa)
- Draws page with winners
- Admin analytics dashboard
- Fraud detection/review page

## Pending Items

### P0 - High Priority
- None (core functionality complete)

### P1 - Enhancement
- Configure LandingAI API key for full OCR capability (currently falls back to manual entry)
- Set up WhatsApp webhook URL in Meta Business dashboard

### P2 - Future
- Prize fulfillment mechanism (EFT, voucher codes)
- Terms & Conditions / Privacy Policy pages (POPIA compliance)
- Production infrastructure (Cloud hosting, MongoDB Atlas, S3 for images)

## Key Files
- `/app/backend/server.py` - Main API server
- `/app/backend/whatsapp_cloud.py` - WhatsApp Cloud API client
- `/app/backend/receipt_processor.py` - LandingAI OCR logic
- `/app/backend/vector_store.py` - Qdrant vector store
- `/app/backend/.env` - Environment configuration

## Environment Variables Required
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
WHATSAPP_PHONE_NUMBER_ID=993738803815711
WHATSAPP_ACCESS_TOKEN=<your-access-token>
WHATSAPP_VERIFY_TOKEN=retail_rewards_webhook_2026
WHATSAPP_API_VERSION=v23.0
LANDINGAI_API_KEY=<your-landingai-key>
```

## API Endpoints
- `GET /api/health` - Health check
- `GET /api/whatsapp/status` - WhatsApp connection status
- `POST /api/whatsapp/webhook` - Receive WhatsApp messages
- `GET /api/whatsapp/webhook` - Webhook verification
- `POST /api/whatsapp/send` - Send WhatsApp message
- `POST /api/receipts/process-image` - Process receipt image
- `GET /api/fraud/flagged` - Get flagged receipts
- `POST /api/fraud/review/{id}` - Approve/reject receipt
- `POST /api/draws/run` - Trigger daily draw
- `GET /api/analytics/overview` - Platform stats
