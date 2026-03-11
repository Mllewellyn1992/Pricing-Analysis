# Credit Pricing Tool - Backend API Documentation

## Overview

The Credit Pricing Tool backend provides a FastAPI-based REST API for credit rating and pricing analysis. It combines S&P and Moody's rating engines with NZ base rate lookups and pricing matrix analysis.

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Running the Server

From the project root directory:

```bash
uvicorn api.main:app --reload
```

The server will be available at `http://localhost:8000`

- Interactive API docs: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

### CORS Configuration

The API is configured with CORS enabled for:
- `http://localhost:5173` (Vite dev server)
- `http://localhost:3000` (Alternative dev server)

## API Endpoints

### 1. Rating Engine

#### POST `/api/rate`

Rate a company using both S&P and Moody's engines, returns blended rating.

**Request Body:**
```json
{
  "financials": {
    "revenue_mn": 1000,
    "ebit_mn": 150,
    "depreciation_mn": 50,
    "amortization_mn": 20,
    "interest_expense_mn": 30,
    "cash_interest_paid_mn": 30,
    "cash_taxes_paid_mn": 20,
    "total_debt_mn": 200,
    "cash_mn": 50,
    "avg_capital_mn": 500,
    "cfo_mn": 120,
    "capex_mn": 40,
    "dividends_paid_mn": 20,
    "share_buybacks_mn": 10,
    "st_debt_mn": 20,
    "cpltd_mn": 30,
    "lt_debt_net_mn": 150,
    "capital_leases_mn": 0,
    "cash_like_mn": 10,
    "nwc_current_mn": 100,
    "nwc_prior_mn": 95,
    "lt_operating_assets_current_mn": 500,
    "lt_operating_assets_prior_mn": 480,
    "common_dividends_mn": 20,
    "preferred_dividends_mn": 0,
    "minority_dividends_mn": 0,
    "total_equity_mn": 300,
    "minority_interest_mn": 0,
    "deferred_taxes_mn": 20,
    "assets_current_mn": 600,
    "assets_prior_mn": 580,
    "marketable_securities_mn": 5
  },
  "sector_id": "technology_software_and_services",
  "business_description": null
}
```

**Response:**
```json
{
  "sp_rating": "AA",
  "moodys_rating": "Aa3",
  "moodys_sp_equivalent": "AA-",
  "blended_rating": "AA-",
  "computed_metrics": {
    "sp_computed_ratios": { ... },
    "moodys_computed_metrics": { ... }
  },
  "sp_details": { ... },
  "moodys_details": { ... }
}
```

**Supported Sector IDs:**
- `technology_software_and_services`
- `mining`
- `regulated_utilities`
- `retail_and_restaurants`
- `engineering_and_construction`
- `pharmaceuticals`
- `aerospace_and_defense`
- `building_materials`
- `chemicals`
- `consumer_durables`
- (See engines/sp_defaults.py for full list)

**Features:**
- Runs both S&P and Moody's engines with country_risk=2 (New Zealand)
- Automatically maps sector to Moody's methodology
- Returns blended rating (average of both engines)
- Includes detailed computed ratios and factor scores
- Uses quant_only=True mode for consistent, data-driven ratings

---

### 2. Pricing Lookup

#### POST `/api/pricing/lookup`

Look up spreads from the pricing matrix for a given rating and tenor.

**Request Body:**
```json
{
  "rating": "BBB",
  "tenor": 3,
  "facility_type": "corporate"
}
```

**Response:**
```json
{
  "rating": "BBB",
  "tenor": 3,
  "min_spread_bps": 140,
  "max_spread_bps": 160,
  "mid_spread_bps": 150
}
```

**Parameters:**
- `rating`: S&P rating (AAA to CCC-)
- `tenor`: Years (1-5)
- `facility_type`: "corporate" or "working_capital" (for future filtering)

---

### 3. Full Pricing Analysis

#### POST `/api/pricing/full-analysis`

Complete analysis pipeline: rate company, look up spreads, compare to actual rate, and generate interpretation.

**Request Body:**
```json
{
  "financials": { ... },
  "sector_id": "technology_software_and_services",
  "actual_rate_pct": 6.5,
  "facility_tenor": 3,
  "facility_type": "corporate",
  "base_rate_type": "corporate"
}
```

**Response:**
```json
{
  "ratings": {
    "sp_rating": "AA",
    "moodys_rating": "Aa3",
    "moodys_sp_equivalent": "AA-",
    "blended_rating": "AA-",
    "computed_metrics": { ... },
    "sp_details": { ... },
    "moodys_details": { ... }
  },
  "spread": {
    "min_bps": 140,
    "max_bps": 160,
    "mid_bps": 150
  },
  "base_rate_pct": 5.5,
  "expected_rate_range": {
    "min_rate": 6.9,
    "mid_rate": 7.0,
    "max_rate": 7.1
  },
  "actual_rate_pct": 6.5,
  "delta_bps": -50,
  "interpretation": "Actual rate 6.50% is significantly tight (attractive pricing). Expected range: 6.90% - 7.10%."
}
```

**Output Fields:**
- `ratings`: Full rating output from both engines
- `spread`: Spread lookup result (min, mid, max bps)
- `base_rate_pct`: Current NZ base rate for facility type
- `expected_rate_range`: Expected rate range in % (min, mid, max)
- `actual_rate_pct`: Actual rate offered
- `delta_bps`: Difference from expected mid-point (in basis points)
- `interpretation`: Textual analysis of pricing relative to expectations

**Delta Interpretation:**
- **-50 to -10 bps**: Significantly tight (attractive)
- **-10 to 10 bps**: Inline with expectations
- **10 to 50 bps**: Slightly loose (above market)
- **50+ bps**: Significantly loose (poor pricing)

---

### 4. Base Rates

#### GET `/api/base-rates`

Get current NZ bank base rates (currently hardcoded defaults).

**Response:**
```json
[
  {
    "bank": "ANZ",
    "corporate_rate": 5.45,
    "working_capital_rate": 7.15,
    "last_updated": "2026-03-11"
  },
  {
    "bank": "ASB",
    "corporate_rate": 5.50,
    "working_capital_rate": 7.20,
    "last_updated": "2026-03-11"
  },
  {
    "bank": "BNZ",
    "corporate_rate": 5.55,
    "working_capital_rate": 7.30,
    "last_updated": "2026-03-11"
  },
  {
    "bank": "Westpac",
    "corporate_rate": 5.50,
    "working_capital_rate": 7.25,
    "last_updated": "2026-03-11"
  },
  {
    "bank": "Kiwibank",
    "corporate_rate": 5.60,
    "working_capital_rate": 7.35,
    "last_updated": "2026-03-11"
  }
]
```

**Current Rates (Defaults):**
- Corporate indicator: 5.50% (average across major banks)
- Working capital: 7.25% (average)

**Future Enhancement:**
This endpoint will be enhanced with live scraping to get real-time rates.

---

### 5. PDF Extraction (Stub)

#### POST `/api/extract/pdf`

Upload a PDF document for financial data extraction.

**Request:**
- Content-Type: `multipart/form-data`
- File: PDF document

**Response:**
```json
{
  "status": "extraction_pending",
  "extracted_fields": {},
  "filename": "financials.pdf",
  "message": "PDF extraction for 'financials.pdf' queued. Results will be available when processing completes."
}
```

**Current Status:**
This is a stub implementation. Production implementation will:
1. Extract text and tables from PDF
2. Use NLP/OCR to identify financial line items
3. Return structured financial data matching the financials dict schema
4. Handle multi-year comparisons

---

## Financial Data Schema

All rating endpoints expect a `financials` dictionary with these fields:

### Required for S&P Engine:
- `revenue_mn`: Revenue (millions)
- `ebit_mn`: EBIT (millions)
- `depreciation_mn`: Depreciation (millions)
- `amortization_mn`: Amortization (millions)
- `interest_expense_mn`: Interest expense (millions)
- `cash_interest_paid_mn`: Cash interest paid (millions)
- `cash_taxes_paid_mn`: Cash taxes paid (millions)
- `total_debt_mn`: Total debt (millions)
- `cash_mn`: Cash balance (millions)
- `avg_capital_mn`: Average capital (millions)
- `cfo_mn`: Operating cash flow (millions)
- `capex_mn`: Capital expenditures (millions)
- `dividends_paid_mn`: Dividends paid (millions)
- `share_buybacks_mn`: Share buybacks (millions)

### Required for Moody's Engine:
- `st_debt_mn`: Short-term debt (millions)
- `cpltd_mn`: Current portion of LT debt (millions)
- `lt_debt_net_mn`: Long-term debt net (millions)
- `capital_leases_mn`: Capital leases (millions)
- `cash_like_mn`: Cash-like assets (millions)
- `nwc_current_mn`: Net working capital - current year (millions)
- `nwc_prior_mn`: Net working capital - prior year (millions)
- `lt_operating_assets_current_mn`: LT operating assets - current (millions)
- `lt_operating_assets_prior_mn`: LT operating assets - prior (millions)
- `common_dividends_mn`: Common dividends (millions)
- `preferred_dividends_mn`: Preferred dividends (millions)
- `minority_dividends_mn`: Minority dividends (millions)
- `total_equity_mn`: Total equity (millions)
- `minority_interest_mn`: Minority interest (millions)
- `deferred_taxes_mn`: Deferred taxes (millions)
- `assets_current_mn`: Current assets (millions)
- `assets_prior_mn`: Prior year assets (millions)
- `marketable_securities_mn`: Marketable securities (millions)

---

## Error Handling

All endpoints return appropriate HTTP status codes:

- **200 OK**: Successful request
- **400 Bad Request**: Invalid input (missing field, invalid rating, etc.)
- **500 Internal Server Error**: Engine error (missing config, calculation failure, etc.)

**Error Response Format:**
```json
{
  "detail": "Error message explaining the issue"
}
```

**Common Errors:**
- `"Tenor 6 not found in pricing matrix"` → Use tenor 1-5
- `"Rating ABC not found for tenor 3"` → Use valid S&P rating
- `"Unknown facility type 'bond'"` → Use "corporate" or "working_capital"

---

## Sector Mapping: S&P to Moody's

The API automatically maps S&P sector IDs to Moody's methodologies:

| S&P Sector | Moody's Methodology |
|---|---|
| technology_software_and_services | software |
| mining | steel |
| regulated_utilities | telecommunications |
| retail_and_restaurants | retail_and_apparel |
| engineering_and_construction | construction |
| pharmaceuticals | pharmaceuticals |
| aerospace_and_defense | aerospace_defense |
| building_materials | building_materials |
| chemicals | chemicals |
| consumer_durables | consumer_durables |
| (any other) | diversified_manufacturing |

---

## Engine Architecture

### S&P Engine (`engines/sp_engine.py`)

Uses a methodology-based scoring system:
1. **Compute Ratios**: FFO, Debt/EBITDA, Interest Coverage, etc.
2. **Competitive Position**: Based on sector-specific factors
3. **Industry Risk**: CICRA matrix (cyclicality × competitive risk × country risk)
4. **Business Risk**: Blend of competitive position and industry risk
5. **Financial Risk**: Based on leverage and coverage ratios
6. **Anchor Rating**: From business risk + financial risk
7. **Modifiers**: Liquidity caps and qualitative adjustments (in full mode)
8. **Final Rating**: Anchor rating after modifiers

### Moody's Engine (`engines/moodys_wrapper.py`)

Universal metrics-based scoring:
1. **Compute Universal Metrics**: 40+ metrics including debt, leverage, margins, ROA
2. **Methodology Selection**: Different methodologies for different sectors
3. **Factor Scoring**: Weight-based scoring of quantitative factors
4. **Composite Score**: Weighted average of all factors
5. **Rating Conversion**: Composite score → Moody's rating (Aaa to Ca)
6. **S&P Equivalence**: Automatic conversion to S&P scale

### Blended Rating

- Average of S&P final rating and Moody's S&P-equivalent rating
- Provides consensus estimate when both engines available
- Smooths out differences between rating philosophies

---

## Pricing Matrix

Located at: `engines/configs/moodys/pricing_matrix.yaml`

Structure:
```yaml
tenors:
  "1":  # 1-year tenor
    "AAA": { min_bps: 15, max_bps: 30 }
    "AA": { min_bps: 35, max_bps: 50 }
    # ... more ratings ...
  "2":  # 2-year tenor
    # ...
```

Coverage:
- Tenors: 1-5 years
- Ratings: AAA to CCC-
- Easy to update with new market data

---

## Configuration Files

### Sector-Specific Methodologies
Location: `engines/configs/sp/sector_specific/`

Each sector (e.g., `technology_software_and_services.yaml`) contains:
- Factor definitions (Business Performance, Capital Structure, Liquidity, etc.)
- Subfactor weights
- Metric grids and scoring bands

### Industry Risk Matrix
Location: `engines/configs/sp/industry_risk.yaml`

6x6 matrix mapping:
- Cyclicality (1-6) × Competitive Risk (1-6) → Industry Risk Score

### Corporate Methodology
Location: `engines/configs/sp/corporate_method.yaml`

Core rating methodology:
- CICRA matrix (Industry Risk × Country Risk)
- Financial risk tables (standard, medial, low)
- Anchor rating mapping
- Modifier adjustments

---

## Production Considerations

### Enhancements Needed

1. **PDF Extraction**: Implement full document extraction pipeline
2. **Live Base Rates**: Add scraping for real-time NZ bank rates
3. **Caching**: Add Redis/memcached for repeated analyses
4. **Audit Logging**: Track all rating computations for compliance
5. **Database**: Store historical analyses for trend tracking
6. **Authentication**: API key or OAuth for access control
7. **Rate Limiting**: Prevent abuse with rate limiting middleware
8. **Monitoring**: Add structured logging and performance monitoring

### Performance

- Rating computation: ~50-100ms per call
- Pricing lookup: <5ms
- Full analysis: ~100-150ms (includes both engines)

### Deployment

The application is designed to run with standard ASGI servers:

```bash
# Development (with auto-reload)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production (multiple workers)
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## Examples

### Example 1: Rate a Software Company

```bash
curl -X POST http://localhost:8000/api/rate \
  -H "Content-Type: application/json" \
  -d '{
    "financials": {
      "revenue_mn": 5000,
      "ebit_mn": 1000,
      "depreciation_mn": 100,
      "amortization_mn": 50,
      "interest_expense_mn": 50,
      "cash_interest_paid_mn": 50,
      "cash_taxes_paid_mn": 200,
      "total_debt_mn": 500,
      "cash_mn": 200,
      "avg_capital_mn": 3000,
      "cfo_mn": 800,
      "capex_mn": 100,
      "dividends_paid_mn": 100,
      "share_buybacks_mn": 50,
      "st_debt_mn": 50,
      "cpltd_mn": 50,
      "lt_debt_net_mn": 400,
      "capital_leases_mn": 0,
      "cash_like_mn": 20,
      "nwc_current_mn": 500,
      "nwc_prior_mn": 480,
      "lt_operating_assets_current_mn": 2000,
      "lt_operating_assets_prior_mn": 1900,
      "common_dividends_mn": 100,
      "preferred_dividends_mn": 0,
      "minority_dividends_mn": 0,
      "total_equity_mn": 2500,
      "minority_interest_mn": 0,
      "deferred_taxes_mn": 100,
      "assets_current_mn": 2000,
      "assets_prior_mn": 1900,
      "marketable_securities_mn": 20
    },
    "sector_id": "technology_software_and_services"
  }'
```

### Example 2: Full Pricing Analysis

```bash
curl -X POST http://localhost:8000/api/pricing/full-analysis \
  -H "Content-Type: application/json" \
  -d '{
    "financials": { ... },
    "sector_id": "technology_software_and_services",
    "actual_rate_pct": 6.25,
    "facility_tenor": 3,
    "facility_type": "corporate",
    "base_rate_type": "corporate"
  }'
```

### Example 3: Get Base Rates

```bash
curl http://localhost:8000/api/base-rates
```

---

## Support

For issues or questions:
1. Check the error message detail field for specific guidance
2. Review computed_metrics in the response for diagnostic data
3. Consult the engine workings for detailed calculation trails
4. Verify all required financials fields are present
