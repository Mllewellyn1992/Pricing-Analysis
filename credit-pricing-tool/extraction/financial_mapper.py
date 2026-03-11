"""
Financial field mapping and extraction.

Provides two approaches:
1. AI-powered mapping using Claude API for intelligent field extraction
2. Heuristic/regex-based fallback for when API is unavailable

Extracts standard financial statement fields:
- Income statement: revenue, EBIT, depreciation, amortization, interest, taxes
- Cash flow: CFO, CAPEX, dividends
- Balance sheet: debt, cash, equity, assets, NWC
- Calculated metrics: average capital, adjusted EBITDA, etc.
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Standard financial fields we try to extract
FINANCIAL_FIELDS = {
    "revenue_mn": "Total revenue or net sales (millions)",
    "ebit_mn": "EBIT or operating income (millions)",
    "depreciation_mn": "Depreciation (millions)",
    "amortization_mn": "Amortization (millions)",
    "interest_expense_mn": "Interest expense (millions)",
    "cash_interest_paid_mn": "Cash interest paid (millions)",
    "cash_taxes_paid_mn": "Cash taxes paid (millions)",
    "total_debt_mn": "Total debt (millions)",
    "st_debt_mn": "Short-term debt (millions)",
    "cpltd_mn": "Current portion of long-term debt (millions)",
    "lt_debt_net_mn": "Long-term debt net (millions)",
    "capital_leases_mn": "Capital leases (millions)",
    "cash_mn": "Cash and equivalents (millions)",
    "cash_like_mn": "Cash-like securities (millions)",
    "total_equity_mn": "Total equity (millions)",
    "minority_interest_mn": "Minority interest (millions)",
    "deferred_taxes_mn": "Deferred taxes (millions)",
    "cfo_mn": "Cash flow from operations (millions)",
    "capex_mn": "Capital expenditures (millions)",
    "common_dividends_mn": "Common dividends paid (millions)",
    "preferred_dividends_mn": "Preferred dividends paid (millions)",
    "nwc_current_mn": "Net working capital - current period (millions)",
    "nwc_prior_mn": "Net working capital - prior period (millions)",
    "lt_operating_assets_current_mn": "Long-term operating assets - current (millions)",
    "lt_operating_assets_prior_mn": "Long-term operating assets - prior (millions)",
    "assets_current_mn": "Total assets - current period (millions)",
    "assets_prior_mn": "Total assets - prior period (millions)",
    "avg_capital_mn": "Average capital invested (millions)",
}


def map_financials_with_ai(
    raw_text: str,
    tables: List[Dict[str, Any]],
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Use Claude API to intelligently extract financial fields from documents.

    Analyzes both raw text and structured table data to identify and extract
    financial fields. Returns confidence scores for each field.

    Args:
        raw_text: Extracted text from PDF
        tables: Extracted tables from PDF (list of dicts with columns/rows/caption)
        api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)

    Returns:
        Dictionary with structure:
        {
            "fields": {
                "revenue_mn": 1234.5,
                "ebit_mn": 234.5,
                ...
            },
            "confidence": {
                "revenue_mn": 0.95,
                "ebit_mn": 0.80,
                ...
            },
            "errors": ["field_name: error reason", ...],
            "method": "ai"
        }
    """
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic library not installed; falling back to heuristic")
        return map_financials_heuristic(raw_text, tables)

    import os
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; falling back to heuristic")
        return map_financials_heuristic(raw_text, tables)

    client = anthropic.Anthropic(api_key=api_key)

    # Build table context
    table_text = ""
    if tables:
        table_text = "\n\nExtracted Tables:\n"
        for i, table in enumerate(tables[:5], 1):  # Limit to first 5 tables
            caption = table.get("caption", f"Table {i}")
            columns = table.get("columns", [])
            rows = table.get("rows", [])[:10]  # Limit rows

            table_text += f"\n{caption}:\n"
            if columns:
                table_text += " | ".join(columns) + "\n"
                table_text += "-" * 60 + "\n"
            for row in rows:
                table_text += " | ".join(row) + "\n"

    # Build the extraction prompt
    fields_str = "\n".join(
        f"- {field}: {desc}" for field, desc in FINANCIAL_FIELDS.items()
    )

    prompt = f"""You are a financial data extraction expert. Extract financial data from the following financial statement.

DOCUMENT TEXT:
{raw_text[:8000]}
{table_text}

TASK:
Extract the following financial fields from the document above. Only extract values that you can identify with reasonable confidence. Report values in MILLIONS of the local currency (note the currency if found).

FIELDS TO EXTRACT:
{fields_str}

RESPONSE FORMAT:
Return ONLY a valid JSON object with this structure (no other text):
{{
  "fields": {{
    "field_name": number_in_millions,
    "another_field": null
  }},
  "confidence": {{
    "field_name": 0.0_to_1.0,
    "another_field": null
  }},
  "currency": "USD|NZD|GBP|etc or UNKNOWN",
  "fiscal_period": "FY2024|Q1 2024|etc or UNKNOWN",
  "notes": "any important notes about the extraction"
}}

CONFIDENCE SCORING:
- 0.95+: Found exact value in financial statements
- 0.80-0.94: High confidence, but slight ambiguity
- 0.60-0.79: Reasonable confidence, calculated or inferred
- 0.40-0.59: Low confidence, uncertain
- Below 0.40: Don't include in response (use null instead)

CRITICAL RULES:
1. Only include fields you are confident about (confidence >= 0.40)
2. Return null for fields you cannot find
3. All numbers must be in MILLIONS
4. If a field is 0 or missing, return null, not 0
5. Validate debt components sum reasonably if multiple debt fields found
"""

    try:
        logger.debug("Calling Claude API for financial field extraction")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = response.content[0].text

        # Parse JSON response
        json_str = response_text
        # Handle potential markdown code block formatting
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        result = json.loads(json_str.strip())

        # Validate and clean response
        fields = result.get("fields", {})
        confidence = result.get("confidence", {})

        # Remove None values
        fields = {k: v for k, v in fields.items() if v is not None}
        confidence = {k: v for k, v in confidence.items() if confidence.get(k) is not None}

        # Validate numbers are in millions (sanity check for very large outliers)
        errors = []
        for field, value in list(fields.items()):
            if not isinstance(value, (int, float)):
                try:
                    fields[field] = float(value)
                except (ValueError, TypeError):
                    errors.append(f"{field}: could not convert to number")
                    del fields[field]
                    if field in confidence:
                        del confidence[field]
            elif value > 1_000_000:  # Likely not in millions
                logger.warning(f"{field} value {value} seems too large for millions")

        return {
            "fields": fields,
            "confidence": confidence,
            "currency": result.get("currency", "UNKNOWN"),
            "fiscal_period": result.get("fiscal_period", "UNKNOWN"),
            "notes": result.get("notes", ""),
            "errors": errors,
            "method": "ai",
        }

    except ImportError:
        logger.warning("anthropic not installed, falling back to heuristic")
        return map_financials_heuristic(raw_text, tables)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        return map_financials_heuristic(raw_text, tables)
    except Exception as e:
        logger.error(f"API call failed: {e}")
        return map_financials_heuristic(raw_text, tables)


def map_financials_heuristic(
    raw_text: str,
    tables: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Extract financial fields using regex and pattern matching (no AI needed).

    Fallback method that works without API access. Uses common financial
    statement labels and patterns to locate values.

    Args:
        raw_text: Extracted text from PDF
        tables: Extracted tables from PDF

    Returns:
        Dictionary with same structure as map_financials_with_ai
    """
    fields = {}
    confidence = {}

    # Combine text and tables for searching
    search_text = raw_text.lower()
    for table in tables:
        caption = (table.get("caption") or "").lower()
        search_text += "\n" + caption
        for row in table.get("rows", []):
            search_text += "\n" + " ".join(str(v).lower() for v in row)

    # Pattern matching rules: (field_name, [patterns], confidence)
    patterns = [
        ("revenue_mn", [r"(?:total\s+)?(?:net\s+)?revenue", r"net\s+sales", r"sales\s+revenue"], 0.85),
        ("ebit_mn", [r"operating\s+(?:income|earnings)", r"\bebit\b"], 0.90),
        ("depreciation_mn", [r"depreciation\s+and\s+amortization|depreciation"], 0.80),
        ("amortization_mn", [r"amortization\s+(?:of\s+)?(?:intangibles|goodwill)|amortization"], 0.80),
        ("interest_expense_mn", [r"interest\s+expense"], 0.85),
        ("cfo_mn", [r"cash\s+flow\s+from\s+operations|operating\s+cash\s+flow"], 0.85),
        ("capex_mn", [r"capital\s+expenditure|capex|purchase\s+of\s+(?:property|plant|equipment)"], 0.75),
        ("total_debt_mn", [r"total\s+debt(?!\s+service)", r"(?:long|short).{0,15}debt"], 0.70),
        ("cash_mn", [r"cash\s+and\s+(?:cash\s+)?equivalent", r"cash\s+balance"], 0.85),
        ("total_equity_mn", [r"total\s+(?:shareholders?\s+)?equity|stockholders?\s+equity"], 0.85),
        ("common_dividends_mn", [r"dividends?\s+paid.*common", r"common\s+dividends?"], 0.80),
    ]

    # Try to find patterns and extract numbers
    for field, pats, conf in patterns:
        for pattern in pats:
            matches = re.finditer(pattern, search_text, re.IGNORECASE)
            for match in matches:
                # Look for numbers near the pattern match
                start = max(0, match.start() - 200)
                end = min(len(search_text), match.end() + 200)
                context = search_text[start:end]

                # Extract numbers (look for patterns like 1,234.5 or 1234 M or 1.2B)
                num_patterns = [
                    r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:mn|m|million)",
                    r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:k|thousand)(?!\s*\()",
                    r"(\d+(?:\.\d+)?)\s*(?:billion|b)(?!\s*\()",
                    r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)",
                ]

                for num_pattern in num_patterns:
                    num_match = re.search(num_pattern, context, re.IGNORECASE)
                    if num_match:
                        num_str = num_match.group(1).replace(",", "")
                        try:
                            value = float(num_str)

                            # Convert to millions if necessary
                            if "billion" in context or "b)" in context:
                                value *= 1000
                            elif "thousand" in context or "k)" in context:
                                value /= 1000

                            # Only accept if reasonable range
                            if 0 < value < 1_000_000:
                                if field not in fields or conf > confidence.get(field, 0):
                                    fields[field] = value
                                    confidence[field] = conf
                                break
                        except ValueError:
                            pass

    return {
        "fields": fields,
        "confidence": confidence,
        "currency": "UNKNOWN",
        "fiscal_period": "UNKNOWN",
        "notes": f"Extracted {len(fields)} fields using heuristic pattern matching",
        "errors": [],
        "method": "heuristic",
    }
