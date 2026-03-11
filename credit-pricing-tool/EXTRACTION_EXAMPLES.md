# Financial Extraction Pipeline - Examples and Testing

Quick start guide with practical examples for the PDF financial extraction system.

## Quick Start

### Installation

```bash
# Install all dependencies for full features
pip install fastapi pydantic docling pdfplumber PyPDF2 ocrmypdf anthropic uvicorn

# Or minimal installation (fallback extraction only)
pip install fastapi pydantic PyPDF2 uvicorn
```

### Set API Key

```bash
# For AI features
export ANTHROPIC_API_KEY="sk-your-key-here"
```

### Start the API

```bash
cd /path/to/credit-pricing-tool
python -m uvicorn api.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

View API docs: `http://localhost:8000/docs`

## Example 1: Extract Financial Data from a 10-K Filing

### Using cURL

```bash
curl -X POST http://localhost:8000/api/extract/pdf \
  -H "Content-Type: multipart/form-data" \
  -F "file=@acme_10k_2024.pdf"
```

### Using Python

```python
import requests

# Upload and extract
with open("acme_10k_2024.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/extract/pdf",
        files={"file": f}
    )

result = response.json()
print(f"Status: {result['status']}")
print(f"Extracted fields: {result['extracted_fields']}")
print(f"Confidence scores: {result['confidence_scores']}")
print(f"Currency: {result['currency']}")
print(f"Method used: {result['extraction_method']}")
```

### Expected Response

```json
{
  "status": "success",
  "filename": "acme_10k_2024.pdf",
  "extracted_fields": {
    "revenue_mn": 45230.5,
    "ebit_mn": 8945.2,
    "depreciation_mn": 1234.5,
    "amortization_mn": 456.8,
    "interest_expense_mn": 234.5,
    "cash_interest_paid_mn": 245.0,
    "cash_taxes_paid_mn": 1850.3,
    "total_debt_mn": 12500.0,
    "cash_mn": 3450.0,
    "total_equity_mn": 28500.0,
    "cfo_mn": 8234.5,
    "capex_mn": 2345.0,
    "common_dividends_mn": 1500.0
  },
  "confidence_scores": {
    "revenue_mn": 0.98,
    "ebit_mn": 0.92,
    "depreciation_mn": 0.88,
    "amortization_mn": 0.85,
    "interest_expense_mn": 0.90,
    "cash_interest_paid_mn": 0.87,
    "cash_taxes_paid_mn": 0.92,
    "total_debt_mn": 0.95,
    "cash_mn": 0.96,
    "total_equity_mn": 0.94,
    "cfo_mn": 0.89,
    "capex_mn": 0.85,
    "common_dividends_mn": 0.88
  },
  "raw_text_preview": "ACME CORPORATION\n10-K ANNUAL REPORT\nFiscal Year Ended December 31, 2024\n\nPart I - Business\nACME Corporation is a leading provider...",
  "extraction_method": "ai",
  "currency": "USD",
  "fiscal_period": "FY2024",
  "message": "Successfully extracted 13 financial fields from acme_10k_2024.pdf"
}
```

## Example 2: Classify Company Sector

### Using cURL

```bash
curl -X POST http://localhost:8000/api/classify-sector \
  -H "Content-Type: application/json" \
  -d '{
    "business_description": "ACME Corporation develops and markets cloud-based enterprise software solutions for customer relationship management (CRM). Our platforms serve mid-market and large enterprises across all major industries. Founded in 2005, we have grown to serve over 10,000 customers globally with a focus on AI-powered customer analytics."
  }'
```

### Using Python

```python
import requests

description = """
ACME Corporation develops and markets cloud-based enterprise software
solutions for customer relationship management (CRM). Our platforms serve
mid-market and large enterprises across all major industries. Founded in 2005,
we have grown to serve over 10,000 customers globally with a focus on
AI-powered customer analytics.
"""

response = requests.post(
    "http://localhost:8000/api/classify-sector",
    json={"business_description": description}
)

result = response.json()
print(f"S&P Sector: {result['sp_sector']}")
print(f"Moody's Sector: {result['moodys_sector']}")
print(f"Confidence: {result['confidence']:.0%}")
print(f"Reasoning: {result['reasoning']}")
```

### Expected Response

```json
{
  "sp_sector": "technology_software_and_services",
  "moodys_sector": "software",
  "confidence": 0.95,
  "reasoning": "Clear enterprise software/cloud CRM business model with strong AI focus. Typical SaaS characteristics with focus on customer analytics and mid-market to enterprise customer base.",
  "method": "ai"
}
```

## Example 3: Direct Python Usage (No API)

### Extract and Analyze a PDF

```python
import os
from extraction import (
    extract_text_from_pdf,
    extract_tables_from_pdf,
    map_financials_with_ai,
    classify_sector_with_ai
)

pdf_path = "company_financial_statement.pdf"
api_key = os.getenv("ANTHROPIC_API_KEY")

# Step 1: Extract text and tables
print("Extracting text from PDF...")
text = extract_text_from_pdf(pdf_path)
print(f"  Extracted {len(text):,} characters")

print("Extracting tables...")
tables = extract_tables_from_pdf(pdf_path)
print(f"  Found {len(tables)} tables")

# Step 2: Extract financial fields
print("Mapping financial fields...")
financial = map_financials_with_ai(text, tables, api_key)

print(f"  Fields extracted: {len(financial['fields'])}")
print(f"  Average confidence: {sum(financial['confidence'].values()) / len(financial['confidence']):.1%}")
print(f"  Currency: {financial['currency']}")

# Step 3: Print results
print("\nExtracted Financial Data:")
for field, value in sorted(financial['fields'].items()):
    conf = financial['confidence'].get(field, 0)
    print(f"  {field}: ${value:,.1f}M (confidence: {conf:.0%})")

# Step 4: Classify sector
print("\nClassifying sector...")
business_text = text[:2000]  # Use first part describing business
sector = classify_sector_with_ai(business_text, api_key)

print(f"  S&P Sector: {sector['sp_sector']}")
print(f"  Moody's Sector: {sector['moodys_sector']}")
print(f"  Confidence: {sector['confidence']:.0%}")
print(f"  Reasoning: {sector['reasoning']}")
```

## Example 4: Batch Processing Multiple PDFs

```python
import os
import glob
import json
from pathlib import Path
from extraction import (
    extract_text_from_pdf,
    extract_tables_from_pdf,
    map_financials_heuristic,  # Use heuristic for speed
    classify_sector_heuristic
)

pdf_dir = "financials/"
output_file = "extraction_results.json"
results = {}

# Process all PDFs in directory
for pdf_path in glob.glob(os.path.join(pdf_dir, "*.pdf")):
    filename = os.path.basename(pdf_path)
    print(f"Processing {filename}...")

    try:
        # Extract text and tables
        text = extract_text_from_pdf(pdf_path)
        tables = extract_tables_from_pdf(pdf_path)

        # Use heuristic methods (faster, no API calls)
        financial = map_financials_heuristic(text, tables)
        sector = classify_sector_heuristic(text[:2000])

        results[filename] = {
            "status": "success",
            "financial": {
                "fields": financial['fields'],
                "confidence": financial['confidence'],
                "method": financial['method']
            },
            "sector": {
                "sp_sector": sector['sp_sector'],
                "moodys_sector": sector['moodys_sector'],
                "confidence": sector['confidence']
            }
        }

    except Exception as e:
        results[filename] = {
            "status": "error",
            "error": str(e)
        }

# Save results
with open(output_file, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to {output_file}")
print(f"Processed {len(results)} files")
print(f"  Successful: {sum(1 for r in results.values() if r['status'] == 'success')}")
print(f"  Failed: {sum(1 for r in results.values() if r['status'] == 'error')}")
```

## Example 5: Handling Different PDF Types

### Standard Digital PDF (10-K)

```python
from extraction import extract_text_from_pdf

# Standard 10-K filing
text = extract_text_from_pdf("apple_10k_2024.pdf")
# Auto-detects: digital PDF with good text layer
# Extraction method: docling (if available) → pdfplumber → PyPDF2
```

### Scanned Annual Report

```python
from extraction import extract_text_from_pdf

# Scanned annual report (image-based PDF)
text = extract_text_from_pdf("old_company_annual_report.pdf")
# Auto-detects: low text quality → applies OCRmyPDF automatically
# Extraction method: PyPDF2 → OCRmyPDF → re-extract → better results
```

### Mixed Quality PDF (old filing with OCR layer)

```python
from extraction import extract_text_from_pdf

# PDF with both digital and scanned pages
text = extract_text_from_pdf("mixed_quality_filing.pdf")
# Docling intelligently handles mixed quality
# Falls back to pdfplumber if needed
```

## Example 6: Error Handling and Fallbacks

```python
from extraction import (
    extract_text_from_pdf,
    map_financials_with_ai,
    map_financials_heuristic,
    classify_sector_with_ai,
    classify_sector_heuristic
)
import os

pdf_path = "company_10k.pdf"

try:
    # Extract text with automatic fallback
    text = extract_text_from_pdf(pdf_path)
except Exception as e:
    print(f"Failed to extract text: {e}")
    exit(1)

# Try AI extraction first, fall back to heuristic if needed
api_key = os.getenv("ANTHROPIC_API_KEY")

if api_key:
    print("Attempting AI-powered extraction...")
    financial = map_financials_with_ai(text, [], api_key)

    if not financial.get('fields'):
        print("AI extraction returned no fields, using heuristic...")
        financial = map_financials_heuristic(text, [])
else:
    print("No API key, using heuristic extraction...")
    financial = map_financials_heuristic(text, [])

print(f"Extraction method: {financial['method']}")
print(f"Fields found: {len(financial['fields'])}")

# Same pattern for sector classification
if api_key:
    sector = classify_sector_with_ai(text[:2000], api_key)
    if sector['confidence'] < 0.6:
        print("Low confidence from AI, using heuristic...")
        sector = classify_sector_heuristic(text[:2000])
else:
    sector = classify_sector_heuristic(text[:2000])

print(f"Sector: {sector['sp_sector']} (confidence: {sector['confidence']:.0%})")
```

## Example 7: Building a Complete Analysis Pipeline

```python
import os
import json
from datetime import datetime
from extraction import (
    extract_text_from_pdf,
    extract_tables_from_pdf,
    map_financials_with_ai,
    classify_sector_with_ai
)

class FinancialAnalyzer:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    def analyze_pdf(self, pdf_path):
        """Complete analysis of a financial PDF."""
        result = {
            "file": os.path.basename(pdf_path),
            "timestamp": datetime.now().isoformat(),
            "extraction": None,
            "analysis": None,
            "errors": []
        }

        try:
            # Extract content
            text = extract_text_from_pdf(pdf_path)
            tables = extract_tables_from_pdf(pdf_path)

            result["extraction"] = {
                "text_length": len(text),
                "table_count": len(tables)
            }

            # Map financial fields
            financial = map_financials_with_ai(text, tables, self.api_key)

            # Calculate metrics
            metrics = self._calculate_metrics(financial['fields'])

            # Classify sector
            sector = classify_sector_with_ai(text[:2000], self.api_key)

            result["analysis"] = {
                "financial": {
                    "fields": financial['fields'],
                    "confidence_avg": sum(financial['confidence'].values()) / len(financial['confidence']) if financial['confidence'] else 0,
                    "method": financial['method'],
                    "currency": financial.get('currency'),
                    "fiscal_period": financial.get('fiscal_period')
                },
                "metrics": metrics,
                "sector": {
                    "sp": sector['sp_sector'],
                    "moodys": sector['moodys_sector'],
                    "confidence": sector['confidence']
                }
            }

        except Exception as e:
            result["errors"].append(str(e))

        return result

    def _calculate_metrics(self, fields):
        """Calculate derived financial metrics."""
        metrics = {}

        # Debt metrics
        if "total_debt_mn" in fields and "cash_mn" in fields:
            metrics["net_debt_mn"] = fields["total_debt_mn"] - fields["cash_mn"]

        # EBITDA
        if all(k in fields for k in ["ebit_mn", "depreciation_mn", "amortization_mn"]):
            metrics["ebitda_mn"] = (
                fields["ebit_mn"] +
                fields["depreciation_mn"] +
                fields["amortization_mn"]
            )

        # Leverage
        if "net_debt_mn" in metrics and "ebitda_mn" in metrics and metrics["ebitda_mn"] > 0:
            metrics["net_debt_to_ebitda"] = metrics["net_debt_mn"] / metrics["ebitda_mn"]

        # Free cash flow
        if all(k in fields for k in ["cfo_mn", "capex_mn"]):
            metrics["free_cash_flow_mn"] = fields["cfo_mn"] - fields["capex_mn"]

        return metrics


# Usage
analyzer = FinancialAnalyzer()
result = analyzer.analyze_pdf("company_10k.pdf")

print(json.dumps(result, indent=2))
```

## Debugging and Validation

### Check Extraction Quality

```python
from extraction import extract_text_from_pdf

text = extract_text_from_pdf("test.pdf")

# Check text quality
stats = {
    "total_chars": len(text),
    "word_count": len(text.split()),
    "line_count": len(text.split("\n")),
    "has_numbers": any(c.isdigit() for c in text),
    "has_financial_keywords": any(
        kw in text.lower()
        for kw in ["revenue", "ebit", "cash", "debt", "assets", "equity"]
    )
}

print(f"Text Quality: {stats}")

# If word_count is very low, PDF might be scanned
if stats['word_count'] < 100 and len(text) > 10000:
    print("WARNING: PDF appears to be scanned, OCR may help")
```

### Validate Financial Data

```python
from extraction import map_financials_heuristic

financial = map_financials_heuristic(text, [])

# Sanity checks
issues = []

if 'revenue_mn' in financial['fields'] and 'ebit_mn' in financial['fields']:
    if financial['fields']['ebit_mn'] > financial['fields']['revenue_mn']:
        issues.append("EBIT > Revenue (likely error)")

if 'total_debt_mn' in financial['fields']:
    if financial['fields']['total_debt_mn'] > 1_000_000:
        issues.append("Debt > 1 trillion (likely not in millions)")

if issues:
    print("Data Validation Issues:")
    for issue in issues:
        print(f"  - {issue}")
```

## Testing the API

### Using HTTPie

```bash
# Test PDF extraction
http --form POST http://localhost:8000/api/extract/pdf \
  file@test_10k.pdf

# Test sector classification
http POST http://localhost:8000/api/classify-sector \
  business_description="Software company specializing in cloud CRM"
```

### Using Postman

1. Create a new POST request to `http://localhost:8000/api/extract/pdf`
2. Go to Body → form-data
3. Add key "file" → select PDF file
4. Send

Or for sector classification:
1. Create POST to `http://localhost:8000/api/classify-sector`
2. Body → raw JSON:
   ```json
   {
     "business_description": "Your business description here"
   }
   ```

## Performance Profiling

```python
import time
from extraction import extract_text_from_pdf, extract_tables_from_pdf

pdf_path = "large_10k.pdf"

# Profile text extraction
start = time.time()
text = extract_text_from_pdf(pdf_path)
text_time = time.time() - start

# Profile table extraction
start = time.time()
tables = extract_tables_from_pdf(pdf_path)
table_time = time.time() - start

print(f"Text extraction: {text_time:.2f}s ({len(text):,} chars)")
print(f"Table extraction: {table_time:.2f}s ({len(tables)} tables)")
print(f"Text speed: {len(text) / text_time / 1024 / 1024:.1f} MB/s")
```

## Troubleshooting Guide

### "All PDF text extraction methods failed"
**Solution:** Install at least one PDF library:
```bash
pip install pdfplumber  # Recommended
# or
pip install PyPDF2  # Minimal
# or
pip install docling  # Best quality
```

### "ocrmypdf not installed"
**Solution:** Install OCRmyPDF for scanned PDFs:
```bash
pip install ocrmypdf
```

### "anthropic not installed"
**Solution:** For AI features:
```bash
pip install anthropic
```

### No financial fields extracted
**Checklist:**
- Is the PDF a financial statement? (10-K, annual report, etc.)
- Is the PDF in English?
- Try with heuristic: `map_financials_heuristic(text, tables)`
- Check raw text: `print(text[:1000])`

### Low confidence scores
**Possible causes:**
- Scanned or low-quality PDF → ensure OCR was applied
- Non-standard layout → try manual review
- Wrong currency → set conversion if needed
- Old document format → heuristic may work better

---

For more details, see [EXTRACTION_PIPELINE.md](EXTRACTION_PIPELINE.md)
