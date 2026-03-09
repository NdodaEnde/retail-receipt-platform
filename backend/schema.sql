-- Receipt-to-Win: Supabase PostgreSQL Schema
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- CUSTOMERS TABLE
-- ============================================
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255),
    first_name VARCHAR(255),
    surname VARCHAR(255),
    registration_status VARCHAR(20) DEFAULT 'unregistered',
    invited_by VARCHAR(255),
    invited_at TIMESTAMP WITH TIME ZONE,
    total_receipts INTEGER DEFAULT 0,
    total_spent DECIMAL(12, 2) DEFAULT 0.00,
    total_wins INTEGER DEFAULT 0,
    total_winnings DECIMAL(12, 2) DEFAULT 0.00,
    last_latitude DECIMAL(10, 7),
    last_longitude DECIMAL(10, 7),
    location_updated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_customers_phone ON customers(phone_number);
CREATE INDEX idx_customers_created ON customers(created_at DESC);

-- ============================================
-- SHOPS TABLE
-- ============================================
CREATE TABLE shops (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    address TEXT,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    geocoded_address TEXT,
    geocode_confidence VARCHAR(20),
    geocoded_at TIMESTAMP WITH TIME ZONE,
    receipt_count INTEGER DEFAULT 0,
    total_sales DECIMAL(12, 2) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_shops_name ON shops(name);
CREATE INDEX idx_shops_location ON shops(latitude, longitude);
CREATE INDEX idx_shops_receipt_count ON shops(receipt_count DESC);

-- ============================================
-- RECEIPTS TABLE
-- ============================================
CREATE TABLE receipts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    customer_phone VARCHAR(20) NOT NULL,
    shop_id UUID REFERENCES shops(id) ON DELETE SET NULL,
    shop_name VARCHAR(255),
    amount DECIMAL(12, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'ZAR',
    
    -- Image stored in Supabase Storage, URL reference here
    image_url TEXT,
    image_path TEXT,  -- Storage bucket path
    
    -- Raw OCR data
    raw_text TEXT,
    
    -- Customer upload location
    upload_latitude DECIMAL(10, 7),
    upload_longitude DECIMAL(10, 7),
    upload_address TEXT,
    
    -- Shop location from receipt
    shop_latitude DECIMAL(10, 7),
    shop_longitude DECIMAL(10, 7),
    shop_address TEXT,
    
    -- Fraud detection
    distance_km DECIMAL(8, 2),
    fraud_flag VARCHAR(20) DEFAULT 'valid',  -- valid, review, suspicious, flagged
    fraud_score INTEGER DEFAULT 0,  -- 0-100
    fraud_reason TEXT,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processed, won, rejected
    processing_error TEXT,
    
    -- Metadata
    receipt_date DATE,
    grounding JSONB,  -- OCR grounding data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_receipts_customer ON receipts(customer_id);
CREATE INDEX idx_receipts_customer_phone ON receipts(customer_phone);
CREATE INDEX idx_receipts_shop ON receipts(shop_id);
CREATE INDEX idx_receipts_status ON receipts(status);
CREATE INDEX idx_receipts_fraud_flag ON receipts(fraud_flag);
CREATE INDEX idx_receipts_created ON receipts(created_at DESC);
CREATE INDEX idx_receipts_date ON receipts(receipt_date DESC);
CREATE INDEX idx_receipts_amount ON receipts(amount DESC);

-- ============================================
-- RECEIPT ITEMS TABLE (Normalized for analytics)
-- ============================================
CREATE TABLE receipt_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    receipt_id UUID REFERENCES receipts(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    quantity INTEGER DEFAULT 1,
    unit_price DECIMAL(10, 2),
    total_price DECIMAL(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_receipt_items_receipt ON receipt_items(receipt_id);
CREATE INDEX idx_receipt_items_name ON receipt_items(name);
CREATE INDEX idx_receipt_items_price ON receipt_items(total_price DESC);

-- ============================================
-- DRAWS TABLE
-- ============================================
CREATE TABLE draws (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    draw_date DATE UNIQUE NOT NULL,
    total_receipts INTEGER DEFAULT 0,
    total_amount DECIMAL(12, 2) DEFAULT 0.00,
    winner_receipt_id UUID REFERENCES receipts(id) ON DELETE SET NULL,
    winner_customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    winner_customer_phone VARCHAR(20),
    prize_amount DECIMAL(12, 2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, completed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_draws_date ON draws(draw_date DESC);
CREATE INDEX idx_draws_status ON draws(status);
CREATE INDEX idx_draws_winner ON draws(winner_customer_phone);

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to tables
CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_shops_updated_at BEFORE UPDATE ON shops
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_receipts_updated_at BEFORE UPDATE ON receipts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- ANALYTICS VIEWS
-- ============================================

-- Daily spending summary
CREATE VIEW daily_spending AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as receipt_count,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount,
    COUNT(DISTINCT customer_phone) as unique_customers
FROM receipts
WHERE status != 'rejected'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Shop performance
CREATE VIEW shop_performance AS
SELECT 
    s.id,
    s.name,
    s.address,
    s.latitude,
    s.longitude,
    COUNT(r.id) as receipt_count,
    SUM(r.amount) as total_sales,
    AVG(r.amount) as avg_transaction,
    COUNT(DISTINCT r.customer_phone) as unique_customers
FROM shops s
LEFT JOIN receipts r ON s.id = r.shop_id
GROUP BY s.id, s.name, s.address, s.latitude, s.longitude
ORDER BY total_sales DESC NULLS LAST;

-- Customer summary
CREATE VIEW customer_summary AS
SELECT 
    c.id,
    c.phone_number,
    c.name,
    c.total_receipts,
    c.total_spent,
    c.total_wins,
    c.total_winnings,
    COUNT(r.id) as actual_receipts,
    MAX(r.created_at) as last_receipt_date
FROM customers c
LEFT JOIN receipts r ON c.id = r.customer_id
GROUP BY c.id, c.phone_number, c.name, c.total_receipts, c.total_spent, c.total_wins, c.total_winnings
ORDER BY c.total_spent DESC;

-- Fraud analysis
CREATE VIEW fraud_analysis AS
SELECT 
    fraud_flag,
    COUNT(*) as count,
    AVG(distance_km) as avg_distance,
    MAX(distance_km) as max_distance,
    AVG(amount) as avg_amount
FROM receipts
WHERE distance_km IS NOT NULL
GROUP BY fraud_flag;

-- Hourly receipt distribution
CREATE VIEW hourly_distribution AS
SELECT 
    EXTRACT(HOUR FROM created_at) as hour,
    COUNT(*) as receipt_count,
    SUM(amount) as total_amount
FROM receipts
GROUP BY EXTRACT(HOUR FROM created_at)
ORDER BY hour;

-- ============================================
-- PENDING STATE TABLE (write-through cache)
-- ============================================
CREATE TABLE pending_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state_type VARCHAR(30) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    data JSONB NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_pending_state_type_phone ON pending_state(state_type, phone_number);
CREATE INDEX idx_pending_state_expires ON pending_state(expires_at);

-- ============================================
-- BASKET ANALYTICS VIEWS
-- ============================================

-- Top items by frequency
CREATE VIEW top_items AS
SELECT UPPER(TRIM(name)) AS item_name, COUNT(*) AS frequency,
       SUM(quantity) AS total_qty, AVG(unit_price) AS avg_price,
       MIN(unit_price) AS min_price, MAX(unit_price) AS max_price
FROM receipt_items ri JOIN receipts r ON ri.receipt_id = r.id
WHERE r.status != 'rejected'
GROUP BY UPPER(TRIM(name)) ORDER BY frequency DESC;

-- Items frequently bought together
CREATE VIEW item_pairs AS
SELECT LEAST(UPPER(TRIM(a.name)), UPPER(TRIM(b.name))) AS item_a,
       GREATEST(UPPER(TRIM(a.name)), UPPER(TRIM(b.name))) AS item_b,
       COUNT(DISTINCT a.receipt_id) AS co_occurrence
FROM receipt_items a JOIN receipt_items b ON a.receipt_id = b.receipt_id AND a.id < b.id
JOIN receipts r ON a.receipt_id = r.id WHERE r.status != 'rejected'
GROUP BY 1, 2 HAVING COUNT(DISTINCT a.receipt_id) >= 2 ORDER BY co_occurrence DESC;

-- Basket size stats per receipt
CREATE VIEW basket_stats AS
SELECT r.id, r.shop_name, r.amount, r.created_at,
       COUNT(ri.id) AS item_count, AVG(ri.unit_price) AS avg_item_price
FROM receipts r LEFT JOIN receipt_items ri ON r.id = ri.receipt_id
WHERE r.status != 'rejected' GROUP BY r.id, r.shop_name, r.amount, r.created_at;

-- Customer shopping behavior
CREATE VIEW customer_behavior AS
SELECT c.phone_number, c.first_name, c.surname, c.total_receipts, c.total_spent,
       CASE WHEN c.total_receipts > 0 THEN c.total_spent / c.total_receipts ELSE 0 END AS avg_basket,
       COUNT(DISTINCT r.shop_name) AS unique_shops,
       COUNT(DISTINCT DATE(r.created_at)) AS active_days
FROM customers c LEFT JOIN receipts r ON c.id = r.customer_id AND r.status != 'rejected'
GROUP BY c.phone_number, c.first_name, c.surname, c.total_receipts, c.total_spent;

-- ============================================
-- CUSTOMER SPEND ANALYTICS VIEWS
-- ============================================

-- Monthly spend per customer
CREATE OR REPLACE VIEW customer_monthly_spend AS
SELECT
    r.customer_phone,
    TO_CHAR(r.created_at, 'YYYY-MM') AS month,
    COUNT(*) AS receipt_count,
    SUM(r.amount) AS total_spent,
    AVG(r.amount) AS avg_receipt,
    COUNT(DISTINCT r.shop_name) AS unique_shops
FROM receipts r
WHERE r.status != 'rejected'
GROUP BY r.customer_phone, TO_CHAR(r.created_at, 'YYYY-MM')
ORDER BY r.customer_phone, month DESC;

-- Spend by shop per customer
CREATE OR REPLACE VIEW customer_shop_spend AS
SELECT
    r.customer_phone,
    r.shop_name,
    COUNT(*) AS receipt_count,
    SUM(r.amount) AS total_spent,
    AVG(r.amount) AS avg_receipt,
    MAX(r.created_at) AS last_visit
FROM receipts r
WHERE r.status != 'rejected'
GROUP BY r.customer_phone, r.shop_name
ORDER BY r.customer_phone, total_spent DESC;

-- Overall spend summary per customer (with period breakdowns)
CREATE OR REPLACE VIEW customer_spend_summary AS
SELECT
    r.customer_phone,
    COUNT(*) AS total_receipts,
    SUM(r.amount) AS total_spent,
    AVG(r.amount) AS avg_receipt,
    MIN(r.amount) AS min_receipt,
    MAX(r.amount) AS max_receipt,
    COUNT(DISTINCT r.shop_name) AS unique_shops,
    COUNT(DISTINCT DATE(r.created_at)) AS active_days,
    MIN(r.created_at) AS first_receipt,
    MAX(r.created_at) AS last_receipt,
    -- Current month
    SUM(CASE WHEN TO_CHAR(r.created_at, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM') THEN r.amount ELSE 0 END) AS this_month_spent,
    COUNT(CASE WHEN TO_CHAR(r.created_at, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM') THEN 1 END) AS this_month_receipts,
    -- Current year
    SUM(CASE WHEN EXTRACT(YEAR FROM r.created_at) = EXTRACT(YEAR FROM NOW()) THEN r.amount ELSE 0 END) AS this_year_spent,
    COUNT(CASE WHEN EXTRACT(YEAR FROM r.created_at) = EXTRACT(YEAR FROM NOW()) THEN 1 END) AS this_year_receipts
FROM receipts r
WHERE r.status != 'rejected'
GROUP BY r.customer_phone;

-- ============================================
-- ROW LEVEL SECURITY (Optional - for future)
-- ============================================

-- Enable RLS on tables (uncomment when ready)
-- ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE receipts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE receipt_items ENABLE ROW LEVEL SECURITY;

-- ============================================
-- STORAGE BUCKET SETUP (Run in Supabase Dashboard)
-- ============================================
-- Create a bucket called 'receipts' in Supabase Storage
-- Set it to public or create policies as needed

COMMENT ON TABLE customers IS 'Registered customers identified by phone number';
COMMENT ON TABLE shops IS 'Retail shops detected from receipts';
COMMENT ON TABLE receipts IS 'Uploaded receipts with OCR data and fraud scoring';
COMMENT ON TABLE receipt_items IS 'Individual line items from receipts for basket analysis';
COMMENT ON TABLE draws IS 'Daily prize draws with winners';
