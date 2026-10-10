-- Migration 007 — share of wallet by suburb
-- Run in the Supabase SQL editor. Idempotent.
--
-- Why: "who wins where" is the one thing no single retailer can see. A suburb's
-- residents split their spend across branches; receipts from many chains tied to
-- one customer are the only way to observe that split. We key it on the
-- *customer's* suburb (where the people are), not the shop's, so leakage
-- (Kraaifontein residents spending in Bellville) is visible.
--
-- upload_suburb / upload_locality are derived from the upload coordinates via
-- Google reverse geocoding (sublocality / locality). They are a home proxy and
-- therefore Personal (P) data: never served unaggregated, never publicly.
-- The wallet-share endpoint suppresses suburbs below the k-anonymity floor
-- (5 distinct customers) outside the admin surface.

ALTER TABLE receipts ADD COLUMN IF NOT EXISTS upload_suburb   VARCHAR(120);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS upload_locality VARCHAR(120);
CREATE INDEX IF NOT EXISTS idx_receipts_upload_suburb ON receipts(upload_suburb);
COMMENT ON COLUMN receipts.upload_suburb   IS 'Suburb of the upload point (Google sublocality). Home proxy — P-class';
COMMENT ON COLUMN receipts.upload_locality IS 'City/town of the upload point (Google locality). P-class';

-- Owning chain of a branch (brand_registry.infer_chain), stored so analytics
-- can group by it without re-deriving from the name on every request.
ALTER TABLE shops ADD COLUMN IF NOT EXISTS chain VARCHAR(60);
CREATE INDEX IF NOT EXISTS idx_shops_chain ON shops(chain);
COMMENT ON COLUMN shops.chain IS 'Owner group (Shoprite Group, Pick n Pay Group, SPAR, …); NULL = independent';

-- After running this, assign suburbs to existing receipts and chains to shops:
--   python scripts/backfill_suburbs.py              # dry run + wallet-share preview
--   python scripts/backfill_suburbs.py --apply
