-- Migration 002 — exclude non-product rows from category analytics
-- Run in the Supabase SQL editor (idempotent CREATE OR REPLACE).
-- Non-product rows (department subtotals, headers, VAT/rounding lines, bags,
-- OCR-description fragments) are tagged category='Non-product' by
-- item_normalizer.py and must not appear in the category spend breakdown.

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
  AND COALESCE(ri.category, 'Other') <> 'Non-product'
GROUP BY COALESCE(ri.category, 'Other'), TO_CHAR(r.created_at, 'YYYY-MM');
