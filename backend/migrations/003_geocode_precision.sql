-- Migration 003 — shop-location precision on receipts
-- Run in the Supabase SQL editor (idempotent).
--
-- Why: Google's Geocoding API returns the *country* (status OK, geographic centre
-- of SA at -30.559482, 22.937506) when it cannot match a shop. 22 receipts were
-- pinned there and 17 falsely flagged as >200 km fraud. geocoding.py now rejects
-- region-level matches and records how precisely each shop was resolved so
-- analytics can filter on location quality and fraud can weight the evidence.
--
-- Values (best → worst):
--   rooftop  specific establishment / street address
--   biased   establishment found via Places search biased to the customer's
--            location — accurate, but not independent evidence for fraud
--   street   road, no number
--   suburb   suburb / neighbourhood centroid
--   city     town / postal-code centroid
--   none     unresolved (shop_latitude/longitude are NULL)
-- shops.geocode_confidence (already exists) holds the same value for the shop.

ALTER TABLE receipts ADD COLUMN IF NOT EXISTS geocode_precision VARCHAR(20);
COMMENT ON COLUMN receipts.geocode_precision IS
  'How precisely the shop location was resolved: rooftop|biased|street|suburb|city|none';

CREATE INDEX IF NOT EXISTS idx_receipts_geocode_precision ON receipts(geocode_precision);

-- Geographic views should only trust independently resolved, sub-city locations.
-- Example predicate for future views:
--   WHERE geocode_precision IN ('rooftop','biased','street','suburb')
