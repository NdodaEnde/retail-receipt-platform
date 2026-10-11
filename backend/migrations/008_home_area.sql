-- Migration 008 — customer home area
-- Run in the Supabase SQL editor. Idempotent. Adds columns only — nothing is dropped;
-- receipts.upload_suburb / upload_locality (migration 007) stay as they are.
--
-- Why: share of wallet needs where people LIVE; where a receipt is sent from is
-- often the shop itself (41% within 0.5 km). So the bot also asks once, optionally:
-- "Which area do you live in?" — suburb/township level, never an address,
-- customer can SKIP, change (AREA) or remove it. P-class: admin-only, aggregated.

ALTER TABLE customers ADD COLUMN IF NOT EXISTS home_suburb        VARCHAR(120);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS home_locality      VARCHAR(120);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS home_area_asked_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_customers_home_suburb ON customers(home_suburb);
COMMENT ON COLUMN customers.home_suburb        IS 'Home suburb/township the customer chose to share (normalised via Google). P-class';
COMMENT ON COLUMN customers.home_locality      IS 'City/town of home_suburb. P-class';
COMMENT ON COLUMN customers.home_area_asked_at IS 'When the optional home-area question was asked — it is asked once';
