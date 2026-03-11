# Financial Extraction Pipeline

Production-quality PDF financial data extraction system with multiple fallback strategies.

## Overview

The extraction pipeline extracts financial data from PDF financial statements through a multi-stage process:

1. **PDF Text Extraction** - Extracts text with intelligent format detection
2. **Table Extraction** - Identifies and extracts structured tables
3. **Financial Field Mapping** - Maps extracted data to standard financial metrics
4. **Sector Classification** - Classifies companies into S&P and Moody's sector taxonomies

## Components

### 1. PDF Extractor (`extraction/pdf_extractor.py`)

Extracts text and tables from PDFs with fallback strategies.

#### Features
- **Multi-strategy text extraction:**
  1. Docling (advanced layout understanding) - if available
  2. pdfplumber (standard PDF library) - fallback
  3. PyPDF2 (basic PDF library) - final fallback
  4. OCRmyPDF for scanned documents - automatic detection and retry

- **Intelligent scanned PDF detection** - Detects low-quality text and automatically applies OCR

- **Graceful degradation** - Works with any of the three PDF libraries

#### API

```python
from extraction.pdf_extractor import extract_text_from_pdf, extract_tables_from_pdf

# Extract text from PDF
text = extract_text_from_pdf("/path/to/document.pdf")

# Extract tables
tables = extract_tables_from_pdf("/path/to/document.pdf")
# Returns: [
#     {
#         "columns": ["Col1", "Col2", ...],
#         "rows": [["val1", "val2", ...], ...],
#         "caption": "Table title"
#     },
#     ...
# ]
```

#### Supported Scenarios
- Multi-page financial statements
- Complex layouts with sidebars, callouts, footnotes
- Scanned PDFs (automatic OCR with text layer addition)
- Mixed digital and scanned content

### 2. Financial Mapper (`extraction/financial_mapper.py`)

Maps extracted text and tables to standard financial statement fields.

#### Extracted Fields

Income Statement:
- `revenue_mn` - Total revenue
- `ebit_mn` - Operating income/EBIT
- `depreciation_mn` - Depreciation expense
- `amortization_mn` - Amortization expense
- `interest_expense_mn` - Interest expense
- `cash_interest_paid_mn` - Cash interest paid
- `cash_taxes_paid_mn` - Cash taxes paid

Balance Sheet:
- `total_debt_mn` - Total debt (or components)
  - `st_debt_mn` - Short-term debt
  - `cpltd_mn` - Current portion of long-term debt
  - `lt_debt_net_mn` - Long-term debt net
  - `capital_leases_mn` - Capital leases
- `cash_mn` - Cash and cash equivalents
- `cash_like_mn` - Cash-like securities
- `total_equity_mn` - Total shareholders' equity
- `minority_interest_mn` - Minority interest
- `deferred_taxes_mn` - Deferred tax assets/liabilities
- `assets_current_mn` - Total current assets
- `assets_prior_mn` - Total assets (prior period)

Cash Flow Statement:
- `cfo_mn` - Cash flow from operations
- `capex_mn` - Capital expenditures
- `common_dividends_mn` - Common dividends paid
- `preferred_dividends_mn` - Preferred dividends paid

Working Capital & Assets:
- `nwc_current_mn` - Net working capital (current)
- `nwc_prior_mn` - Net working capital (prior)
- `lt_operating_assets_current_mn` - Long-term operating assets
- `lt_operating_assets_prior_mn` - Long-term operating assets (prior)
- `avg_capital_mn` - Average capital invested

#### Two-Strategy Extraction

**AI-Powered (`map_financials_with_ai`)**
- Uses Claude API for intelligent field identification
- Understands context and variations in financial statement format
- Detects currency and fiscal period
- Provides confidence scores (0.0-1.0) per field
- Handles non-standard layouts and terminology

**Heuristic (`map_financials_heuristic`)**
- Regex and pattern-based extraction
- Works without API access
- Uses common financial statement labels
- Lower confidence scores but more predictable
- Useful as fallback or for batch processing

#### API

```python
from extraction.financial_mapper import (
    map_financials_with_ai,
    map_financials_heuristic
)

# AI-powered extraction
result = map_financials_with_ai(raw_text, tables, api_key="sk-...")
# Returns: {
#     "fields": {
#         "revenue_mn": 1234.5,
#         "ebit_mn": 234.5,
#         ...
#     },
#     "confidence": {
#         "revenue_mn": 0.95,
#         "ebit_mn": 0.80,
#         ...
#     },
#     "currency": "USD",
#     "fiscal_period": "FY2024",
#     "errors": [],
#     "method": "ai"
# }

# Heuristic extraction
result = map_financials_heuristic(raw_text, tables)
```

#### Confidence Scoring

- **0.95+** - Exact match in financial statements
- **0.80-0.94** - High confidence, slight ambiguity
- **0.60-0.79** - Reasonable confidence, calculated/inferred
- **0.40-0.59** - Low confidence, uncertain
- **Below 0.40** - Excluded from results

### 3. Sector Classifier (`extraction/sector_classifier.py`)

Classifies companies into standardized sector taxonomies.

#### Supported Taxonomies

**S&P Sectors** (40+):
- technology_software_and_services
- mining, regulated_utilities
- retail_and_restaurants
- aerospace_and_defense
- pharmaceuticals
- healthcare_services
- telecommunications
- media_and_entertainment
- oil_and_gas_exploration_and_production
- [and 30+ more...]

**Moody's Sectors** (45+):
- software, steel, telecommunications
- retail_and_apparel, construction
- pharmaceuticals, aerospace_defense
- integrated_oil_gas
- media, metals_mining
- [and 35+ more...]

#### Two-Strategy Classification

**AI-Powered (`classify_sector_with_ai`)**
- Uses Claude API for intelligent classification
- Understands company context and nuances
- Returns confidence score and reasoning
- Handles diversified companies well

**Heuristic (`classify_sector_heuristic`)**
- Keyword-based classification
- No API required
- Uses 50+ industry keywords
- Falls back to generic classification if no matches

#### API

```python
from extraction.sector_classifier import (
    classify_sector_with_ai,
    classify_sector_heuristic
)

description = "We develop cloud-based software solutions for enterprise customers..."

# AI classification
result = classify_sector_with_ai(description, api_key="sk-...")
# Returns: {
#     "sp_sector": "technology_software_and_services",
#     "moodys_sector": "software",
#     "confidence": 0.92,
#     "reasoning": "Clear software/cloud business model",
#     "method": "ai"
# }

# Heuristic classification
result = classify_sector_heuristic(description)
```

## API Endpoints

### POST /api/extract/pdf

Extract financial data from a PDF document.

**Request:**
```
Content-Type: multipart/form-data

file: <PDF file>
```

**Response (200):**
```json
{
  "status": "success",
  "filename": "acme_10k_2024.pdf",
  "extracted_fields": {
    "revenue_mn": 1234.5,
    "ebit_mn": 234.5,
    "total_debt_mn": 500.0,
    "cash_mn": 100.0
  },
  "confidence_scores": {
    "revenue_mn": 0.95,
    "ebit_mn": 0.85,
    "total_debt_mn": 0.90,
    "cash_mn": 0.88
  },
  "raw_text_preview": "ACME Corporation 10-K Filing FY2024...",
  "extraction_method": "ai",
  "currency": "USD",
  "fiscal_period": "FY2024",
  "message": "Successfully extracted 4 financial fields from acme_10k_2024.pdf"
}
```

**Error Responses:**
- `400` - File missing or not PDF
- `422` - Text extraction failed
- `500` - Unexpected error

### POST /api/classify-sector

Classify company sector.

**Request:**
```json
{
  "business_description": "Global software company providing cloud-based CRM solutions..."
}
```

**Response (200):**
```json
{
  "sp_sector": "technology_software_and_services",
  "moodys_sector": "software",
  "confidence": 0.92,
  "reasoning": "Clear software/cloud business model with enterprise focus",
  "method": "ai"
}
```

**Error Responses:**
- `400` - Missing or empty business_description
- `500` - Classification failed

## Configuration

### Environment Variables

```bash
# Anthropic API key (for AI features)
export ANTHROPIC_API_KEY="sk-..."

# Optional: Log level
export LOG_LEVEL="INFO"
```

### Library Dependencies

**Required:**
- `fastapi` - API framework
- `pydantic` - Data validation

**Recommended (for best extraction):**
- `docling` - Advanced PDF parsing
- `anthropic` - Claude API access

**Optional (fallbacks):**
- `pdfplumber` - Standard PDF library
- `PyPDF2` - Basic PDF library
- `ocrmypdf` - OCR for scanned documents

**Installation:**
```bash
# All features (recommended)
pip install fastapi pydantic docling pdfplumber PyPDF2 ocrmypdf anthropic

# Minimal (without AI and advanced features)
pip install fastapi pydantic PyPDF2
```

## Usage Examples

### Complete PDF Processing

```python
from extraction.pdf_extractor import extract_text_from_pdf, extract_tables_from_pdf
from extraction.financial_mapper import map_financials_with_ai
from extraction.sector_classifier import classify_sector_with_ai
import os

pdf_path = "company_10k.pdf"
api_key = os.getenv("ANTHROPIC_API_KEY")

# Extract text and tables
text = extract_text_from_pdf(pdf_path)
tables = extract_tables_from_pdf(pdf_path)

# Extract financial fields
financial_data = map_financials_with_ai(text, tables, api_key)

# Classify sector
business_section = text[:1000]  # Use relevant section
sector_info = classify_sector_with_ai(business_section, api_key)

# Process results
print(f"Revenue: ${financial_data['fields'].get('revenue_mn', 'N/A')}M")
print(f"Sector: {sector_info['sp_sector']}")
print(f"Confidence: {sector_info['confidence']:.0%}")
```

### Batch Processing with Heuristics

```python
import os
import glob
from extraction import (
    extract_text_from_pdf,
    extract_tables_from_pdf,
    map_financials_heuristic,
    classify_sector_heuristic
)

pdf_dir = "pdfs/"
results = []

for pdf_path in glob.glob(os.path.join(pdf_dir, "*.pdf")):
    try:
        text = extract_text_from_pdf(pdf_path)
        tables = extract_tables_from_pdf(pdf_path)

        # Use heuristics (no API calls)
        financial = map_financials_heuristic(text, tables)
        sector = classify_sector_heuristic(text[:2000])

        results.append({
            "file": os.path.basename(pdf_path),
            "financial": financial,
            "sector": sector
        })
    except Exception as e:
        print(f"Failed to process {pdf_path}: {e}")

# Save results
import json
with open("extraction_results.json", "w") as f:
    json.dump(results, f, indent=2)
```

## Error Handling

The pipeline handles errors gracefully:

1. **PDF Extraction Failure** → Tries next available library
2. **Scanned PDF Detection** → Automatically applies OCR
3. **AI Field Extraction Failure** → Falls back to heuristic
4. **Low AI Confidence** → Validates against heuristic
5. **API Unavailable** → Uses heuristic methods

## Performance Considerations

- **Docling extraction**: ~2-5 seconds per page (best quality)
- **pdfplumber extraction**: ~0.5-1 second per page (good balance)
- **PyPDF2 extraction**: ~0.1-0.3 seconds per page (fastest)
- **OCRmyPDF**: ~5-15 seconds per page (depends on quality)
- **Claude API call**: ~2-5 seconds (includes network latency)

## Quality Metrics

Typical extraction performance:

| Metric | AI | Heuristic |
|--------|--|---------|
| Fields found (avg) | 15-22 | 8-12 |
| Confidence (avg) | 0.80+ | 0.65-0.75 |
| Processing time | 5-10s | <1s |
| Handles complex layouts | Yes | Limited |
| Requires API | Yes | No |

## Troubleshooting

### No text extracted
- Install docling: `pip install docling`
- Verify PDF is readable (not corrupted)
- Try manual OCR: `pip install ocrmypdf`

### Low confidence scores
- Ensure PDF is clean (not degraded copy)
- Check if PDF is scanned (should auto-detect)
- Try with larger text sample

### Missing financial fields
- Verify PDF contains financial statements
- Check for multi-currency issues
- Ensure field names match common variations

### API errors
- Verify `ANTHROPIC_API_KEY` is set
- Check API rate limits
- Ensure network connectivity

## Architecture Decisions

1. **Fallback Strategy** - Multiple PDF libraries ensure compatibility
2. **Confidence Scoring** - Helps downstream systems assess data quality
3. **Separate AI/Heuristic** - Allows flexibility in deployment
4. **Standard Field Names** - Maps to common credit analysis metrics
5. **Sector Taxonomies** - Supports both S&P and Moody's frameworks

## Future Enhancements

- Multi-currency automatic conversion to NZD
- Ledger entry extraction (general ledger)
- Cash flow statement reconstruction
- Balance sheet period matching
- Segment financial data extraction
- Custom field templates
