# KlpIT Data Intelligence Roadmap

## Overview
KlpIT sits on a unique data asset: real-time, geolocated retail transaction data across formal and informal channels in South Africa. This document outlines the intelligence layers we can build as the user base grows.

## Data Foundation (what we have today)

| Table | Key Fields | Intelligence Value |
|-------|-----------|-------------------|
| `customers` | phone, first_name, surname, total_receipts, total_spent, registration_status | Customer lifetime value, engagement scoring |
| `receipts` | shop_name, amount, created_at, latitude/longitude, fraud_score, status | Transaction patterns, geographic activity |
| `receipt_items` | name, quantity, unit_price, total_price | Basket composition, product popularity |
| `shops` | name, address, latitude/longitude, receipt_count, total_sales | Retail landscape mapping |
| `draws` | draw_date, winner, prize_amount, total_receipts | Engagement incentive tracking |

**Existing SQL views**: daily_spending, shop_performance, customer_summary, fraud_analysis, hourly_distribution, top_items, item_pairs, basket_stats, customer_behavior

---

## Phase 1: Foundation Analytics (Sprint 1 — DONE)

Already built and deployed:
- Top items by frequency + price stats
- Item co-occurrence (bought together)
- Basket size distribution
- Customer shopping behavior (frequency vs spend scatter)

## Phase 2: Behavioral Segmentation (Sprint 2-3)

### Customer Archetypes

Derive from existing data — no new tables needed.

| Archetype | Data Signals | Business Use |
|-----------|-------------|-------------|
| **Budget Maximizer** | High receipt frequency, low avg basket, many shops | Target with cashback bonuses, referral incentives |
| **Cross-Shopper** | 5+ unique shops, diverse categories | Valuable for FMCG testing, coalition offers |
| **Loyal Local** | 1-2 shops, high frequency, stable basket size | Ideal for shop-specific promotions |
| **Weekend Warrior** | 80%+ receipts on Fri-Sun | Event-driven marketing, pay-cycle alignment |

**Implementation**: SQL view computing archetype label from `total_receipts`, `total_spent`, `unique_shops`, day-of-week distribution. No ML needed — rule-based thresholds.

### Loyalty Tiers + Streaks (Sprint 2)
- Bronze (0-4 receipts) → Silver (5-14) → Gold (15-29) → Platinum (30+)
- Daily upload streaks with WhatsApp commands
- Tier progress visible in dashboard

### Shopping Pattern Analytics
- Day-of-week spending distribution
- Time-of-day upload patterns by region
- Shop loyalty metrics (repeat visit rate)

## Phase 3: Geographic Intelligence (Sprint 3-4)

### Spend Density Mapping
- Heatmap: receipt value weighted by shop location
- Suburb-level average basket size trending (30/60/90 days)
- Upload density as proxy for foot traffic

### Mobility Patterns
- Cross-shop distance analysis (how far do customers travel?)
- Commuter corridors: fuel + convenience receipts near transport hubs
- Weekend vs weekday geographic spread

### SA-Specific Economic Signals

#### SASSA Grant Cycle Pulse
- SASSA payments land around the 3rd of each month
- Track: basket size growth, category shifts, geographic spread in days 3-7
- Value: real-time welfare impact indicator for government, banks, retailers

#### Load-Shedding Impact (requires Eskom data integration)
- Correlate Eskom stage alerts with receipt timestamps + upload locations
- Detect: drop in evening uploads, shift to generator/fuel purchases
- Requires: External API (EskomSePush) — defer until volume justifies

## Phase 4: Product & Category Intelligence (requires item normalization)

### The Item Normalization Problem
OCR produces inconsistent item names:
- "SPAR 2L MILK" vs "FRESH MILK 2L" vs "CLOVER 2LTR FULL CRM"
- Without normalization, category analysis is noisy

**Approach** (when ready):
1. Build keyword-based category mapper first (50 rules cover 80% of items)
2. Add fuzzy matching for top 200 items (Levenshtein/token similarity)
3. Optional: Use embeddings (OpenAI) for semantic item matching at scale

### Once Normalized
- Category allocation: % of spend on groceries/fuel/airtime/clothing
- Trade-up/trade-down signals: shifts from premium to value brands by area
- Life event detection: spikes in baby products, school supplies, funeral items
- Cross-category basket affinity by location type

## Phase 5: Data Monetization (requires volume + POPIA compliance)

### Prerequisites
- **Minimum 1,000 active monthly users** for statistical significance
- **POPIA compliance**: Privacy policy, explicit consent for anonymized data use
- **Data anonymization pipeline**: Strip PII, aggregate to suburb/region level

### Potential Partners

| Partner Type | Value Proposition | Data Product |
|-------------|-------------------|--------------|
| **FMCG Brands** (Coca-Cola, Unilever) | See where products are actually bought — formal + informal channels | Heatmap of brand presence by township |
| **Banks & Fintechs** | Identify underserved high-spend corridors for agent banking | Anonymous spend density maps + income proxy |
| **Government / Stats SA** | Real-time economic activity data to supplement census | Aggregated township spend indices |
| **Property Developers** | Validate foot traffic and spend power before investing | Retail spend velocity by coordinate |
| **Research Institutions** | Study informal economy, price elasticity, grant impact | De-identified, aggregated academic datasets |

### Revenue Model Options
1. **Dashboard subscriptions**: Retailers pay for hyperlocal market intelligence
2. **API access**: Anonymized, aggregated transaction data feeds
3. **Custom reports**: One-off geographic or category analysis
4. **Campaign attribution**: Track promotional lift for partner campaigns

---

## Implementation Priority Matrix

| Feature | Data Exists? | Users Needed | Effort | Priority |
|---------|-------------|-------------|--------|----------|
| Behavioral archetypes | Yes | 50+ | 1 view + 1 endpoint | P1 |
| Day-of-week patterns | Yes | 20+ | 1 view | P1 |
| Spend density heatmap | Yes | 50+ | Frontend only (Leaflet) | P1 |
| SASSA cycle tracking | Yes | 100+ | Date filtering logic | P2 |
| Loyalty tiers | Yes | Any | Computed, no schema | P1 (Sprint 2) |
| Item categorization | Partial | 200+ | Category mapper + view | P2 |
| Churn prediction | Needs streaks | 200+ | Streak data + thresholds | P3 |
| B2B data API | Needs volume | 1000+ | Full product | P4 |
| Income proxy modeling | Needs volume | 500+/suburb | Statistical modeling | P5 |

---

## Key Principles

1. **Users first, analytics second** — don't build dashboards nobody will use
2. **SQL views over application code** — keep analytics logic in the database
3. **Aggregate, anonymize, comply** — never sell individual-level data; POPIA compliance is non-negotiable
4. **SA context is the moat** — township economies, grant cycles, informal retail are uniquely addressable
5. **Simple rules before ML** — rule-based segmentation covers 80% of value; ML is Phase 5+
6. **Item normalization is the bottleneck** — most category intelligence is blocked until this is solved

---

## SQL Query Templates (for future views)

### Behavioral Archetype Assignment
```sql
CREATE VIEW customer_archetypes AS
SELECT c.phone_number, c.first_name, c.surname,
  c.total_receipts, c.total_spent,
  CASE WHEN c.total_receipts > 0 THEN c.total_spent / c.total_receipts ELSE 0 END AS avg_basket,
  cb.unique_shops, cb.active_days,
  CASE
    WHEN c.total_receipts >= 20 AND cb.unique_shops >= 5 THEN 'Cross-Shopper'
    WHEN c.total_receipts >= 15 AND cb.unique_shops <= 2 THEN 'Loyal Local'
    WHEN c.total_receipts >= 10 AND (c.total_spent / NULLIF(c.total_receipts, 0)) < 100 THEN 'Budget Maximizer'
    WHEN c.total_receipts >= 5 THEN 'Regular'
    ELSE 'New'
  END AS archetype
FROM customers c
LEFT JOIN customer_behavior cb ON c.phone_number = cb.phone_number;
```

### SASSA Grant Cycle Spend
```sql
-- Compare spend in days 3-7 (post-grant) vs days 15-20 (mid-month)
SELECT
  EXTRACT(MONTH FROM created_at) AS month,
  AVG(CASE WHEN EXTRACT(DAY FROM created_at) BETWEEN 3 AND 7 THEN amount END) AS avg_post_grant,
  AVG(CASE WHEN EXTRACT(DAY FROM created_at) BETWEEN 15 AND 20 THEN amount END) AS avg_mid_month,
  COUNT(CASE WHEN EXTRACT(DAY FROM created_at) BETWEEN 3 AND 7 THEN 1 END) AS post_grant_count,
  COUNT(CASE WHEN EXTRACT(DAY FROM created_at) BETWEEN 15 AND 20 THEN 1 END) AS mid_month_count
FROM receipts WHERE status != 'rejected'
GROUP BY 1 ORDER BY 1;
```

### Day-of-Week Shopping Patterns
```sql
CREATE VIEW day_of_week_patterns AS
SELECT
  EXTRACT(DOW FROM created_at) AS day_num,
  TO_CHAR(created_at, 'Day') AS day_name,
  COUNT(*) AS receipt_count,
  AVG(amount) AS avg_amount,
  SUM(amount) AS total_amount,
  COUNT(DISTINCT customer_id) AS unique_customers
FROM receipts WHERE status != 'rejected'
GROUP BY 1, 2 ORDER BY 1;
```

### Purchase-to-Upload Distance
```sql
-- Requires: receipts have upload lat/lon AND shop has geocoded lat/lon
SELECT
  CASE
    WHEN distance_km <= 1 THEN 'Immediate (≤1km)'
    WHEN distance_km <= 5 THEN 'Nearby (1-5km)'
    WHEN distance_km <= 50 THEN 'Local (5-50km)'
    ELSE 'Remote (50km+)'
  END AS upload_pattern,
  COUNT(*) AS receipt_count,
  AVG(amount) AS avg_spend,
  COUNT(DISTINCT customer_id) AS unique_customers
FROM (
  SELECT r.*, s.latitude AS shop_lat, s.longitude AS shop_lon,
    -- Haversine approximation
    111.045 * DEGREES(ACOS(LEAST(1.0,
      COS(RADIANS(r.latitude)) * COS(RADIANS(s.latitude)) *
      COS(RADIANS(s.longitude - r.longitude)) +
      SIN(RADIANS(r.latitude)) * SIN(RADIANS(s.latitude))
    ))) AS distance_km
  FROM receipts r
  JOIN shops s ON r.shop_name = s.name
  WHERE r.latitude IS NOT NULL AND s.latitude IS NOT NULL
) sub
GROUP BY 1;
```
