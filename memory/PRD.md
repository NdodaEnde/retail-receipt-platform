# Retail Rewards Platform - PRD

## Original Problem Statement
Create a retail module where customers buy items from retail shops (any retail) by cash/credit card, take a picture of the receipt slip, and upload it via WhatsApp. The system captures receipt data to the database, geo-locates the shop they bought from, and geo-locates the point when they upload the receipt. As an incentive, daily customers stand a chance to win back their spend through a random draw.

## Complete Workflow
1. **Customer uploads receipt photo via WhatsApp** 
2. **Baileys Node.js service receives image + optional location**
3. **LandingAI ADE extracts: shop name, amount, items, address**
4. **Receipt image stored + structured data saved to MongoDB**
5. **Geolocate shop from receipt data (or use customer location)**
6. **Geolocate customer's upload position (from WhatsApp location share)**
7. **Receipt enters daily draw pool**
8. **Midnight UTC: Scheduler runs random draw**
9. **Winner notified via WhatsApp**

## User Personas
1. **Retail Customer**: Shops at various retail stores, sends receipt photos via WhatsApp
2. **Platform Admin**: Manages draws, views analytics, monitors customer behavior
3. **Business Analyst**: Uses aggregated data for market research

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + Leaflet Maps + Recharts
- **Backend**: FastAPI (Python) with async endpoints + APScheduler
- **Database**: MongoDB (customers, receipts, shops, draws)
- **WhatsApp Service**: Node.js + Baileys library (separate microservice)
- **OCR**: LandingAI ADE (ready for integration)

## What's Been Implemented (January 4, 2026)

### Backend APIs
- ✅ Customer CRUD endpoints + location tracking
- ✅ Receipt upload (manual form) with geolocation
- ✅ Receipt image processing endpoint (`/api/receipts/process-image`) - ready for WhatsApp
- ✅ LandingAI ADE integration framework (needs API key)
- ✅ Shop auto-detection, creation, and geocoding
- ✅ Daily random draw system with winner notification
- ✅ **APScheduler** - automated daily draw at midnight UTC
- ✅ Analytics endpoints (overview, spending, shops, customers, time)
- ✅ Map data endpoints
- ✅ WhatsApp proxy endpoints (QR, status, send)

### WhatsApp Service (Node.js)
- ✅ Baileys integration code (`/app/whatsapp-service/index.js`)
- ✅ QR code generation and authentication
- ✅ Image receipt download and forwarding to FastAPI
- ✅ Bot commands (HELP, RECEIPTS, WINS, STATUS, BALANCE)
- ✅ Winner notification endpoint
- ⏳ Requires `npm install` and `npm start` to run

### Frontend Pages
- ✅ Landing page with hero section and platform stats
- ✅ Customer dashboard with receipts and wins tabs
- ✅ Receipt upload dialog
- ✅ Interactive map view with shop markers
- ✅ Daily draws page with winner announcement
- ✅ Analytics dashboard (4 tabs: Spending, Shops, Customers, Time)
- ✅ WhatsApp setup page with QR code display

### Scheduler
- ✅ APScheduler configured for midnight UTC daily draws
- ✅ Automatic winner notification via WhatsApp
- ✅ Status endpoint: `/api/scheduler/status`
- ✅ Manual trigger: `/api/scheduler/trigger-draw`

## Required Setup for Full Operation

### 1. Start WhatsApp Service
```bash
cd /app/whatsapp-service
npm install
npm start
```
Then scan the QR code displayed in terminal/frontend with your WhatsApp app.

### 2. LandingAI API Key (for receipt OCR)
Add to `/app/backend/.env`:
```
LANDINGAI_API_KEY=your_api_key_here
```

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/receipts/process-image` | POST | Process receipt image (from WhatsApp) |
| `/api/receipts/upload` | POST | Manual receipt upload |
| `/api/draws/run` | POST | Run draw for specific date |
| `/api/scheduler/status` | GET | Check scheduler status |
| `/api/scheduler/trigger-draw` | POST | Manually trigger draw |
| `/api/whatsapp/qr` | GET | Get QR code for authentication |
| `/api/whatsapp/status` | GET | Check WhatsApp connection |
| `/api/analytics/*` | GET | Various analytics endpoints |

## Prioritized Backlog

### P1 - Ready to Deploy
- [x] Start WhatsApp microservice
- [ ] Configure LandingAI API key for OCR
- [ ] Test end-to-end WhatsApp → Receipt → Draw flow

### P2 - Enhancements
- [ ] Receipt image cloud storage (S3/GCS)
- [ ] Customer authentication
- [ ] Multi-timezone support for draws
- [ ] Export analytics to CSV

### P3 - Future
- [ ] Push notifications
- [ ] Social sharing of wins
- [ ] Referral system
- [ ] Multiple draw tiers
