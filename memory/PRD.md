# Retail Rewards Platform - PRD

## Original Problem Statement
Create a retail module where customers buy items from retail shops (any retail) by cash/credit card, take a picture of the receipt slip, and upload it via WhatsApp. The system captures receipt data to the database, geo-locates the shop they bought from, and geo-locates the point when they upload the receipt. As an incentive, daily customers stand a chance to win back their spend through a random draw.

## Complete Workflow
1. **Customer uploads receipt photo via WhatsApp** 
2. **WhatsApp Cloud API webhook receives image + optional location**
3. **LandingAI ADE extracts: shop name, amount, items, address**
4. **Receipt image stored + structured data saved to MongoDB**
5. **Geolocate shop from receipt data using Google Maps API**
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
- **OCR**: LandingAI ADE (with HEIC support) + OpenAI Embeddings + Qdrant vector search
- **Geocoding**: Google Maps Geocoding API
- **Fraud Detection**: Haversine distance calculation

## What's Been Implemented

### Session: February 10, 2026
- **Receipt View Modal on Dashboard**: Added "View" button to customer receipts page with full detail modal showing image, items, location data
- **WhatsApp Confirmation for Web Uploads**: Added background task to send WhatsApp confirmation when receipts are uploaded via web interface

### Session: February 9-10, 2026
- **Dashboard Phone Formatting Fix**: Fixed receipts not loading on `/dashboard` page by auto-formatting phone numbers to include country code (27)
- **HEIC Image Support**: Added automatic conversion of iPhone HEIC images to JPEG before OCR processing
- **Google Maps Geocoding**: Replaced failing Nominatim with Google Maps API for accurate shop location detection
- **Shop Display Names**: Implemented smart naming (e.g., "Shoprite Brackenfell") combining OCR shop name with geocoded location
- **Manual Upload Page**: Created `/upload` page for demo purposes with image upload, location sharing, and OCR processing
- **Fraud Detection Modal**: Added detailed receipt view on Fraud page with image display and item-level data

### Core Features (Complete)
#### ✅ WhatsApp Cloud API Integration
- Full migration from Baileys to official Meta WhatsApp Cloud API
- Webhook for receiving messages (`/api/whatsapp/webhook`)
- Send text messages, receipt confirmations, winner notifications
- Download media (receipt images) from WhatsApp
- Bot commands: HELP, RECEIPTS, WINS, STATUS, BALANCE
- Message read receipts
- **Note**: Inbound webhook blocked in preview environment (network issue)

#### ✅ Backend APIs
- Customer CRUD endpoints + location tracking
- Receipt upload (manual form + WhatsApp) with geolocation
- Receipt image processing endpoint (`/api/receipts/process-image`)
- LandingAI ADE integration for OCR
- Shop auto-detection, creation, and geocoding via Google Maps
- Daily random draw system with WhatsApp winner notification
- **APScheduler** - automated daily draw at midnight UTC
- Analytics endpoints (overview, spending, shops, customers, time)
- Map data endpoints
- Semantic search via Qdrant vector store

#### ✅ Fraud Detection System
- Haversine distance calculation between shop and upload location
- Fraud risk thresholds: Valid (<50km), Review (50-100km), Suspicious (100-200km), Flagged (>200km)
- Admin review page for flagged receipts with detailed view modal
- Approve/reject workflow

#### ✅ Frontend Pages
- Landing page with stats
- Customer dashboard with receipts (now with View button)
- Interactive map (Leaflet, centered on South Africa)
- Draws page with winners
- Admin analytics dashboard
- Fraud detection/review page with image display
- Manual upload page for demos

## Known Issues / Blockers

### P0 - Critical
- **WhatsApp Inbound Messages**: Meta webhook cannot reach preview environment URL. Solution: Deploy to production environment and configure webhook URL in Meta Business Dashboard.

### P1 - Non-blocking
- **OpenAI API Key**: The configured key appears invalid (401 error). Vector store embedding fails but doesn't block core functionality.

## Pending Tasks

### Upcoming
1. **Production Deployment**: Deploy to Render/similar to enable WhatsApp webhook
2. **Receipt Parser Enhancement**: Improve item extraction for restaurant receipts
3. **WhatsApp 24-hour Window**: Document workaround for Meta test number limitations

### Future / Backlog
- Analytics: Basket analysis, customer behavior dashboards
- Monetization: B2B data sales, targeted promotions
- Gamification: Loyalty tiers, streaks, referral program
- Compliance: Terms & Conditions, Privacy Policy (POPIA)
- Customer features: WhatsApp command for receipt history download

## Key Files
- `/app/backend/server.py` - Main API server
- `/app/backend/whatsapp_cloud.py` - WhatsApp Cloud API client
- `/app/backend/receipt_processor.py` - LandingAI OCR logic with HEIC support
- `/app/backend/vector_store.py` - Qdrant vector store
- `/app/backend/geocoding.py` - Google Maps Geocoding service
- `/app/frontend/src/pages/CustomerDashboard.jsx` - Receipt history with view modal
- `/app/frontend/src/pages/FraudDetection.jsx` - Admin review with image modal
- `/app/frontend/src/pages/UploadReceipt.jsx` - Manual upload page

## Environment Variables Required
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
WHATSAPP_PHONE_NUMBER_ID=993738803815711
WHATSAPP_ACCESS_TOKEN=<your-access-token>
WHATSAPP_VERIFY_TOKEN=retail_rewards_webhook_2026
WHATSAPP_API_VERSION=v23.0
LANDINGAI_API_KEY=<your-landingai-key>
OPENAI_API_KEY=<your-openai-key>
GOOGLE_MAPS_API_KEY=<your-google-maps-key>
```

## API Endpoints
- `GET /api/health` - Health check
- `GET /api/whatsapp/webhook` - Webhook verification
- `POST /api/whatsapp/webhook` - Receive WhatsApp messages
- `POST /api/receipts/process-image` - Process receipt image (with WhatsApp notification)
- `POST /api/receipts/upload` - Manual upload (with WhatsApp notification)
- `GET /api/receipts/{id}/full` - Full receipt details with image
- `GET /api/fraud/flagged` - Get flagged receipts
- `POST /api/fraud/review/{id}` - Approve/reject receipt
- `POST /api/draws/run` - Trigger daily draw
- `GET /api/analytics/overview` - Platform stats
- `POST /api/geocode/address` - Test geocoding
