# 🎰 Retail Rewards Platform

A South African retail receipt lottery platform where customers upload shopping receipts via WhatsApp for a chance to win back their entire spend in daily draws.

![Platform](https://img.shields.io/badge/Platform-South%20Africa-green)
![Currency](https://img.shields.io/badge/Currency-ZAR-blue)
![Tech](https://img.shields.io/badge/Stack-FastAPI%20%2B%20React%20%2B%20MongoDB-purple)

## 📋 Overview

Customers shop at retail stores (Checkers, Pick n Pay, Woolworths, etc.), take a photo of their receipt, and send it via WhatsApp. The system:

1. **Extracts data** from the receipt using AI (LandingAI ADE)
2. **Geolocates the shop** from the receipt address
3. **Captures customer location** when they upload
4. **Detects fraud** by comparing shop vs upload location distance
5. **Enters valid receipts** into daily prize draws
6. **Notifies winners** via WhatsApp

## 🚀 Features

### Customer Features
- 📱 Upload receipts via WhatsApp
- 📍 Automatic geolocation tracking
- 🎫 View receipt history and status
- 🏆 Track winnings and draw results
- 💬 WhatsApp bot commands (HELP, RECEIPTS, WINS, STATUS)

### Admin Features
- 📊 Analytics dashboard (spending patterns, popular shops, time trends)
- 🗺️ Interactive map of shops and customer activity
- 🎲 Daily draw management (automatic at midnight UTC)
- 🛡️ Fraud detection with manual review system
- 📈 Customer behavior insights

### Fraud Detection
| Distance | Status | Action |
|----------|--------|--------|
| < 50km | ✅ Valid | Auto-approved for draw |
| 50-100km | ⚠️ Review | Manual review suggested |
| 100-200km | 🟠 Suspicious | Needs verification |
| > 200km | 🔴 Flagged | Blocked from draw |

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Customer      │     │   WhatsApp      │     │   FastAPI       │
│   WhatsApp      │────▶│   Baileys       │────▶│   Backend       │
│   App           │     │   Service       │     │   (Python)      │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌─────────────────┐              │
                        │   LandingAI     │◀─────────────┤
                        │   ADE (OCR)     │              │
                        └─────────────────┘              │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React         │     │   MongoDB       │     │   Qdrant        │
│   Frontend      │◀───▶│   Database      │     │   Vector Store  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                        ┌─────────────────┐              │
                        │   Geolocation   │◀─────────────┘
                        │   + Fraud Det.  │
                        └─────────────────┘
```

### Key Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Receipt OCR | LandingAI ADE (dpt-2-latest) | Extract shop, items, amounts with grounding |
| Vector Search | Qdrant + sentence-transformers | Semantic receipt search |
| Database | MongoDB | Store receipts, customers, shops, draws |
| Fraud Detection | Haversine distance | Compare shop vs upload GPS |
| Scheduler | APScheduler | Midnight daily draws |
| WhatsApp | Baileys (Node.js) | Customer interaction |

## 📁 Project Structure

```
/app
├── backend/
│   ├── server.py           # FastAPI application
│   ├── requirements.txt    # Python dependencies
│   └── .env               # Environment variables
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LandingPage.jsx
│   │   │   ├── CustomerDashboard.jsx
│   │   │   ├── MapView.jsx
│   │   │   ├── DrawsPage.jsx
│   │   │   ├── AdminAnalytics.jsx
│   │   │   ├── FraudDetection.jsx
│   │   │   └── WhatsAppSetup.jsx
│   │   ├── App.js
│   │   └── index.css
│   └── package.json
├── whatsapp-service/
│   ├── index.js            # Baileys WhatsApp service
│   └── package.json
└── README.md
```

## 🛠️ Setup Instructions

### Prerequisites
- Node.js 18+
- Python 3.11+
- MongoDB
- WhatsApp account for bot

### 1. Backend Setup

```bash
cd /app/backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
# Edit .env file with your settings:
# - MONGO_URL (already configured)
# - LANDINGAI_API_KEY (get from https://landing.ai)

# Start server (handled by supervisor)
sudo supervisorctl restart backend
```

### 2. Frontend Setup

```bash
cd /app/frontend

# Install dependencies
yarn install

# Start development server (handled by supervisor)
sudo supervisorctl restart frontend
```

### 3. WhatsApp Service Setup

```bash
cd /app/whatsapp-service

# Install dependencies
npm install

# Start service
npm start

# Scan QR code with WhatsApp app:
# Settings → Linked Devices → Link a Device
```

### 4. Load Demo Data

```bash
# Seed South African demo data with fraud scenarios
curl -X POST http://localhost:8001/api/demo/seed
```

## 📱 WhatsApp Bot Commands

| Command | Description |
|---------|-------------|
| `HELP` | Show available commands |
| `RECEIPTS` | View recent uploaded receipts |
| `WINS` | Check winning history |
| `STATUS` | Today's draw status |
| `BALANCE` | Total stats (receipts, spent, won) |
| *Send photo* | Upload receipt for draw entry |
| *Share location* | Capture GPS for fraud detection |

## 🔌 API Endpoints

### Receipts
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/receipts/upload` | Upload receipt (form data) |
| POST | `/api/receipts/process-image` | Process receipt image (WhatsApp) |
| POST | `/api/receipts/search` | **Semantic search** (e.g., "milk purchases") |
| GET | `/api/receipts/customer/{phone}` | Get customer's receipts |
| GET | `/api/receipts` | List all receipts |

### Draws
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/draws/run` | Run daily draw |
| GET | `/api/draws` | List all draws |
| GET | `/api/draws/{date}` | Get draw by date |
| GET | `/api/draws/winner/{phone}` | Get customer's wins |

### Fraud Detection
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/fraud/stats` | Fraud statistics |
| GET | `/api/fraud/flagged` | Flagged receipts |
| GET | `/api/fraud/thresholds` | Distance thresholds |
| POST | `/api/fraud/review/{id}` | Approve/reject receipt |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/overview` | Platform statistics |
| GET | `/api/analytics/spending-by-day` | Daily spending trend |
| GET | `/api/analytics/popular-shops` | Top shops by receipts |
| GET | `/api/analytics/top-spenders` | Top spending customers |
| GET | `/api/analytics/receipts-by-hour` | Hourly distribution |

### Vector Store (Semantic Search)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/vector-store/stats` | Vector store status |
| POST | `/api/receipts/search` | Semantic receipt search |

### Scheduler
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scheduler/status` | Scheduler status |
| POST | `/api/scheduler/trigger-draw` | Manual draw trigger |

## 🗄️ Database Schema

### Collections

**customers**
```json
{
  "id": "uuid",
  "phone_number": "+27821234567",
  "name": "Thabo Mokoena",
  "total_receipts": 15,
  "total_spent": 12500.00,
  "total_wins": 2,
  "total_winnings": 1850.00
}
```

**receipts**
```json
{
  "id": "uuid",
  "customer_phone": "+27821234567",
  "shop_name": "Checkers Sandton",
  "amount": 350.50,
  "currency": "ZAR",
  "shop_latitude": -26.1076,
  "shop_longitude": 28.0567,
  "upload_latitude": -26.1102,
  "upload_longitude": 28.0543,
  "distance_km": 3.2,
  "fraud_flag": "valid",
  "fraud_score": 3,
  "status": "processed"
}
```

**shops**
```json
{
  "id": "uuid",
  "name": "Checkers Sandton City",
  "address": "Sandton City Mall, Rivonia Rd",
  "latitude": -26.1076,
  "longitude": 28.0567,
  "receipt_count": 245,
  "total_sales": 125000.00
}
```

**draws**
```json
{
  "id": "uuid",
  "draw_date": "2026-01-04",
  "total_receipts": 82,
  "total_amount": 65000.00,
  "winner_customer_phone": "+27821234567",
  "prize_amount": 1250.00,
  "status": "completed"
}
```

## ⚙️ Configuration

### Environment Variables

**Backend (.env)**
```env
MONGO_URL=mongodb://...
DB_NAME=retail_rewards
LANDINGAI_API_KEY=your_key_here
WHATSAPP_SERVICE_URL=http://localhost:3001
```

**Frontend (.env)**
```env
REACT_APP_BACKEND_URL=https://your-domain.com
```

### Fraud Thresholds

Edit in `server.py`:
```python
FRAUD_THRESHOLD_VALID = 50      # km - auto-approved
FRAUD_THRESHOLD_REVIEW = 100    # km - needs review
FRAUD_THRESHOLD_SUSPICIOUS = 200 # km - suspicious
# > 200km = flagged/blocked
```

## 🎯 Production Checklist

- [ ] Set up official WhatsApp Business API (Twilio/Meta Cloud API)
- [ ] Configure LandingAI API key for receipt OCR
- [ ] Set up cloud storage for receipt images (S3/GCS)
- [ ] Configure SSL certificates
- [ ] Set up MongoDB Atlas for production database
- [ ] Enable automated backups
- [ ] Configure POPIA-compliant privacy policy
- [ ] Set up prize fulfillment mechanism (EFT/vouchers)
- [ ] Register business for WhatsApp Business verification

## 🇿🇦 Supported South African Retailers

- Checkers
- Pick n Pay
- Woolworths
- Shoprite
- Spar
- Engen
- Shell
- Dis-Chem
- Clicks
- Game
- Makro
- *And more...*

## 📄 License

MIT License - See LICENSE file for details.

## 🤝 Support

For issues or questions, please open a GitHub issue or contact the development team.

---

Built with ❤️ for South African retail customers
