# Receipt-to-Win: Product Requirements Document

## Document Info
- **Version**: 1.6
- **Last Updated**: March 4, 2026
- **Status**: MVP Complete, Production Deployment Pending

---

## 1. Executive Summary

### Product Vision
Create a retail rewards platform where South African customers can win back their entire purchase amount by uploading receipt photos via WhatsApp.

### Business Model
- **Customer Acquisition**: Free lottery incentive (win back your spend)
- **Revenue Streams**: 
  - B2B retail data analytics
  - Targeted promotions
  - Receipt verification API

### Current Status
- MVP complete and functional
- WhatsApp outbound messaging working
- WhatsApp inbound blocked (requires production deployment)
- OCR processing operational
- Fraud detection system live

---

## 2. Original Problem Statement

> Create a retail module where customers buy items from retail shops (any retail) by cash/credit card, take a picture of the receipt slip, and upload it via WhatsApp. The system captures receipt data to the database, geo-locates the shop they bought from, and geo-locates the point when they upload the receipt. As an incentive, daily customers stand a chance to win back their spend through a random draw.

---

## 3. User Personas

### Persona 1: Retail Customer (Primary)
- **Profile**: South African adult who shops at retail stores
- **Goal**: Win back purchase amount with minimal effort
- **Behavior**: Takes receipt photo immediately after shopping, sends via WhatsApp
- **Pain Points**: Doesn't want complicated registration, wants instant feedback

### Persona 2: Platform Admin
- **Profile**: Operations manager at KlpIt Tech
- **Goal**: Manage draws, monitor fraud, view analytics
- **Behavior**: Daily check of flagged receipts, run draws, review stats
- **Pain Points**: Needs clear fraud indicators, easy approve/reject workflow

### Persona 3: Business Analyst (Future)
- **Profile**: Market researcher at FMCG company
- **Goal**: Understand consumer purchasing patterns
- **Behavior**: Queries aggregated data for insights
- **Pain Points**: Needs clean, structured data with good coverage

---

## 4. Core Requirements

### 4.1 Receipt Submission (P0)
| Requirement | Status | Notes |
|-------------|--------|-------|
| WhatsApp image submission | Blocked | Requires production webhook |
| Web upload interface | Complete | Manual upload page available |
| Support JPEG images | Complete | Standard format |
| Support PNG images | Complete | Screenshots |
| Support HEIC images | Complete | iPhone photos |
| Support WebP images | Complete | Android photos |

### 4.2 OCR Processing (P0)
| Requirement | Status | Notes |
|-------------|--------|-------|
| Extract shop name | Complete | LandingAI ADE |
| Extract total amount | Complete | Multiple patterns supported |
| Extract line items | Complete | Name, quantity, unit price, total |
| Extract address | Complete | For geocoding |
| Extract postal code | Complete | Improved geocoding accuracy |
| Extract date | Complete | Receipt date detection |
| Handle multi-column formats | Complete | 2, 3, 4 column tables |

### 4.3 Geolocation (P0)
| Requirement | Status | Notes |
|-------------|--------|-------|
| Geocode shop from receipt | Complete | Google Maps API |
| Capture customer location | Complete | Browser geolocation |
| Calculate distance | Complete | Haversine formula |
| SA postal code lookup | Complete | Local fallback database |

### 4.4 Fraud Detection (P0)
| Requirement | Status | Notes |
|-------------|--------|-------|
| Distance-based scoring | Complete | 0-100 score |
| Flag categories | Complete | valid/review/suspicious/flagged |
| Admin review queue | Complete | Approve/reject workflow |
| Auto-exclude flagged | Complete | Blocked from draw |

### 4.5 Prize Draw (P0)
| Requirement | Status | Notes |
|-------------|--------|-------|
| Daily random selection | Complete | Midnight UTC |
| Winner notification | Complete | WhatsApp message |
| Draw history | Complete | Full audit trail |
| Multiple entries per customer | Complete | One per receipt |

### 4.6 Customer Features (P1)
| Requirement | Status | Notes |
|-------------|--------|-------|
| View receipt history | Complete | Dashboard with filters |
| View receipt details | Complete | Image, items, location |
| View winning history | Complete | Wins tab |
| WhatsApp bot commands | Complete | HELP, RECEIPTS, WINS, etc. |

### 4.7 Admin Features (P1)
| Requirement | Status | Notes |
|-------------|--------|-------|
| Analytics dashboard | Complete | Stats, charts |
| Map visualization | Complete | Leaflet with SA focus |
| Fraud review page | Complete | With image display |
| Geocoding management | Complete | Batch operations |

---

## 5. Non-Functional Requirements

### 5.1 Performance
- Receipt processing: < 10 seconds
- API response time: < 500ms (p95)
- Support 1000+ daily receipts

### 5.2 Reliability
- 99.5% uptime target
- Graceful degradation if OCR fails
- Retry logic for external APIs

### 5.3 Security
- No PII in logs
- Secure API key storage
- HTTPS required

### 5.4 Scalability
- MongoDB sharding ready
- Stateless backend design
- Async processing throughout

---

## 6. Technical Architecture

### 6.1 Stack
- **Frontend**: React 19, Tailwind CSS, Shadcn UI
- **Backend**: FastAPI (Python 3.11+), async
- **Database**: MongoDB (Motor async driver)
- **OCR**: LandingAI ADE
- **Geocoding**: Google Maps API
- **Messaging**: Meta WhatsApp Cloud API
- **Search**: Qdrant vector store

### 6.2 Data Flow
```
Customer → WhatsApp/Web → Backend API → OCR → Geocoding → DB → Draw Scheduler
                                                                    ↓
                                                              Winner Notification
```

### 6.3 Key Files
| File | Purpose | Lines |
|------|---------|-------|
| `server.py` | Main API, business logic | ~1900 |
| `receipt_processor.py` | OCR integration | ~850 |
| `geocoding.py` | Google Maps service | ~340 |
| `whatsapp_cloud.py` | WhatsApp client | ~310 |

---

## 7. Integration Details

### 7.1 WhatsApp Cloud API
- **Business**: KlpIt Tech / ReceiptsProd2026
- **Phone**: +27 65 561 5874
- **Phone ID**: 955997190937092
- **WABA ID**: 2129214027857484
- **Template**: receipts_welcome (approved)
- **Webhook**: Requires production URL

### 7.2 LandingAI ADE
- **Model**: dpt-2-latest
- **Methods**: parse(), extract()
- **Features**: Grounding boxes, schema extraction

### 7.3 Google Maps
- **Service**: Geocoding API
- **Region**: ZA (South Africa)
- **Fallback**: Local suburb database

---

## 8. What's Been Implemented

### Complete Features
1. Full-stack web application (React + FastAPI + MongoDB)
2. WhatsApp Cloud API integration (outbound working)
3. LandingAI OCR with image format conversion
4. Google Maps geocoding with postal code priority
5. Fraud detection with distance-based scoring
6. Admin dashboard with analytics
7. Customer dashboard with receipt details
8. Daily draw system with scheduler
9. Interactive map view
10. Web-based receipt upload

### Partial Features
1. WhatsApp inbound messages (webhook blocked by preview environment)
2. Vector search (OpenAI key issue, non-blocking)

---

## 9. Known Issues

### P0 - Critical
| Issue | Impact | Resolution |
|-------|--------|------------|
| WhatsApp inbound blocked | Core feature unavailable | Deploy to production |

### P1 - Important
| Issue | Impact | Resolution |
|-------|--------|------------|
| OCR column merging | Data quality | Improve parsing logic |
| OpenAI 401 error | Search unavailable | Update API key |

---

## 10. Next Steps

### Immediate (Week 1)
1. Deploy to production environment (Render/Railway)
2. Configure production webhook URL in Meta Dashboard
3. Test end-to-end WhatsApp flow
4. Update documentation

### Short-term (Month 1)
1. Onboard first batch of test users
2. Collect feedback on OCR accuracy
3. Improve fraud detection thresholds
4. Add receipt deduplication

### Medium-term (Quarter 1)
1. Analytics improvements
2. Gamification features
3. B2B data API
4. Compliance (POPIA)

---

## 11. Success Metrics

### MVP Launch
- [ ] WhatsApp inbound working
- [ ] 100 registered customers
- [ ] 500 receipts processed
- [ ] First draw winner notified

### Growth (6 months)
- [ ] 10,000 customers
- [ ] 50,000 receipts
- [ ] 50+ unique shops
- [ ] <2% fraud rate

---

## 12. Appendix

### A. Supported Retailers
Major SA chains supported via OCR:
- Checkers, Shoprite, Pick n Pay, Woolworths
- Spar, Dis-Chem, Clicks
- Game, Makro, Builders
- Engen, Shell, BP, Sasol
- Various restaurants and specialty stores

### B. SA Postal Code Regions
- 0001-0999: Northern provinces
- 1000-2999: Gauteng
- 3000-4999: KwaZulu-Natal
- 5000-5999: Free State
- 6000-6999: Eastern Cape
- 7000-7999: Western Cape
- 8000-8999: Northern Cape
- 9000-9999: Limpopo/Mpumalanga

### C. Fraud Scoring
| Distance (km) | Score | Flag | Action |
|---------------|-------|------|--------|
| 0-50 | 0-50 | valid | Auto-approve |
| 50-100 | 50-75 | review | Manual check |
| 100-200 | 75-100 | suspicious | Verify |
| 200+ | 100 | flagged | Block |

---

*Document maintained by KlpIt Tech development team*
