# KlpIT – Retail Receipt Platform

## What it is
A WhatsApp-first receipt lottery platform for South African retail customers.
Customers submit receipts via WhatsApp → OCR extracts data → daily draw at 21:00 SAST.

## Tech Stack
- **Frontend**: React 19, Tailwind CSS, shadcn/ui, Framer Motion, Recharts, Leaflet
- **Backend**: FastAPI (Python, async), Uvicorn
- **Database**: Supabase (PostgreSQL) — NOT MongoDB
- **Storage**: Supabase Storage (receipt images)
- **OCR**: LandingAI ADE (`landingai-ade`)
- **Messaging**: Meta WhatsApp Cloud API
- **Geocoding**: Google Maps API
- **Scheduler**: APScheduler (draw at 19:00 UTC = 21:00 SAST)
- **Deployment**: Render (`render.yaml` at project root)

## Running Locally

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```
Environment variables must be in `backend/.env` (see `backend/.env.example`).

### Frontend
```bash
cd frontend
npm install
REACT_APP_BACKEND_URL=http://localhost:8000 npm start
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/server.py` | All FastAPI routes and business logic (1900+ lines) |
| `backend/whatsapp_cloud.py` | WhatsApp Cloud API client + message templates |
| `backend/database.py` | Supabase database abstraction layer |
| `backend/receipt_processor.py` | LandingAI OCR receipt extraction |
| `backend/geocoding.py` | Google Maps shop geocoding |
| `backend/vector_store.py` | Qdrant semantic search (disabled by default — `available=False`) |
| `backend/schema.sql` | PostgreSQL schema — run once in Supabase SQL editor |
| `frontend/src/App.js` | React router + bottom nav |
| `frontend/src/pages/` | 7 page components |
| `render.yaml` | Render deployment config (both services) |

## Database Tables
`customers` · `shops` · `receipts` · `receipt_items` · `draws`

Run `backend/schema.sql` in the Supabase SQL editor to initialise tables.

## WhatsApp Flow (Two-Step)
1. Customer sends receipt image → bot acknowledges + sends location request button
2. Customer taps location button → receipt is finalised, confirmation sent
3. Receipt stays `pending_location` until step 2 (15-min window)
4. If location not received in 24h → receipt expires

In-memory state:
- `pending_receipts` dict — receipts awaiting location
- `customer_locations` dict — pre-shared locations (if location sent before image)

## Fraud Detection
- **Distance fraud**: upload location vs shop geocoded location (Haversine)
  - Valid <50km · Review 50-100km · Suspicious 100-200km · Flagged >200km
- **Velocity fraud**: implied travel speed >900 km/h between shops → flagged
- **Duplicate fraud**: same customer + same shop + same amount today → flagged
- Customer GPS is NOT required — fraud runs on shop coordinates only

## Draw Schedule
- Runs at **19:00 UTC = 21:00 SAST** every day (APScheduler CronTrigger)
- Picks a random valid receipt from today
- Sends winner notification via WhatsApp

## Deployment (Render)
1. Push to GitHub
2. Render auto-deploys from `render.yaml` (connect repo in Render dashboard)
3. Set environment variables in Render dashboard (see `backend/.env.example`)
4. After backend deploys → set `REACT_APP_BACKEND_URL` in frontend service
5. After frontend deploys → set `CORS_ORIGINS` in backend service
6. Update Meta WhatsApp webhook URL → `https://klpit-api.onrender.com/api/whatsapp/webhook`

**Render free tier note**: backend sleeps after 15 min inactivity.
Use UptimeRobot to ping `https://klpit-api.onrender.com/api/health` every 10 min,
or upgrade to Starter ($7/mo) for always-on.

## Disabled Features (re-enable later)
- **Qdrant semantic search**: `vector_store.available` is `False` when Qdrant not running.
  To re-enable: set up Qdrant Cloud free tier, add `QDRANT_URL` + `QDRANT_API_KEY` env vars.

## WhatsApp Message Types
- **Session messages** (within 24h of customer message): any format, no Meta approval needed
- **Template messages** (proactive after 24h window): must be pre-approved by Meta
  - Winner notifications may need a template if customer's session has expired

## Important Conventions
- Always use `database.py` (`get_database()`) for DB operations — NOT `supabase_db.py`
- All DB writes use Supabase. MongoDB packages in old migration scripts only.
- Currency is ZAR. Amounts stored as float.
- Phone numbers stored WITHOUT `+` prefix in WhatsApp API calls, WITH `+` in DB.
- Draw prize = random % of total daily amount (see `run_daily_draw` in `server.py`)

---

## Required Environment Variables

```
# Database
SUPABASE_URL
SUPABASE_KEY          # service role key (not anon key)

# WhatsApp
WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_WABA_ID
WHATSAPP_ACCESS_TOKEN
WHATSAPP_VERIFY_TOKEN
WHATSAPP_API_VERSION  # default: v23.0

# Integrations
LANDINGAI_API_KEY
GOOGLE_MAPS_API_KEY
OPENAI_API_KEY        # optional — only needed when Qdrant Cloud is enabled

# Server
CORS_ORIGINS          # e.g. https://klpit-web.onrender.com
```

Full template with descriptions: `backend/.env.example`
Secrets (tokens, keys) live in `backend/.env` only — never committed.

---

## Current Status (March 2026)

- ✅ Supabase migration complete (MongoDB fully replaced)
- ✅ Outbound WhatsApp working (production number +27 65 561 5874)
- ✅ Two-step WhatsApp flow implemented (image → location → confirmation)
- ✅ Multi-signal fraud detection (velocity, distance, duplicate)
- ✅ Draw scheduler set to 21:00 SAST
- ⏳ Render deployment pending (render.yaml ready, env vars to be set)
- ❌ Inbound webhook not yet live on production URL (still local/Afrihost proxy)
- ❌ Qdrant semantic search disabled (re-enable with Qdrant Cloud later)

---

## Test Contacts

| Label | Value |
|-------|-------|
| Production WhatsApp number | +27 65 561 5874 |
| Phone Number ID | 955997190937092 |
| WABA ID | 2129214027857484 |
| Webhook verify token | `receipts_verify_2026` |
| Domain | www.klpit.co.za (hosted on Afrihost) |

Access tokens and API keys are in `backend/.env` only.

---

## Supabase Storage

- **Bucket**: `receipts` (public read)
- **Path pattern**: `receipts/{customer_phone}/{receipt_id}.jpg`
- Images uploaded via `storage_helper.py` → `upload_receipt_image()`
- Public URL returned and stored as `image_url` on the receipt record

---

## Development Workflow

**Rule: Task → Verify → Proceed. Never move to the next step until the current one is confirmed working.**

### Deployment Sequence (in order)

| Step | Task | Verified when... |
|------|------|-----------------|
| 1 | Supabase tables exist | `/check-supabase` returns row counts for all 5 tables |
| 2 | Backend runs locally | `GET http://localhost:8000/api/health` returns `{"status": "healthy"}` |
| 3 | WhatsApp outbound works | `/test-whatsapp` sends a message to +27655615874 successfully |
| 4 | WhatsApp inbound works | Send a text to the bot → bot replies (requires tunnel or deployed URL) |
| 5 | Receipt flow works end-to-end | Send receipt image → step 2 location request arrives → tap → confirmation arrives |
| 6 | Commit & push to GitHub | `git status` clean, `git log` shows latest changes |
| 7 | Render backend deployed | `GET https://klpit-api.onrender.com/api/health` returns healthy |
| 8 | Render frontend deployed | Web app loads at Render URL, can reach backend |
| 9 | Meta webhook updated | Send test message to production number → webhook logs show it arriving |
| 10 | Full production test | Real receipt photo → real confirmation → receipt visible in admin |

### Session Startup Checklist
Before starting work in any session:
1. Check `## Current Status` section above — know what's ✅ and what's ❌
2. Update status items as work is completed
3. Only work on one step at a time; verify before moving on

### When Something Breaks
- Check backend logs first (`Render dashboard → Logs` or local terminal)
- Check Meta webhook delivery logs (`Meta Developer Console → Webhooks → Recent Deliveries`)
- Check Supabase logs for DB errors (`Supabase dashboard → Logs`)
- Don't patch symptoms — find the root cause
