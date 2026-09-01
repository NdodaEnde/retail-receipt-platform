-- Migration 004 — shops keyed by Google Place ID (the branch is the entity)
-- Run in the Supabase SQL editor. Idempotent; safe to run even if 003 was never run
-- (it re-applies 003's column too).
--
-- Why: shops were matched by OCR'd name, so "PICK N PAY" in Cape Town and
-- Douglasdale collapsed into one shop, and one bad geocode poisoned every later
-- receipt at that name. shop_resolver.py now returns a Google Place ID for every
-- resolved branch; that becomes the identity, names become aliases.

-- 003 (re-applied, idempotent)
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS geocode_precision VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_receipts_geocode_precision ON receipts(geocode_precision);

-- 004
ALTER TABLE shops ADD COLUMN IF NOT EXISTS place_id TEXT;
ALTER TABLE shops ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
CREATE UNIQUE INDEX IF NOT EXISTS idx_shops_place_id ON shops(place_id) WHERE place_id IS NOT NULL;
COMMENT ON COLUMN shops.place_id IS 'Google Place ID of the branch — the canonical identity when present';
COMMENT ON COLUMN shops.phone IS 'Branch phone number as printed on receipts, E.164 (+27...)';

-- Names seen on receipts for a shop ("PICK N PAY", "Pick n Pay", "<::LOGO: PICK N PAY").
-- Not a lookup key (a chain name maps to many branches) — an audit/analytics aid.
CREATE TABLE IF NOT EXISTS shop_aliases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    alias VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (shop_id, alias)
);
CREATE INDEX IF NOT EXISTS idx_shop_aliases_alias ON shop_aliases(alias);

-- After running this, populate identities from existing receipts:
--   python scripts/backfill_shop_identity.py            # dry run
--   python scripts/backfill_shop_identity.py --apply
