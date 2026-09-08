-- Migration 006 — house brands, pack sizes, product identity attributes
-- Run in the Supabase SQL editor. Idempotent.
--
-- Why: retailers white-label products (Ritebrand, No Name, SPAR brand…). To
-- compare Retailer A's house brand vs Retailer B's on the SAME product, the
-- comparable unit is (product type + pack size), with brand as an attribute:
--   type_key   brand-independent product key ("sugar white")
--   pack_size  normalized quantity in base unit (2.5KG -> 2500)
--   pack_unit  'g' | 'ml' | 'each'
--   brand_type 'house' | 'national'; brand_owner = owning chain; brand_tier
--              'value' | 'mainstream' | 'premium'
--   gtin       barcode where printed (Dis-Chem prints these) — the product
--              world's Place ID, check-digit validated
-- Values are written by item_normalizer.py + brand_registry.py at insert;
-- scripts/backfill_item_attributes.py fills existing rows.

ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS brand_type  VARCHAR(10);
ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS brand_owner VARCHAR(30);
ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS brand_tier  VARCHAR(12);
ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS pack_size   NUMERIC(12,3);
ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS pack_unit   VARCHAR(6);
ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS gtin        VARCHAR(14);
ALTER TABLE receipt_items ADD COLUMN IF NOT EXISTS type_key    VARCHAR(300);

CREATE INDEX IF NOT EXISTS idx_receipt_items_brand_owner ON receipt_items(brand_owner);
CREATE INDEX IF NOT EXISTS idx_receipt_items_type_key    ON receipt_items(type_key);

-- House-brand price gap: same product type + pack, house label vs house label
-- across chains. Aggregate only (X-class). Ontology: housebrandPriceGap.
CREATE OR REPLACE VIEW house_brand_price_gap AS
SELECT
    ri.type_key,
    ri.pack_size,
    ri.pack_unit,
    ri.brand_owner,
    ri.brand,
    ri.brand_tier,
    COUNT(*) AS observations,
    ROUND(AVG(ri.unit_price)::numeric, 2) AS avg_price,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ri.unit_price))::numeric, 2) AS median_price,
    CASE WHEN ri.pack_size > 0 AND ri.pack_unit IN ('g', 'ml')
         THEN ROUND((AVG(ri.unit_price) / ri.pack_size * 1000)::numeric, 2)
    END AS avg_price_per_kg_or_l
FROM receipt_items ri
JOIN receipts r ON ri.receipt_id = r.id
WHERE ri.brand_type = 'house'
  AND ri.type_key IS NOT NULL
  AND ri.unit_price IS NOT NULL AND ri.unit_price > 0
  AND r.status != 'rejected'
GROUP BY ri.type_key, ri.pack_size, ri.pack_unit, ri.brand_owner, ri.brand, ri.brand_tier
HAVING COUNT(*) >= 2;
