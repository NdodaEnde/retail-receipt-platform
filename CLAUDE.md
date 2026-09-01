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
- **Only the distance signal is implemented in code today** (`assess_fraud_risk`); velocity and duplicate checks are roadmap
- **Geocode precision gate** (Sept 2026): Google returns the *country* (SA centroid `-30.559482, 22.937506`) with `status: OK` when it can't match a shop. `geocoding.py` rejects region-level matches, records `geocode_precision` (`rooftop|biased|street|suburb|city|none`) on receipts (migration 003) and `shops.geocode_confidence`, and falls back to a Places search *biased* to the customer's location (`biased`: a *small* distance is not scored as evidence, a large one still is). Results must name a place the receipt address names (`address_consistent`) — guards against precise-but-wrong matches
- **A receipt is never held from the draw because we couldn't find the shop** — unresolved shop ⇒ `fraud_flag=valid` with reason; only a missing customer location ⇒ `review`
- Backfill / repair: `python scripts/backfill_geocode.py [--apply | --fill-precision]`

## Receipt Field Extraction & Shop Resolution (Sept 2026)

**The LLM proposes, the receipt's structure verifies, Google resolves, agreement decides.**

| Stage | Module | Rule |
|-------|--------|------|
| Propose | `receipt_processor.py` (LandingAI `extract()` schema) | asks for `address_lines`, `phone_number`, `postal_code` + `postal_code_source_line`; descriptions say *return null if not printed* |
| Verify | `extraction_verifier.py` → `verify_extraction()` | a postcode is accepted only if printed on an **address-block line** (header, or restaurant footer like `7848 Cape Town`), not a transaction row (`Store Cash. Till Date Time`), < 8 digits on the line, next to a place word. Phone must be printed, SA-shaped, not 0800/0860/0861. Shop names like `Purchase`, `18:01`, `Ver 2.1` are rejected. Every decision is logged as `verify: …` |
| Resolve | `shop_resolver.py` → `resolve_shop()` | witness ladder: **phone** → name+address → name+suburb → address geocode → name+postcode → name near customer (`biased`) → postcode alone (`city`). Results must agree with the slip's text (`address_consistent`); a metro city is not a suburb |
| Decide | precision `verified` (two witnesses agree) / `rooftop` / `biased` / … | `biased` = found only by searching around the customer: a *small* distance is not fraud evidence, a large one still is |

- No whole-text 4-digit postcode scan anywhere — it had ~4% precision on real receipts. Absence is the normal answer.
- **Golden set**: `backend/tests/golden_receipts.json` (30 real, scrubbed slips) + `python tests/test_extraction_golden.py [--live-schema] [--live-resolve]`. Add a receipt there whenever a new POS format misbehaves.
- **Shops are keyed by Google Place ID** (migration 004): same `place_id` ⇒ same shop whatever the slip called it; a resolved branch claims a legacy name-matched shop only at the same place (≤2 km); without a place_id a name match 1 400 km away is a *different* branch. Canonical `shops.name` = Google's business name (+suburb); OCR names land in `shop_aliases`. Place IDs come only from Places (establishment) results — never from address/postcode geocodes. Brand-token matching stops a mall outscoring the store inside it.
- Identity backfill: `python scripts/backfill_shop_identity.py [--apply]` (requires migration 004; resolves every receipt via the full pipeline, merges duplicate shops, repoints receipts, recomputes shop stats).
- Unit tests: `python tests/test_shop_identity.py` (identity rules, mocked DB).

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
- ✅ Draw scheduler set to 21:00 SAST (explicit UTC timezone on CronTrigger)
- ✅ Render deployment live (backend: klpit-api.onrender.com, frontend: klpit-web.onrender.com)
- ✅ Meta WhatsApp webhook pointing to Render backend
- ✅ Full end-to-end receipt flow verified in production (March 2026)
- ✅ Admin auth (Supabase Auth, email/password)
- ✅ Customer registration flow (first_name + surname via WhatsApp)
- ✅ QR code invite system (`/admin/invite` page)
- ✅ Winner confetti notifications with entry count
- ✅ Sprint 1: Write-through cache for in-memory state (`pending_state` table)
- ✅ Sprint 1: Basket analysis dashboard (4 views, 4 endpoints, BasketAnalytics page)
- 🔲 Sprint 2: Loyalty tiers + streaks
- 🔲 Sprint 3: Public winners page + winner broadcast + OCR date extraction
- 🔲 Sprint 4: Rate limiting + duplicate image hashing + referral analytics
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

### Golden Rule
**NEVER push code that hasn't been locally verified. Task → Verify → Proceed. No exceptions.**

### Feature Development Cycle

| Phase | Action | Must Pass |
|-------|--------|-----------|
| 1. Plan | Identify files to change, SQL views needed | — |
| 2. Backend | Add DB methods, endpoints, test with curl | `curl localhost:8000/api/...` returns correct data |
| 3. Frontend | Build UI, connect to API | Page renders, data displays, no console errors |
| 4. Verify | Run `/verify-feature` checklist | All checks green |
| 5. Commit | `git add` specific files, commit | `git status` clean |
| 6. Push | `git push` to trigger Render deploy | Render build succeeds |
| 7. Production | Test on live URL | Feature works on klpit-web.onrender.com |

**If any phase fails → fix before proceeding. Never skip verification.**

### Phone Number Normalization

| Source | Format | Example |
|--------|--------|---------|
| `customers` table | With `+` prefix | `+27769695462` |
| `receipts` table | Without `+` prefix | `27769695462` |
| Frontend input | User enters `076...` | Converted to `27769695462` |
| WhatsApp API | Without `+` prefix | `27769695462` |

**Every endpoint accepting a phone parameter MUST handle both formats.** Standard pattern:
```python
phone = phone_number.lstrip("+")  # Strip + for receipts table queries
```

### SQL View Development
Use `/add-sql-view` command for the full workflow: SQL → migration → database.py → server.py → frontend.

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

### Available Commands

| Command | Purpose |
|---------|---------|
| `/sprint-status` | Show sprint progress and what's next |
| `/verify-feature` | Mandatory pre-push verification checklist |
| `/add-sql-view` | Full-stack SQL view creation workflow |
| `/check-supabase` | Verify Supabase tables and row counts |
| `/test-whatsapp` | Test WhatsApp message delivery |
| `/deploy-render` | Render deployment walkthrough |
| `/seed` | Seed DB with demo data for testing |

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

---

## Customer Registration & Invites

- Customers must register (first name + surname) before submitting receipts
- Registration state machine: `unregistered` → `pending_first_name` → `pending_surname` → `registered`
- State persisted in `pending_state` table (write-through cache)
- Invite via QR code: `wa.me/{phone}?text=Hi` — customer-initiated, no Meta template needed
- Admin page: `/admin/invite` — QR display, copy link, phone invite, customer list

## State Persistence (Write-Through Cache)

In-memory dicts (`pending_receipts`, `customer_locations`, `pending_registrations`) are backed by the `pending_state` Supabase table. On every write, both memory and DB are updated. On cache miss (e.g., after restart), the DB is checked. Expired rows cleaned every 30 minutes via APScheduler.

TTLs: pending_receipt=15min, customer_location=60min, pending_registration=30min

## Analytics Architecture

- **Cross-table analytics use SQL views** — `database.py` can't do JOINs
- Views created in Supabase SQL Editor, queried as `self.client.table('view_name').select('*')`
- Current views: `daily_spending`, `shop_performance`, `customer_summary`, `fraud_analysis`, `hourly_distribution`, `top_items`, `item_pairs`, `basket_stats`, `customer_behavior`
- Basket analytics: `/analytics/top-items`, `/analytics/item-pairs`, `/analytics/basket-stats`, `/analytics/customer-behavior`

## Data Intelligence Strategy

Full roadmap: `docs/DATA_INTELLIGENCE_ROADMAP.md`

**Key principles:**
1. **Users first, analytics second** — grow the user base before building intelligence products
2. **SQL views over application code** — keep analytics in the database
3. **Aggregate, anonymize, comply** — POPIA compliance before any B2B data play
4. **SA context is the competitive moat** — township economies, SASSA grant cycles, informal retail
5. **Simple rules before ML** — rule-based segmentation covers 80% of value
6. **Item normalization is the bottleneck** — most product-level intelligence is blocked until OCR item names are standardized

**Intelligence tiers by user volume:**
| Users | Unlocked Intelligence |
|-------|----------------------|
| 50+ | Behavioral archetypes, day-of-week patterns, spend density heatmap |
| 200+ | Item categorization, churn prediction, streak analytics |
| 500+ | SASSA grant cycle impact, suburb-level economic indicators |
| 1000+ | B2B data API, income proxy modeling, market share estimation |

## Ontology Layer (Intelligence + POPIA Governance)

A declarative ontology models the platform as Objects / Links / Actions / Functions
with O/P/F/X sensitivity classes on every property. Lives in `ontology/*.yaml`.

- **Run**: `./scripts/verify-ontology.sh` — parses, validates consistency, prints
  the sensitivity/exposure report, and **fails the build** if a function marked
  `exposure: external` would emit Personal (`P`) or Financial (`F`) data.
- **POPIA gate**: only `output_class: X` may be externally exposed — the enforced
  form of "aggregate, anonymize, comply before any B2B data play".
- **Functions = the intelligence roadmap**: each insight is declared with
  `min_users` + `phase` (mirrors the intelligence-tier table above). Most already
  exist as SQL views; the ontology adds sensitivity + release phase.
- **When adding a column/view**: add the property to `objects.yaml` with a
  sensitivity class (validator fails on untagged) and declare new insights in
  `functions.yaml`, then re-run the verifier.
- `product` object is **planned** — the home for the item-normalization bottleneck.

## Sprint Roadmap

| Sprint | Theme | Status |
|--------|-------|--------|
| 1 | Reliability (write-through cache) + Basket Analysis | ✅ Complete |
| 2 | Loyalty Tiers (computed) + Streaks (3 cols on customers) + WhatsApp `tier`/`streak` commands | 🔲 Next |
| 3 | Public Winners Page + Winner Broadcast to all participants + OCR Date Extraction | 🔲 Planned |
| 4 | Rate Limiting (slowapi) + Duplicate Image Hashing + Referral Analytics + UptimeRobot | 🔲 Planned |

**Post-Sprint:** Phase 1 today-only draw (needs OCR date), points system (needs user data), B2B data API (needs volume)
