# Credit Pricing Tool - Quick Start Guide

## Installation & Setup (5 minutes)

### Step 1: Install Dependencies
```bash
cd /sessions/funny-tender-gates/mnt/mllew/OneDrive/Desktop/Building/credit-pricing-tool
pip install -r requirements.txt
```

### Step 2: Start the Server
```bash
uvicorn api.main:app --reload
```

### Step 3: Verify It's Working
```bash
curl http://localhost:8000/health
```

## Interactive API Documentation

Visit these endpoints while the server is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## First Request: Rate a Company

```bash
curl -X POST http://localhost:8000/api/rate \
  -H "Content-Type: application/json" \
  -d '{
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
    "sector_id": "technology_software_and_services"
  }'
```

Expected response includes: sp_rating, moodys_rating, blended_rating, and metrics.

## Available Endpoints

1. **POST /api/rate** - Rate a company (S&P + Moody's)
2. **POST /api/pricing/lookup** - Look up spreads for rating+tenor
3. **POST /api/pricing/full-analysis** - Complete pricing analysis
4. **GET /api/base-rates** - NZ bank rates
5. **POST /api/extract/pdf** - Extract data from PDF (stub)
6. **GET /health** - Health check

## Documentation

- **API_DOCUMENTATION.md**: Complete API reference
- **BACKEND_BUILD_SUMMARY.txt**: Technical details
- Interactive docs: http://localhost:8000/docs

---

Start the server and visit http://localhost:8000/docs to explore all endpoints.
