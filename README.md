# Receipt-to-Win: Retail Rewards Platform

A South African retail receipt lottery platform where customers upload shopping receipts via WhatsApp for a chance to win back their entire spend in daily draws.

![Platform](https://img.shields.io/badge/Platform-South%20Africa-green)
![Currency](https://img.shields.io/badge/Currency-ZAR-blue)
![Stack](https://img.shields.io/badge/Stack-FastAPI%20%2B%20React%20%2B%20MongoDB-purple)
![Status](https://img.shields.io/badge/Status-MVP%20Complete-brightgreen)

## Table of Contents
1. [Project Overview](#project-overview)
2. [Core Workflow](#core-workflow)
3. [Architecture](#architecture)
4. [Features](#features)
5. [Technology Stack](#technology-stack)
6. [Project Structure](#project-structure)
7. [API Reference](#api-reference)
8. [Database Schema](#database-schema)
9. [Third-Party Integrations](#third-party-integrations)
10. [Setup & Installation](#setup--installation)
11. [Configuration](#configuration)
12. [Development History](#development-history)
13. [Known Issues & Roadmap](#known-issues--roadmap)

---

## Project Overview

### Business Concept
Customers shop at any South African retail store (Checkers, Pick n Pay, Woolworths, Shoprite, etc.), take a photo of their receipt, and submit it via WhatsApp or web upload. The system:

1. **Extracts data** from the receipt using AI-powered OCR (LandingAI ADE)
2. **Geolocates the shop** from the receipt address using Google Maps API
3. **Captures customer location** at upload time for fraud detection
4. **Calculates fraud risk** by comparing shop vs upload location distance
5. **Enters valid receipts** into daily prize draws
6. **Notifies winners** via WhatsApp

### Value Proposition
- **For Customers**: Free lottery - win back your entire purchase amount daily
- **For Business**: Rich retail transaction data for analytics, customer behavior insights, and B2B opportunities

---

## Core Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CUSTOMER JOURNEY                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. SHOP           2. CAPTURE          3. SUBMIT         4. WIN        │
│  ────────          ───────────         ──────────        ─────         │
│  Buy items at      Take photo of       Send via          Daily draw    │
│  any SA retailer   receipt             WhatsApp          at midnight   │
│                                        (or web upload)                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM PROCESSING                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Receipt Image → OCR Extraction → Geocoding → Fraud Check → Draw Entry │
│       │              │                │            │            │      │
│       ▼              ▼                ▼            ▼            ▼      │
│  Convert format  Extract:         Locate shop   Calculate    Store in  │
│  (HEIC→JPEG)    - Shop name       via Google    distance     MongoDB   │
│                 - Items           Maps API      (Haversine)            │
│                 - Total amount                                         │
│                 - Address                                              │
│                 - Postal code                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### High-Level Architecture

```
                                    ┌──────────────────────┐
                                    │   Meta WhatsApp      │
                                    │   Cloud API          │
                                    └──────────┬───────────┘
                                               │
                                               │ Webhook
                                               ▼
┌─────────────┐    HTTP API     ┌──────────────────────────┐
│   React     │ ◄──────────────►│       FastAPI Backend    │
│   Frontend  │                 │       (Python 3.11+)     │
│   (Port 3000)                 │       (Port 8001)        │
└─────────────┘                 └──────────┬───────────────┘
                                           │
            ┌──────────────────────────────┼──────────────────────────────┐
            │                              │                              │
            ▼                              ▼                              ▼
┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
│     MongoDB         │      │   LandingAI ADE     │      │   Google Maps API   │
│     Database        │      │   (OCR Engine)      │      │   (Geocoding)       │
└─────────────────────┘      └─────────────────────┘      └─────────────────────┘
            │
            │
            ▼
┌─────────────────────┐
│   Qdrant Vector     │
│   Store (Search)    │
└─────────────────────┘
```

### Key Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | React 19 + Tailwind CSS + Shadcn UI | Customer dashboard, admin pages, map views |
| **Backend** | FastAPI (async) | REST API, business logic, scheduler |
| **Database** | MongoDB (Motor async driver) | Store customers, receipts, shops, draws |
| **OCR Engine** | LandingAI ADE (dpt-2-latest) | Extract text and structure from receipt images |
| **Geocoding** | Google Maps Geocoding API | Convert addresses to coordinates |
| **Vector Search** | Qdrant + OpenAI Embeddings | Semantic search across receipts |
| **Messaging** | Meta WhatsApp Cloud API | Customer notifications, receipt submission |
| **Scheduler** | APScheduler | Automated daily draws at midnight UTC |

---

## Features

### Customer Features
- Upload receipts via WhatsApp or web interface
- Automatic OCR extraction of shop, items, and total
- View receipt history with full details (image, items, location)
- Track winnings and draw participation
- WhatsApp bot commands: HELP, RECEIPTS, WINS, STATUS, BALANCE

### Admin Features
- Analytics dashboard (spending patterns, popular shops, time trends)
- Interactive map of shops and customer activity (Leaflet)
- Daily draw management (automatic at midnight UTC)
- Fraud detection with manual review system
- Geocoding management (batch geocoding, stats)

### Fraud Detection System
| Distance | Status | Action |
|----------|--------|--------|
| < 50km | Valid | Auto-approved for draw |
| 50-100km | Review | Manual review suggested |
| 100-200km | Suspicious | Needs verification |
| > 200km | Flagged | Blocked from draw |

### OCR Capabilities
- **Image Formats**: JPEG, PNG, HEIC (iPhone), WebP (Android)
- **Auto-conversion**: All formats converted to optimized JPEG
- **Extraction**: Shop name, address, postal code, items (name, qty, unit price, total), grand total
- **Schema-based extraction**: Uses LandingAI's structured extraction for better accuracy
- **Multi-column table parsing**: Handles 2, 3, and 4 column receipt formats

---

## Technology Stack

### Backend
- **Python 3.11+**
- **FastAPI** - Async web framework
- **Motor** - Async MongoDB driver
- **APScheduler** - Background job scheduling
- **Pydantic** - Data validation
- **httpx** - Async HTTP client
- **geopy** - Geographic utilities
- **pillow** + **pillow-heif** - Image processing
- **landingai-ade** - OCR engine

### Frontend
- **React 19**
- **Tailwind CSS** - Styling
- **Shadcn/UI** - Component library
- **Framer Motion** - Animations
- **Leaflet** - Maps
- **Recharts** - Charts
- **Axios** - HTTP client
- **Sonner** - Toast notifications

### Infrastructure
- **MongoDB** - Document database
- **Qdrant** - Vector database for semantic search
- **Meta WhatsApp Cloud API** - Messaging
- **Google Maps API** - Geocoding
- **LandingAI** - OCR

---

## Project Structure

```
/app
├── backend/
│   ├── .env                    # Environment variables (API keys)
│   ├── requirements.txt        # Python dependencies
│   ├── server.py              # Main FastAPI application (1900+ lines)
│   │   ├── API routes (customers, receipts, draws, fraud, analytics)
│   │   ├── WhatsApp webhook handlers
│   │   ├── Background tasks and scheduler
│   │   └── Business logic (fraud detection, geocoding)
│   ├── receipt_processor.py   # LandingAI OCR integration (850 lines)
│   │   ├── Image format conversion (HEIC, WebP → JPEG)
│   │   ├── Schema-based extraction
│   │   ├── HTML table parsing (multi-column)
│   │   └── Text parsing fallback
│   ├── geocoding.py           # Google Maps geocoding service
│   │   ├── Address → coordinates
│   │   ├── Postal code prioritization
│   │   └── Local SA fallback database
│   ├── vector_store.py        # Qdrant vector store wrapper
│   └── whatsapp_cloud.py      # WhatsApp Cloud API client
│       ├── Send text messages
│       ├── Download media
│       ├── Webhook parsing
│       └── Message templates
│
├── frontend/
│   ├── src/
│   │   ├── App.js             # Router and layout
│   │   ├── index.css          # Global styles (Tailwind)
│   │   ├── pages/
│   │   │   ├── LandingPage.jsx       # Hero, features, stats
│   │   │   ├── CustomerDashboard.jsx # Receipt history, detail modal
│   │   │   ├── UploadReceipt.jsx     # Manual web upload
│   │   │   ├── MapView.jsx           # Shop/receipt map
│   │   │   ├── DrawsPage.jsx         # Draw history, winners
│   │   │   ├── AdminAnalytics.jsx    # Admin dashboard
│   │   │   └── FraudDetection.jsx    # Fraud review page
│   │   └── components/
│   │       └── ui/            # Shadcn components
│   └── package.json
│
├── memory/
│   ├── PRD.md                 # Product requirements document
│   ├── CHANGELOG.md           # Development history
│   └── ROADMAP.md             # Future plans
│
└── README.md                  # This file
```

---

## API Reference

### Authentication
Currently no authentication required. Phone number is used as customer identifier.

### Endpoints

#### Health & Status
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/scheduler/status` | Scheduler status |

#### Customers
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/customers` | Create/get customer |
| GET | `/api/customers/{phone}` | Get customer by phone |
| GET | `/api/customers` | List all customers |
| POST | `/api/customers/location` | Update customer location |

#### Receipts
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/receipts/process-image` | Process receipt image (OCR) |
| POST | `/api/receipts/upload` | Manual form upload |
| GET | `/api/receipts/customer/{phone}` | Get customer's receipts |
| GET | `/api/receipts/{id}` | Get receipt (no image) |
| GET | `/api/receipts/{id}/full` | Get full receipt with image |
| GET | `/api/receipts` | List receipts (with filters) |
| POST | `/api/receipts/search` | Semantic search |

#### Draws
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/draws/run` | Run daily draw |
| GET | `/api/draws` | List all draws |
| GET | `/api/draws/{date}` | Get draw by date |
| GET | `/api/draws/winner/{phone}` | Get customer's wins |
| POST | `/api/scheduler/trigger-draw` | Manual draw trigger |

#### Fraud Detection
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/fraud/flagged` | Get flagged receipts |
| GET | `/api/fraud/stats` | Fraud statistics |
| GET | `/api/fraud/thresholds` | Distance thresholds |
| POST | `/api/fraud/review/{id}` | Approve/reject receipt |

#### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/overview` | Platform stats |
| GET | `/api/analytics/spending-by-day` | Daily spending |
| GET | `/api/analytics/popular-shops` | Top shops |
| GET | `/api/analytics/top-spenders` | Top customers |
| GET | `/api/analytics/receipts-by-hour` | Hourly distribution |

#### Geocoding
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/geocode/shop/{id}` | Geocode single shop |
| POST | `/api/geocode/shops/batch` | Batch geocode shops |
| GET | `/api/geocode/stats` | Geocoding statistics |
| POST | `/api/geocode/address` | Test address geocoding |

#### WhatsApp
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/whatsapp/webhook` | Webhook verification |
| POST | `/api/whatsapp/webhook` | Receive messages |
| GET | `/api/whatsapp/status` | Connection status |
| POST | `/api/whatsapp/send` | Send message |

---

## Database Schema

### Collections

**customers**
```json
{
  "id": "uuid",
  "phone_number": "27769695462",
  "name": "Thabo Mokoena",
  "total_receipts": 15,
  "total_spent": 12500.00,
  "total_wins": 2,
  "total_winnings": 1850.00,
  "created_at": "2026-01-15T10:30:00Z"
}
```

**receipts**
```json
{
  "id": "uuid",
  "customer_id": "uuid",
  "customer_phone": "27769695462",
  "shop_id": "uuid",
  "shop_name": "Checkers Constantia",
  "amount": 350.50,
  "currency": "ZAR",
  "items": [
    {
      "name": "MILK 2L FULL CREAM",
      "quantity": 2,
      "unit_price": 32.99,
      "total_price": 65.98,
      "price": 65.98
    }
  ],
  "raw_text": "...",
  "image_data": "base64...",
  "upload_latitude": -34.0230,
  "upload_longitude": 18.4260,
  "upload_address": "Constantia Village, Cape Town",
  "shop_latitude": -34.0235,
  "shop_longitude": 18.4255,
  "shop_address": "Constantia Village Shopping Centre, 7848",
  "distance_km": 0.5,
  "fraud_flag": "valid",
  "fraud_score": 5,
  "fraud_reason": null,
  "status": "processed",
  "grounding": {...},
  "created_at": "2026-01-15T10:30:00Z"
}
```

**shops**
```json
{
  "id": "uuid",
  "name": "Checkers Constantia",
  "address": "Constantia Village, Cape Town, 7848",
  "latitude": -34.0235,
  "longitude": 18.4255,
  "geocoded_address": "Constantia Village Shopping Centre, Spaanschemat River Rd, Constantia, Cape Town, 7806, South Africa",
  "geocode_confidence": "high",
  "receipt_count": 245,
  "total_sales": 125000.00,
  "created_at": "2026-01-10T08:00:00Z"
}
```

**draws**
```json
{
  "id": "uuid",
  "draw_date": "2026-01-15",
  "total_receipts": 82,
  "total_amount": 65000.00,
  "winner_receipt_id": "uuid",
  "winner_customer_id": "uuid",
  "winner_customer_phone": "27769695462",
  "prize_amount": 1250.00,
  "status": "completed",
  "created_at": "2026-01-16T00:00:00Z"
}
```

---

## Third-Party Integrations

### 1. Meta WhatsApp Cloud API
- **Purpose**: Sending/receiving WhatsApp messages
- **Credentials Required**:
  - `WHATSAPP_PHONE_NUMBER_ID`: Your registered phone number ID
  - `WHATSAPP_ACCESS_TOKEN`: Permanent access token
  - `WHATSAPP_WABA_ID`: Business Account ID
  - `WHATSAPP_VERIFY_TOKEN`: Webhook verification token
- **Current Status**: Outbound messaging working. Inbound requires production webhook URL.

### 2. LandingAI ADE (Agentic Document Extraction)
- **Purpose**: OCR and structured data extraction from receipt images
- **Model**: `dpt-2-latest`
- **Credentials Required**:
  - `LANDINGAI_API_KEY`: API key from landing.ai
- **Features Used**:
  - `parse()`: General text extraction with bounding boxes
  - `extract()`: Schema-based structured extraction

### 3. Google Maps Geocoding API
- **Purpose**: Convert addresses to coordinates, and vice versa
- **Credentials Required**:
  - `GOOGLE_MAPS_API_KEY`: API key with Geocoding API enabled
- **Features Used**:
  - Forward geocoding (address → coordinates)
  - Reverse geocoding (coordinates → address)
  - Region biasing for South Africa

### 4. OpenAI API
- **Purpose**: Generate text embeddings for semantic search
- **Credentials Required**:
  - `OPENAI_API_KEY`: API key
- **Note**: Currently showing 401 errors (key may be invalid). Non-blocking.

### 5. Qdrant Vector Database
- **Purpose**: Store and search receipt embeddings
- **Status**: In-memory mode (no external service required)

---

## Setup & Installation

### Prerequisites
- Node.js 18+
- Python 3.11+
- MongoDB (local or Atlas)
- API keys for LandingAI, Google Maps, WhatsApp

### Backend Setup

```bash
cd /app/backend

# Install dependencies
pip install -r requirements.txt

# Configure environment (edit .env file)
# Required keys: MONGO_URL, LANDINGAI_API_KEY, GOOGLE_MAPS_API_KEY, WHATSAPP_*

# Start server (via supervisor)
sudo supervisorctl restart backend
```

### Frontend Setup

```bash
cd /app/frontend

# Install dependencies
yarn install

# Start development server (via supervisor)
sudo supervisorctl restart frontend
```

### Load Demo Data

```bash
curl -X POST http://localhost:8001/api/demo/seed
```

---

## Configuration

### Environment Variables

**Backend (.env)**
```env
# Database
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database

# WhatsApp Cloud API (KlpIt Tech / ReceiptsProd2026)
WHATSAPP_PHONE_NUMBER_ID=955997190937092
WHATSAPP_WABA_ID=2129214027857484
WHATSAPP_ACCESS_TOKEN=EAAWtMDQgWZCYBQ...
WHATSAPP_VERIFY_TOKEN=receipts_verify_2026
WHATSAPP_API_VERSION=v20.0
WHATSAPP_TEMPLATE_NAME=receipts_welcome
WHATSAPP_TEMPLATE_LANGUAGE=en

# LandingAI OCR
LANDINGAI_API_KEY=your_key_here

# OpenAI (for embeddings)
OPENAI_API_KEY=your_key_here

# Google Maps
GOOGLE_MAPS_API_KEY=your_key_here
```

**Frontend (.env)**
```env
REACT_APP_BACKEND_URL=https://your-domain.com
```

### Fraud Detection Thresholds
Edit in `server.py`:
```python
FRAUD_THRESHOLD_VALID = 50      # km - auto-approved
FRAUD_THRESHOLD_REVIEW = 100    # km - needs review
FRAUD_THRESHOLD_SUSPICIOUS = 200 # km - suspicious
# > 200km = flagged/blocked
```

---

## Development History

### Phase 1: Foundation (Feb 2026)
- Basic FastAPI backend with MongoDB
- React frontend with Tailwind CSS
- Customer, receipt, shop, draw models
- Simple receipt upload (manual form)

### Phase 2: WhatsApp Integration
- Migrated from Baileys to official Meta WhatsApp Cloud API
- Webhook for receiving messages
- Bot commands (HELP, RECEIPTS, WINS, STATUS)
- Winner notifications

### Phase 3: OCR Implementation
- Integrated LandingAI ADE for receipt processing
- HEIC/WebP image format support
- Multi-column table parsing
- Schema-based extraction for items

### Phase 4: Geocoding & Fraud Detection
- Google Maps API integration
- Haversine distance calculation
- Fraud scoring system
- Admin review workflow
- Postal code detection for better accuracy

### Phase 5: UI/UX Enhancements
- Receipt detail modal with full image and items
- Granular item data (quantity, unit price)
- Auto location request on upload page
- WhatsApp confirmation for web uploads

### Phase 6: Production Setup (Current)
- Registered production WhatsApp number (+27 65 561 5874)
- Created managed message template
- Updated credentials for new Meta Business profile
- Outbound messaging verified working

---

## Known Issues & Roadmap

### Critical Issues (P0)
1. **WhatsApp Inbound Messages**: Meta webhook cannot reach preview environment. **Solution**: Deploy to production (Render, Railway) and configure webhook URL.

### Non-Critical Issues (P1)
1. **OCR Robustness**: Some receipt formats cause parsing issues (columns merged). Needs continuous improvement.
2. **OpenAI API**: Key shows 401 error. Vector search non-functional but doesn't block core features.

### Roadmap

#### Near-term
- [ ] Production deployment
- [ ] Configure production webhook URL in Meta Dashboard
- [ ] End-to-end WhatsApp testing

#### Future Features
- **Analytics**: Basket analysis, customer behavior dashboards
- **Monetization**: B2B data sales, targeted promotions, verification API
- **Gamification**: Loyalty tiers, streaks, referral program
- **Compliance**: Terms & Conditions, Privacy Policy (POPIA)
- **Customer Features**: WhatsApp command for receipt history download

---

## Support

For issues or questions, please open a GitHub issue or contact the development team.

---

**Built with passion for South African retail customers**

*KlpIt Tech - ReceiptsProd2026*
