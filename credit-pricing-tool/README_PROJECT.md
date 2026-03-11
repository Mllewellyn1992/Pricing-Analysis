# Credit Pricing Tool

A dual-engine credit rating and pricing system integrating Moody's and S&P methodologies for New Zealand financial institutions.

## Project Structure

```
credit-pricing-tool/
├── api/                       # Vercel Python serverless functions
│   ├── rate/                  # Rating endpoints (S&P, Moody's, blended)
│   ├── pricing/               # Pricing matrix lookup
│   ├── extract/               # PDF/Excel financial data extraction
│   └── scrape/                # NZ base rate scraper
├── engines/                   # Core rating engines (NO Streamlit)
│   ├── moodys_engine.py       # Moody's methodology (generic YAML scorer)
│   ├── sp_engine.py           # S&P methodology (complete implementation)
│   ├── sp_defaults.py         # Industry-level defaults for quant-only mode
│   ├── sector_mapper.py       # AI-driven sector mapping [TODO]
│   ├── blender.py             # AI rating blending [TODO]
│   └── configs/
│       ├── moodys/            # All Moody's YAML configs
│       └── sp/                # All S&P YAML configs
├── extraction/                # Financial data extraction
│   ├── pdf_extract.py         # Docling-based PDF extraction [TODO]
│   ├── excel_extract.py       # Excel/CSV extraction [TODO]
│   └── field_mapper.py        # Maps extracted labels to engine fields [TODO]
├── tests/
│   ├── test_sp.py             # S&P engine tests (PASSING)
│   ├── test_moodys.py         # Moody's engine tests [TODO]
│   └── test_harness.py        # Cross-engine comparison [TODO]
├── src/                       # React frontend [FUTURE]
├── requirements.txt           # Python dependencies
└── package.json               # Node/frontend config
```

## Engines

### S&P Engine (COMPLETE)

**File:** `engines/sp_engine.py`

**Main Function:**
```python
def rate_company_sp(
    financials: dict,
    sector_id: str,
    cyclicality: int = 3,
    competitive_risk: int = 3,
    country_risk: int = 2,
    quant_only: bool = True,
    ...additional qualitative inputs...
) -> dict:
```

**Financials Dict Keys:**
- `revenue_mn`, `ebit_mn`, `depreciation_mn`, `amortization_mn`
- `interest_expense_mn`, `cash_interest_paid_mn`, `cash_taxes_paid_mn`
- `total_debt_mn`, `cash_mn`, `avg_capital_mn`
- `cfo_mn`, `capex_mn`, `dividends_paid_mn`, `share_buybacks_mn`

**Returns:**
```python
{
    "anchor_rating": "BBB",           # e.g. AAA, AA, A, BBB, BB, B, CCC
    "final_rating": "BBB-",           # After modifiers and caps
    "business_risk_score": 3,         # 1-6
    "financial_risk_score": 3,        # 1-6
    "computed_ratios": {...},         # All intermediate metrics
    "factor_scores": [...],           # Competitive position breakdown
    "workings": {...}                 # Full audit trail
}
```

**Key Features:**
- Quant-only mode: Uses industry defaults for cyclicality/competitive_risk
- Computes 7 key ratios: FFO/Debt, Debt/EBITDA, coverage, margins, ROC
- Industry risk matrix: Maps cyclicality x competitive_risk → industry_risk (1-6)
- CICRA matrix: Maps industry_risk x country_risk → corporate risk (1-6)
- Business risk = average(CICRA, competitive_position)
- Financial risk = max(FFO/Debt band, Debt/EBITDA band)
- Anchor rating from business_risk + financial_risk
- Modifiers for financial policy, capital structure, diversification, M&G
- Liquidity cap applied at the end

**Sector IDs (available in configs/sp/sector_specific/):**
- `technology_software_and_services` (default cyclicality 2, competitive_risk 2)
- `regulated_utilities` (1, 2)
- `metals_production_and_processing` (5, 4)
- `mining` (5, 4)
- And 37+ others from S&P methodology

**Tested:** YES - All 4 test cases pass

### Moody's Engine (COMPLETE - Standalone)

**File:** `engines/moodys_engine.py`

**Main Function:**
```python
def score_company(
    methodology_id: str,
    metrics: Dict[str, Any],
    config_dir: Path = CONFIG_DIR,
) -> Dict[str, Any]:
```

**Returns:**
```python
{
    "methodology_id": "building_materials",
    "methodology_name": "Building Materials",
    "composite_score": 8.5,
    "anchor_rating": "Baa2",
    "factor_scores": [...],
    "subfactor_scores": [...]
}
```

**Available Methodologies (configs/moodys/):**
- `building_materials`
- `aerospace_defense`
- `chemicals`
- `consumer_packaged_goods`
- `environmental_services_waste_management`
- And 30+ others

**Status:** Tested via original codebase; awaiting wrapper + tests

## Configs

### Moody's Configs
All methodology YAMLs copied from source:
`engines/configs/moodys/<methodology_id>.yaml`

Each YAML defines:
- Factors (20% weight)
  - Subfactors (80% cumulative)
    - Metrics + grids (numeric or qualitative)
    - Special cases (conditional scoring)
- Score-to-rating mapping (default 1.0-99.9 scale to Aaa-Ca)

### S&P Configs
All sector + corporate configs copied from source:
- `engines/configs/sp/corporate_method.yaml` - CICRA matrix, anchor ratings, modifiers
- `engines/configs/sp/industry_risk.yaml` - 6x6 cyclicality x competitive_risk matrix
- `engines/configs/sp/liquidity.yaml` - Liquidity descriptors & caps
- `engines/configs/sp/mg_modifier.yaml` - Management & Governance scoring
- `engines/configs/sp/sector_specific/<sector_id>.yaml` - Competitive position factors

Each sector YAML defines:
- Competitive advantage (strong, average, weak scales)
- Scale, scope, diversity (numeric bands)
- Operating efficiency (performance bands)

## Testing

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run S&P Tests
```bash
python tests/test_sp.py
```

**Current Status:** 4/4 tests PASSING
- Healthy Software Company → BBB
- Leveraged Mining Company → BBB (with higher financial risk)
- Strong Utility → BBB (lower business risk)
- Sector Consistency → Utilities rate >= Metals on same metrics

### Run Moody's Tests
```bash
python tests/test_moodys.py  # [TODO - to be created]
```

### Run Cross-Engine Tests
```bash
python tests/test_harness.py  # [TODO - to be created]
```

## API Endpoints (To Be Built)

### Rating Endpoints

**POST /api/rate/sp**
```json
{
  "financials": {...},
  "sector_id": "technology_software_and_services",
  "cyclicality": 2,
  "quant_only": true
}
```
Returns: S&P rating + workings

**POST /api/rate/moodys**
```json
{
  "financials": {...},
  "methodology_id": "building_materials"
}
```
Returns: Moody's rating + factor breakdown

**POST /api/rate/blend**
Combines S&P and Moody's using Claude AI + ensemble logic

### Other Endpoints

**POST /api/extract/pdf** - Extract financials from PDF statements
**POST /api/extract/excel** - Upload Excel model
**GET /api/pricing/lookup** - Get spread for rating + sector
**GET /api/scrape/nz-base-rates** - Fetch current NZ OCR + bank rates

## Dependencies

```
pyyaml>=6.0          # Config parsing
pandas>=2.0          # Data manipulation
pyarrow>=14.0        # Efficient storage
docling>=2.0         # PDF extraction
anthropic>=0.40.0    # Claude API for blending/extraction
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test S&P Engine
```bash
python tests/test_sp.py
```

### 3. Rate a Company
```python
from engines import rate_company_sp

financials = {
    "revenue_mn": 50.0,
    "ebit_mn": 12.0,
    "depreciation_mn": 3.0,
    "amortization_mn": 2.0,
    "interest_expense_mn": 1.5,
    "cash_interest_paid_mn": 1.2,
    "cash_taxes_paid_mn": 2.8,
    "total_debt_mn": 20.0,
    "cash_mn": 8.0,
    "avg_capital_mn": 35.0,
    "cfo_mn": 15.0,
    "capex_mn": 4.0,
    "dividends_paid_mn": 2.0,
    "share_buybacks_mn": 0.0,
}

result = rate_company_sp(
    financials,
    sector_id="technology_software_and_services",
    quant_only=True
)

print(f"Rating: {result['final_rating']}")
print(f"Ratios: {result['computed_ratios']}")
```

### 4. Score with Moody's
```python
from engines import score_company_moodys

metrics = {
    "revenue_usd_billion": 3.5,
    "operating_margin_pct": 15.0,
    "debt_book_cap_pct": 45.0,
    "debt_ebitda_x": 3.0,
    "business_profile_band": "Baa",
}

result = score_company_moodys("building_materials", metrics)
print(f"Rating: {result['anchor_rating']}")
```

## Architecture Notes

### Why No Streamlit?
- Streamlit is UI-first; this tool is API-first
- Endpoints can be deployed to Vercel as serverless functions
- Decouples rating logic from UI layer
- Better for testing and integration

### Quant-Only Mode
- When `quant_only=True`, qualitative inputs (M&G, modifiers) are skipped
- Uses industry defaults (cyclicality, competitive_risk) from `sp_defaults.py`
- Produces consistent, reproducible ratings from financials alone
- Useful for batch processing, API automation

### Audit Trail
- `rate_company_sp()` returns full `workings` dict
- Includes all intermediate calculations (ratios, scores, matrices)
- Enables transparent credit decisions and regulatory compliance

## TODO

High Priority:
1. Moody's wrapper + tests (moodys_wrapper.py)
2. AI blending engine (blender.py)
3. PDF extraction (extraction/pdf_extract.py)
4. Excel extraction (extraction/excel_extract.py)
5. Pricing matrix lookup API
6. Cross-engine test harness

Medium Priority:
7. React frontend (src/)
8. FastAPI endpoints (api/)
9. NZ base rate scraper
10. Deployment configs (Vercel, env)

Lower Priority:
11. Sector mapper (AI-driven classification)
12. Historical pricing data
13. Sensitivity analysis
14. Peer comparison

## Contact

For questions about the S&P or Moody's methodologies, refer to:
- S&P config schema: `engines/configs/sp/README_SP.md` [TODO]
- Moody's config schema: `engines/configs/moodys/README_MOODYS.md` [TODO]
