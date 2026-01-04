# Retail Rewards Platform - PRD

## Original Problem Statement
Create a retail module where customers buy items from retail shops (any retail) by cash/credit card, take a picture of the receipt slip, and upload it via WhatsApp. The system captures receipt data to the database, geo-locates the shop they bought from, and geo-locates the point when they upload the receipt. As an incentive, daily customers stand a chance to win back their spend through a random draw. The data is then used to aggregate customer behavior and do analytics.

## User Personas
1. **Retail Customer**: Shops at various retail stores, wants to participate in the daily draw to win back their spend
2. **Platform Admin**: Manages draws, views analytics, monitors customer behavior and spending patterns
3. **Business Analyst**: Uses aggregated data for market research and consumer behavior insights

## Core Requirements
- Receipt upload via WhatsApp (Baileys integration)
- Receipt OCR/parsing (LandingAI ADE ready)
- Geolocation capture (customer upload location + shop detection)
- Daily random prize draw system
- Customer dashboard with receipt history
- Interactive map visualization
- Analytics dashboard with spending patterns, popular shops, time trends

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + Leaflet Maps + Recharts
- **Backend**: FastAPI (Python) with async endpoints
- **Database**: MongoDB with collections for customers, receipts, shops, draws
- **WhatsApp**: Baileys library (Node.js microservice - pending setup)

## What's Been Implemented (January 4, 2026)
### Backend APIs
- ✅ Customer CRUD endpoints
- ✅ Receipt upload with geolocation
- ✅ Shop auto-detection and creation
- ✅ Daily random draw system
- ✅ Analytics endpoints (overview, spending by day, popular shops, top spenders, receipts by hour)
- ✅ Map data endpoints
- ✅ WhatsApp webhook handlers (ready for Baileys integration)
- ✅ Demo data seeding endpoint

### Frontend Pages
- ✅ Landing page with hero section and platform stats
- ✅ Customer dashboard with receipts and wins tabs
- ✅ Receipt upload dialog with shop name, amount, and text
- ✅ Interactive map view with shop markers and receipt locations
- ✅ Daily draws page with winner announcement and history
- ✅ Analytics dashboard with 4 tabs (Spending, Shops, Customers, Time)
- ✅ WhatsApp setup page with integration instructions

### Design
- ✅ "Neon Void" dark theme with glassmorphism
- ✅ Purple/Green/Pink accent colors
- ✅ Space Grotesk + Manrope + JetBrains Mono fonts
- ✅ Framer Motion animations
- ✅ Responsive bottom navigation

## Prioritized Backlog

### P0 - Critical (Next Phase)
- [ ] Node.js Baileys WhatsApp microservice setup
- [ ] Real WhatsApp QR code authentication
- [ ] LandingAI ADE OCR integration for receipt parsing

### P1 - High Priority
- [ ] Customer authentication (phone number verification)
- [ ] Receipt image upload to cloud storage
- [ ] Automated daily draw scheduler (cron job)
- [ ] Winner notification via WhatsApp

### P2 - Medium Priority
- [ ] Receipt image OCR with LandingAI ADE
- [ ] Shop verification and deduplication
- [ ] Export analytics to CSV/Excel
- [ ] Customer segments and targeting

### P3 - Nice to Have
- [ ] Push notifications for winners
- [ ] Social sharing of wins
- [ ] Referral system
- [ ] Multi-currency support
- [ ] Admin user management

## Next Tasks
1. Set up Node.js Baileys microservice with Redis session storage
2. Implement real-time WhatsApp QR code authentication
3. Add receipt image processing with LandingAI ADE
4. Configure automated daily draw at midnight UTC
