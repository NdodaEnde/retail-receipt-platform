# Receipt-to-Win: Development Roadmap

## Current Status: MVP Complete (Phase 6)
Last Updated: March 4, 2026

---

## Completed Phases

### Phase 1: Foundation
- [x] FastAPI backend architecture
- [x] MongoDB integration with Motor async driver
- [x] React 19 frontend with Tailwind CSS
- [x] Shadcn UI component library
- [x] Customer, Receipt, Shop, Draw data models
- [x] Basic CRUD APIs
- [x] Manual receipt upload form

### Phase 2: WhatsApp Integration
- [x] Meta WhatsApp Cloud API integration
- [x] Webhook endpoint for receiving messages
- [x] Send text messages
- [x] Download media (receipt images)
- [x] Bot commands: HELP, RECEIPTS, WINS, STATUS, BALANCE
- [x] Winner notification messages
- [x] Receipt confirmation messages
- [x] Message read receipts

### Phase 3: OCR & Receipt Processing
- [x] LandingAI ADE integration (dpt-2-latest model)
- [x] Image format support: JPEG, PNG, HEIC (iPhone), WebP (Android)
- [x] Auto-conversion to optimized JPEG
- [x] Schema-based structured extraction
- [x] Multi-column table parsing (2, 3, 4 columns)
- [x] Shop name extraction
- [x] Address extraction
- [x] Postal code detection
- [x] Item extraction with granular data:
  - Item name
  - Quantity
  - Unit price
  - Total price

### Phase 4: Geocoding & Fraud Detection
- [x] Google Maps Geocoding API integration
- [x] Postal code prioritization for accuracy
- [x] Local SA fallback database
- [x] Haversine distance calculation
- [x] Fraud scoring system (0-100)
- [x] Fraud flag categories: valid, review, suspicious, flagged
- [x] Admin review workflow (approve/reject)
- [x] Automatic fraud assessment on upload

### Phase 5: UI/UX Enhancements
- [x] Customer Dashboard with receipt history
- [x] Receipt detail modal (image + items + location)
- [x] Interactive map view (Leaflet, SA-centered)
- [x] Analytics dashboard with charts
- [x] Fraud detection admin page
- [x] Manual upload page for demos
- [x] Auto location request on upload
- [x] WhatsApp confirmation for web uploads

### Phase 6: Production Setup (Current)
- [x] Register production WhatsApp number (+27 65 561 5874)
- [x] Create managed message template (receipts_welcome)
- [x] Update credentials (new Meta Business profile: KlpIt Tech)
- [x] Verify outbound messaging working
- [ ] **BLOCKED**: Inbound messaging (requires production webhook URL)

---

## In Progress

### P0 - Critical Path
| Task | Status | Blocker |
|------|--------|---------|
| Deploy to production environment | Not Started | Need to choose platform (Render, Railway, etc.) |
| Configure production webhook URL | Blocked | Waiting for deployment |
| End-to-end WhatsApp testing | Blocked | Waiting for webhook |

---

## Upcoming Tasks

### Short-term (Next Sprint)

#### Production Deployment
- [ ] Choose deployment platform (Render recommended)
- [ ] Set up production MongoDB (Atlas)
- [ ] Configure environment variables
- [ ] Deploy backend
- [ ] Deploy frontend
- [ ] Configure HTTPS/SSL
- [ ] Update Meta webhook URL
- [ ] Verify inbound message flow

#### OCR Improvements
- [ ] Handle more receipt formats
- [ ] Improve column parsing for merged data
- [ ] Add retry logic for failed extractions
- [ ] Cache similar receipts for faster processing

---

## Future Features (Backlog)

### Analytics & Insights (P1)
- [ ] Basket analysis dashboard
  - Most common item combinations
  - Average basket size by shop
  - Price sensitivity analysis
- [ ] Customer behavior insights
  - Shopping frequency patterns
  - Preferred shopping days/times
  - Shop loyalty metrics
- [ ] Shop performance metrics
  - Receipt volume trends
  - Average transaction value
  - Geographic coverage

### Monetization Features (P1)
- [ ] B2B data API
  - Anonymized transaction data
  - Market research exports
  - Competitive intelligence
- [ ] Targeted promotions
  - Push promotions via WhatsApp
  - Personalized offers based on history
  - Shop partnership integrations
- [ ] Receipt verification service
  - API for third parties to verify receipts
  - Fraud detection as a service

### Gamification (P2)
- [ ] Loyalty tiers (Bronze, Silver, Gold, Platinum)
  - Based on receipt volume or spend
  - Tier-specific benefits (bonus entries)
- [ ] Streaks and achievements
  - Daily upload streaks
  - Shop variety badges
  - Big spender achievements
- [ ] Referral program
  - Invite friends via WhatsApp
  - Bonus entries for referrals

### Compliance & Legal (P2)
- [ ] Terms & Conditions page
- [ ] Privacy Policy page (POPIA compliant)
- [ ] Data retention policies
- [ ] User data export (GDPR-style)
- [ ] Opt-out mechanism

### Customer Features (P2)
- [ ] WhatsApp command: HISTORY (download receipts)
- [ ] Receipt search via WhatsApp
- [ ] Spending reports via WhatsApp
- [ ] Location preferences (home area)

### Technical Improvements (P3)
- [ ] Receipt deduplication
- [ ] Image storage optimization (S3/GCS)
- [ ] Rate limiting and throttling
- [ ] API authentication (JWT)
- [ ] Admin user management
- [ ] Audit logging
- [ ] Automated backups

---

## Technical Debt

### Code Quality
- [ ] Refactor `receipt_processor.py` (850 lines → smaller modules)
- [ ] Add unit tests for core functions
- [ ] Add integration tests
- [ ] Set up CI/CD pipeline
- [ ] Improve error handling and logging

### Performance
- [ ] Optimize MongoDB queries (indexing)
- [ ] Add caching layer (Redis)
- [ ] Image compression optimization
- [ ] Lazy loading on frontend

### Documentation
- [ ] API documentation (Swagger/OpenAPI)
- [ ] Developer onboarding guide
- [ ] Architecture decision records

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OCR fails on new receipt format | High | Medium | Continuous improvement, fallback to manual entry |
| WhatsApp API rate limits | Medium | High | Implement queuing, batch notifications |
| Google Maps API quota exceeded | Low | Medium | Local fallback database, caching |
| MongoDB scaling issues | Low | High | Plan for sharding, Atlas auto-scaling |
| User fraud attempts | Medium | Medium | Improve detection, manual review queue |

---

## Success Metrics

### Launch Targets
- [ ] 100 registered customers
- [ ] 500 receipts processed
- [ ] 10 daily draw completions
- [ ] <5% fraud flag rate

### Growth Targets (6 months)
- [ ] 10,000 registered customers
- [ ] 50,000 receipts processed
- [ ] 50+ unique shops
- [ ] 100+ daily draw entries
- [ ] <2% fraud flag rate

---

## Notes

### Design Decisions
1. **WhatsApp as primary channel**: Highest mobile penetration in SA
2. **Daily draws (not instant wins)**: Creates anticipation, reduces fraud
3. **Location verification**: Essential for fraud detection at scale
4. **LandingAI over Tesseract**: Better accuracy on receipt formats, grounding data

### Lessons Learned
1. HEIC image format is common from iPhone users - must support
2. Postal codes are more reliable than shop names for geocoding
3. Column merging in OCR is a common failure mode - need robust parsing
4. Preview environments can't receive webhooks from Meta - need production deploy

---

*Last reviewed: March 4, 2026*
