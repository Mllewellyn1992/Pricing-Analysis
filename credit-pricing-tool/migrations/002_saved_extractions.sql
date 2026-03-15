-- Saved extractions table: stores PDF extraction results for later review
-- Each row is a named extraction that the user can reload into the form

CREATE TABLE IF NOT EXISTS saved_extractions (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name            TEXT NOT NULL,                    -- User-chosen name, e.g. "Ryman H1 2025"
    filename        TEXT,                             -- Original PDF filename
    extracted_fields JSONB NOT NULL DEFAULT '{}',     -- All financial fields as key-value
    confidence_scores JSONB DEFAULT '{}',             -- Per-field confidence scores
    extraction_method TEXT DEFAULT 'ai',              -- 'ai', 'heuristic', 'manual'
    sector_classification JSONB DEFAULT NULL,         -- AI sector classification result
    business_description TEXT DEFAULT NULL,           -- Business description
    warnings        JSONB DEFAULT '[]',               -- Extraction warnings array
    fiscal_period   TEXT DEFAULT NULL,                -- e.g. "FY2025", "H1 2025", "interim"
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for listing by recency
CREATE INDEX IF NOT EXISTS idx_saved_extractions_created
    ON saved_extractions (created_at DESC);

-- RLS: public access (no auth for now)
ALTER TABLE saved_extractions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public access to saved_extractions"
    ON saved_extractions FOR ALL
    USING (true)
    WITH CHECK (true);
