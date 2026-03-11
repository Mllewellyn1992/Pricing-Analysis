-- =============================================================================
-- Credit Pricing Tool - Supabase Schema
-- =============================================================================
-- Run this in Supabase SQL Editor to create all tables + RLS policies.
-- Designed for multi-tenant use: each user sees only their own data.
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 1. COMPANIES - Stores company profiles created by users
-- =============================================================================
CREATE TABLE IF NOT EXISTS companies (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,                       -- Business description for AI sector mapping
    sp_sector       TEXT,                       -- S&P sector ID (e.g. "technology_software_and_services")
    moodys_sector   TEXT,                       -- Moody's methodology ID (e.g. "software")
    sector_confidence FLOAT,                    -- AI classification confidence (0-1)
    country         TEXT DEFAULT 'NZ',
    currency        TEXT DEFAULT 'NZD',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_companies_user ON companies(user_id);

-- =============================================================================
-- 2. FINANCIAL_SNAPSHOTS - Point-in-time financial data for a company
-- =============================================================================
CREATE TABLE IF NOT EXISTS financial_snapshots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    label           TEXT,                       -- e.g. "FY2025", "H1 2025"
    as_of_date      DATE,                      -- Financial statement date

    -- Income Statement (all in millions, local currency)
    revenue_mn              FLOAT,
    ebit_mn                 FLOAT,
    depreciation_mn         FLOAT,
    amortization_mn         FLOAT,
    interest_expense_mn     FLOAT,
    cash_interest_paid_mn   FLOAT,
    cash_taxes_paid_mn      FLOAT,

    -- Balance Sheet
    st_debt_mn              FLOAT DEFAULT 0,
    cpltd_mn                FLOAT DEFAULT 0,
    lt_debt_net_mn          FLOAT DEFAULT 0,
    capital_leases_mn       FLOAT DEFAULT 0,
    total_debt_mn           FLOAT,              -- Computed or entered directly
    cash_mn                 FLOAT DEFAULT 0,
    cash_like_mn            FLOAT DEFAULT 0,
    marketable_securities_mn FLOAT DEFAULT 0,
    total_equity_mn         FLOAT DEFAULT 0,
    minority_interest_mn    FLOAT DEFAULT 0,
    deferred_taxes_mn       FLOAT DEFAULT 0,
    nwc_current_mn          FLOAT DEFAULT 0,
    nwc_prior_mn            FLOAT DEFAULT 0,
    lt_operating_assets_current_mn FLOAT DEFAULT 0,
    lt_operating_assets_prior_mn   FLOAT DEFAULT 0,
    assets_current_mn       FLOAT DEFAULT 0,
    assets_prior_mn         FLOAT DEFAULT 0,

    -- Cash Flow
    cfo_mn                  FLOAT,
    capex_mn                FLOAT DEFAULT 0,
    common_dividends_mn     FLOAT DEFAULT 0,
    preferred_dividends_mn  FLOAT DEFAULT 0,
    minority_dividends_mn   FLOAT DEFAULT 0,
    share_buybacks_mn       FLOAT DEFAULT 0,
    dividends_paid_mn       FLOAT DEFAULT 0,   -- Total dividends (convenience field)
    avg_capital_mn          FLOAT DEFAULT 0,

    -- Metadata
    source          TEXT DEFAULT 'manual',      -- 'manual', 'pdf_upload', 'api'
    pdf_filename    TEXT,                       -- Original PDF filename if uploaded
    confidence      FLOAT,                     -- Extraction confidence (0-1)
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_snapshots_company ON financial_snapshots(company_id);
CREATE INDEX idx_snapshots_user ON financial_snapshots(user_id);

-- =============================================================================
-- 3. ANALYSES - Rating + pricing results
-- =============================================================================
CREATE TABLE IF NOT EXISTS analyses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    snapshot_id     UUID NOT NULL REFERENCES financial_snapshots(id) ON DELETE CASCADE,

    -- Rating results (internal, never shown to end users as letter ratings)
    sp_rating           TEXT,                   -- e.g. "BBB+"
    sp_anchor           TEXT,
    sp_business_risk    INT,
    sp_financial_risk   INT,
    moodys_rating       TEXT,                   -- e.g. "Baa1"
    moodys_sp_equiv     TEXT,                   -- S&P equivalent of Moody's rating
    moodys_score        FLOAT,
    blended_rating      TEXT,                   -- AI-blended final rating

    -- Pricing results (this is what users see)
    spread_min_bps      FLOAT,
    spread_max_bps      FLOAT,
    spread_mid_bps      FLOAT,
    base_rate_pct       FLOAT,                  -- NZ base rate used
    base_rate_type      TEXT,                   -- 'corporate' or 'working_capital'
    expected_rate_min   FLOAT,                  -- base + spread min
    expected_rate_max   FLOAT,                  -- base + spread max
    expected_rate_mid   FLOAT,                  -- base + spread mid

    -- Comparison
    actual_rate_pct     FLOAT,                  -- User's actual borrowing rate
    delta_bps           FLOAT,                  -- actual - expected mid (positive = overpaying)
    facility_tenor      INT DEFAULT 3,          -- Years
    facility_type       TEXT DEFAULT 'corporate',

    -- Computed metrics snapshot (JSONB for flexibility)
    computed_metrics    JSONB,                  -- All ratios: debt_ebitda, ffo_debt, etc.
    sp_workings         JSONB,                  -- Full S&P engine audit trail
    moodys_workings     JSONB,                  -- Full Moody's engine audit trail

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analyses_company ON analyses(company_id);
CREATE INDEX idx_analyses_user ON analyses(user_id);
CREATE INDEX idx_analyses_created ON analyses(created_at DESC);

-- =============================================================================
-- 4. BASE_RATES - Historical NZ bank base rates (scraped)
-- =============================================================================
CREATE TABLE IF NOT EXISTS base_rates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank            TEXT NOT NULL,              -- 'ANZ', 'ASB', 'BNZ', 'Westpac', 'Kiwibank'
    corporate_rate  FLOAT,
    working_capital_rate FLOAT,
    overdraft_rate  FLOAT,
    scraped_at      TIMESTAMPTZ DEFAULT NOW(),
    source_url      TEXT DEFAULT 'https://www.interest.co.nz/borrowing/business-base-rates'
);

CREATE INDEX idx_base_rates_bank ON base_rates(bank, scraped_at DESC);

-- =============================================================================
-- 5. PDF_UPLOADS - Track uploaded financial statement PDFs
-- =============================================================================
CREATE TABLE IF NOT EXISTS pdf_uploads (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id      UUID REFERENCES companies(id) ON DELETE SET NULL,
    filename        TEXT NOT NULL,
    file_size_bytes BIGINT,
    storage_path    TEXT,                       -- Supabase Storage path
    extraction_status TEXT DEFAULT 'pending',   -- 'pending', 'processing', 'completed', 'failed'
    extracted_fields JSONB,                     -- Extracted financial data
    confidence_scores JSONB,                    -- Per-field confidence
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX idx_uploads_user ON pdf_uploads(user_id);

-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- =============================================================================

-- Enable RLS on all user-facing tables
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE pdf_uploads ENABLE ROW LEVEL SECURITY;

-- base_rates is public read (no user_id column)
ALTER TABLE base_rates ENABLE ROW LEVEL SECURITY;

-- Companies: users can only CRUD their own
CREATE POLICY "Users can view own companies"
    ON companies FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own companies"
    ON companies FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own companies"
    ON companies FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own companies"
    ON companies FOR DELETE
    USING (auth.uid() = user_id);

-- Financial snapshots: users can only CRUD their own
CREATE POLICY "Users can view own snapshots"
    ON financial_snapshots FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own snapshots"
    ON financial_snapshots FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own snapshots"
    ON financial_snapshots FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own snapshots"
    ON financial_snapshots FOR DELETE
    USING (auth.uid() = user_id);

-- Analyses: users can only view/create their own
CREATE POLICY "Users can view own analyses"
    ON analyses FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own analyses"
    ON analyses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own analyses"
    ON analyses FOR DELETE
    USING (auth.uid() = user_id);

-- PDF uploads: users can only CRUD their own
CREATE POLICY "Users can view own uploads"
    ON pdf_uploads FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own uploads"
    ON pdf_uploads FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own uploads"
    ON pdf_uploads FOR DELETE
    USING (auth.uid() = user_id);

-- Base rates: everyone can read (public data)
CREATE POLICY "Anyone can view base rates"
    ON base_rates FOR SELECT
    USING (true);

-- Only service role can insert base rates (from scraper)
CREATE POLICY "Service role can insert base rates"
    ON base_rates FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

-- =============================================================================
-- STORAGE BUCKET for PDF uploads
-- =============================================================================
-- Run this separately in Supabase dashboard or via API:
-- INSERT INTO storage.buckets (id, name, public) VALUES ('financial-pdfs', 'financial-pdfs', false);

-- Storage policies
-- CREATE POLICY "Users can upload PDFs"
--     ON storage.objects FOR INSERT
--     WITH CHECK (bucket_id = 'financial-pdfs' AND auth.uid()::text = (storage.foldername(name))[1]);

-- CREATE POLICY "Users can view own PDFs"
--     ON storage.objects FOR SELECT
--     USING (bucket_id = 'financial-pdfs' AND auth.uid()::text = (storage.foldername(name))[1]);

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER snapshots_updated_at
    BEFORE UPDATE ON financial_snapshots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Compute total_debt if components provided
CREATE OR REPLACE FUNCTION compute_total_debt()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.total_debt_mn IS NULL AND (
        NEW.st_debt_mn IS NOT NULL OR
        NEW.cpltd_mn IS NOT NULL OR
        NEW.lt_debt_net_mn IS NOT NULL OR
        NEW.capital_leases_mn IS NOT NULL
    ) THEN
        NEW.total_debt_mn = COALESCE(NEW.st_debt_mn, 0) +
                            COALESCE(NEW.cpltd_mn, 0) +
                            COALESCE(NEW.lt_debt_net_mn, 0) +
                            COALESCE(NEW.capital_leases_mn, 0);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER snapshots_compute_debt
    BEFORE INSERT OR UPDATE ON financial_snapshots
    FOR EACH ROW EXECUTE FUNCTION compute_total_debt();
