-- Migration 001 — item normalization columns + category_spend view
-- Run in the Supabase SQL editor on the LIVE database (additive, safe, idempotent).
-- Backfill is optional; new receipts populate these automatically via item_normalizer.py.

ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS canonical_name VARCHAR(500);
ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS category       VARCHAR(40);
ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS brand          VARCHAR(60);

CREATE INDEX IF NOT EXISTS idx_receipt_items_category ON receipt_items(category);

CREATE OR REPLACE VIEW category_spend AS
SELECT
    COALESCE(ri.category, 'Other') AS category,
    TO_CHAR(r.created_at, 'YYYY-MM') AS month,
    COUNT(*) AS line_count,
    SUM(ri.quantity) AS total_qty,
    SUM(ri.total_price) AS total_spent,
    AVG(ri.unit_price) AS avg_unit_price
FROM receipt_items ri
JOIN receipts r ON ri.receipt_id = r.id
WHERE r.status != 'rejected'
GROUP BY COALESCE(ri.category, 'Other'), TO_CHAR(r.created_at, 'YYYY-MM');

-- Optional backfill of existing rows is done from Python (item_normalizer) rather
-- than SQL, since the category rules live in code:
--   python backend/scripts/backfill_categories.py   (not included; run ad hoc if needed)
