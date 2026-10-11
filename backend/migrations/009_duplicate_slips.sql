-- Migration 009 — duplicate slips: one till slip enters the draw once
-- Run in the Supabase SQL editor. Idempotent. Adds columns + one table; nothing is dropped.
--
-- Why: nothing stopped the same slip being entered twice — by the same customer
-- (an honest double-send) or by several customers sharing one photo (gaming the
-- draw). duplicate_guard.py fingerprints every slip; these columns hold the
-- fingerprint and the verdict, fraud_signals keeps the evidence.
--
-- Same customer  -> told "we already have it", nothing saved (logged as 'resend')
-- Other customer -> saved, draw_eligible=false, fraud_flag/status 'review', told
--                   neutrally "already entered"; logged as 'cross_customer_duplicate'

ALTER TABLE receipts ADD COLUMN IF NOT EXISTS image_hash      VARCHAR(64);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS slip_time       VARCHAR(5);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS transaction_ref VARCHAR(40);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS duplicate_of    UUID REFERENCES receipts(id) ON DELETE SET NULL;
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS duplicate_kind  VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_receipts_amount_created ON receipts(amount, created_at);
CREATE INDEX IF NOT EXISTS idx_receipts_duplicate_of   ON receipts(duplicate_of);
COMMENT ON COLUMN receipts.image_hash      IS '256-bit perceptual (difference) hash of the slip photo, hex';
COMMENT ON COLUMN receipts.slip_time       IS 'Sale time printed on the slip (HH:MM), verified against the OCR text';
COMMENT ON COLUMN receipts.transaction_ref IS 'Transaction / invoice / till-slip number printed on the slip, verified';
COMMENT ON COLUMN receipts.duplicate_of    IS 'The original receipt this slip copies (NULL = an original)';
COMMENT ON COLUMN receipts.duplicate_kind  IS 'same_image | same_transaction | same_content | cleared (admin judged it a different slip)';

-- Evidence log. Personal (P) data — phones and upload points: admin-only, never exported.
CREATE TABLE IF NOT EXISTS fraud_signals (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kind               VARCHAR(40) NOT NULL,     -- resend | cross_customer_duplicate
    customer_phone     VARCHAR(20) NOT NULL,     -- who sent this copy (no '+')
    receipt_id         UUID REFERENCES receipts(id) ON DELETE SET NULL,   -- this copy (NULL when not saved)
    matched_receipt_id UUID REFERENCES receipts(id) ON DELETE SET NULL,   -- the original
    matched_phone      VARCHAR(20),              -- who sent the original
    match_kind         VARCHAR(20),              -- same_image | same_transaction | same_content
    same_customer      BOOLEAN NOT NULL DEFAULT FALSE,
    upload_latitude    DOUBLE PRECISION,
    upload_longitude   DOUBLE PRECISION,
    details            JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_fraud_signals_phone   ON fraud_signals(customer_phone, created_at);
CREATE INDEX IF NOT EXISTS idx_fraud_signals_matched ON fraud_signals(matched_phone);
ALTER TABLE fraud_signals ENABLE ROW LEVEL SECURITY;   -- service role only; no anon/authenticated policies

-- After running this, fingerprint existing slips and take the test copies out of the draw:
--   python scripts/backfill_duplicates.py            # dry run
--   python scripts/backfill_duplicates.py --apply
