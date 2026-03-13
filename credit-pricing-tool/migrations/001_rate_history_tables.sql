-- ============================================================================
-- Migration 001: Rate History Tables
--
-- Run this SQL in your Supabase SQL Editor (Dashboard > SQL Editor > New query)
-- These tables store all scraped rate data persistently for time series charts
-- and audit trails.
-- ============================================================================

-- 1. Bank product rate snapshots (one row per product per scrape)
CREATE TABLE IF NOT EXISTS rate_snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    bank text NOT NULL,
    product_name text NOT NULL,
    rate_pct numeric(8,4) NOT NULL,
    rate_type text,
    category text,
    source_url text
);

CREATE INDEX IF NOT EXISTS idx_rate_snapshots_bank_product
    ON rate_snapshots (bank, product_name, scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_rate_snapshots_scraped_at
    ON rate_snapshots (scraped_at DESC);

-- 2. Wholesale rate snapshots (BKBM, swap, govt bond)
CREATE TABLE IF NOT EXISTS wholesale_rate_snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    rate_name text NOT NULL,
    rate_pct numeric(8,4) NOT NULL,
    tenor text NOT NULL,
    rate_type text NOT NULL,
    rate_date text,
    source text
);

CREATE INDEX IF NOT EXISTS idx_wholesale_rate_type
    ON wholesale_rate_snapshots (rate_type, tenor, scraped_at DESC);

-- 3. OCR (Official Cash Rate) snapshots
CREATE TABLE IF NOT EXISTS ocr_snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    rate_pct numeric(8,4) NOT NULL,
    decision_date text,
    source text
);

CREATE INDEX IF NOT EXISTS idx_ocr_scraped_at
    ON ocr_snapshots (scraped_at DESC);

-- 4. Scrape audit log (detailed record of every scrape run)
CREATE TABLE IF NOT EXISTS scrape_audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    trigger_type text NOT NULL DEFAULT 'manual',
    duration_ms integer,
    banks_scraped text[] DEFAULT '{}',
    product_count integer DEFAULT 0,
    ocr_rate numeric(8,4),
    wholesale_count integer DEFAULT 0,
    errors text[] DEFAULT '{}',
    raw_result jsonb
);

CREATE INDEX IF NOT EXISTS idx_audit_scraped_at
    ON scrape_audit_log (scraped_at DESC);

-- 5. Disable RLS on rate tables (public data, not user-specific)
ALTER TABLE rate_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE wholesale_rate_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocr_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE scrape_audit_log ENABLE ROW LEVEL SECURITY;

-- Allow anonymous read/write (these are public rate tables)
CREATE POLICY "Allow all access to rate_snapshots" ON rate_snapshots
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all access to wholesale_rate_snapshots" ON wholesale_rate_snapshots
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all access to ocr_snapshots" ON ocr_snapshots
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all access to scrape_audit_log" ON scrape_audit_log
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================================
-- Verification: Run this to confirm tables were created
-- ============================================================================
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name IN ('rate_snapshots', 'wholesale_rate_snapshots', 'ocr_snapshots', 'scrape_audit_log');
