-- Migration 005 — intelligence views: price observatory + incentive elasticity
-- Run in the Supabase SQL editor. Idempotent (CREATE OR REPLACE).

-- Price observatory: median/avg price per canonical item per month.
-- Gated by normalization coverage + receipt_date, not user volume. Aggregate only (X).
CREATE OR REPLACE VIEW item_price_index AS
SELECT
    ri.canonical_name,
    ri.category,
    TO_CHAR(COALESCE(r.receipt_date, r.created_at::date), 'YYYY-MM') AS month,
    COUNT(*) AS observations,
    COUNT(DISTINCT r.shop_id) AS branches,
    ROUND(AVG(ri.unit_price)::numeric, 2) AS avg_price,
    ROUND(MIN(ri.unit_price)::numeric, 2) AS min_price,
    ROUND(MAX(ri.unit_price)::numeric, 2) AS max_price,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ri.unit_price))::numeric, 2) AS median_price
FROM receipt_items ri
JOIN receipts r ON ri.receipt_id = r.id
WHERE ri.canonical_name IS NOT NULL
  AND ri.unit_price IS NOT NULL AND ri.unit_price > 0
  AND COALESCE(ri.category, 'Other') NOT IN ('Non-product', 'Other')
  AND r.status != 'rejected'
GROUP BY ri.canonical_name, ri.category, TO_CHAR(COALESCE(r.receipt_date, r.created_at::date), 'YYYY-MM')
HAVING COUNT(*) >= 2;

-- Incentive elasticity: receipts per winner 28 days before vs after their first win.
-- Aggregate only (X); mature = winners whose post-window has fully elapsed.
CREATE OR REPLACE VIEW incentive_elasticity AS
WITH first_wins AS (
    SELECT winner_customer_id AS customer_id, MIN(draw_date) AS first_win_date
    FROM draws
    WHERE status = 'completed' AND winner_customer_id IS NOT NULL
    GROUP BY winner_customer_id
),
rates AS (
    SELECT fw.customer_id,
           fw.first_win_date,
           (fw.first_win_date + 28) <= CURRENT_DATE AS mature,
           COUNT(r.id) FILTER (WHERE r.created_at::date BETWEEN fw.first_win_date - 28 AND fw.first_win_date - 1) AS receipts_before,
           COUNT(r.id) FILTER (WHERE r.created_at::date BETWEEN fw.first_win_date + 1 AND fw.first_win_date + 28) AS receipts_after
    FROM first_wins fw
    LEFT JOIN receipts r ON r.customer_id = fw.customer_id AND r.status != 'rejected'
    GROUP BY fw.customer_id, fw.first_win_date
)
SELECT
    COUNT(*) AS winners_total,
    COUNT(*) FILTER (WHERE mature) AS winners_mature,
    ROUND(AVG(receipts_before) FILTER (WHERE mature), 2) AS avg_receipts_28d_before,
    ROUND(AVG(receipts_after)  FILTER (WHERE mature), 2) AS avg_receipts_28d_after,
    CASE WHEN SUM(receipts_before) FILTER (WHERE mature) > 0
         THEN ROUND(SUM(receipts_after) FILTER (WHERE mature)::numeric
                    / SUM(receipts_before) FILTER (WHERE mature), 2)
    END AS lift_ratio
FROM rates;
