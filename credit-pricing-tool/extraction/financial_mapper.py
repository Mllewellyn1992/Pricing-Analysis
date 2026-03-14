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

# Standard financial fields we try to extract (values in THOUSANDS)
FINANCIAL_FIELDS = {
    "revenue_mn": "Total revenue or net sales (thousands)",
    "ebit_mn": "EBIT or operating income (thousands)",
    "depreciation_mn": "Depreciation (thousands)",
    "amortization_mn": "Amortization (thousands)",
    "interest_expense_mn": "Interest expense (thousands)",
    "cash_interest_paid_mn": "Cash interest paid (thousands)",
    "cash_taxes_paid_mn": "Cash taxes paid (thousands)",
    "total_debt_mn": "Total debt (thousands)",
    "st_debt_mn": "Short-term debt (thousands)",
    "cpltd_mn": "Current portion of long-term debt (thousands)",
    "lt_debt_net_mn": "Long-term debt net (thousands)",
    "capital_leases_mn": "Capital leases (thousands)",
    "cash_mn": "Cash and equivalents (thousands)",
    "cash_like_mn": "Cash-like securities (thousands)",
    "total_equity_mn": "Total equity (thousands)",
    "minority_interest_mn": "Minority interest (thousands)",
    "deferred_taxes_mn": "Deferred taxes (thousands)",
    "cfo_mn": "Cash flow from operations (thousands)",
    "capex_mn": "Capital expenditures (thousands)",
    "common_dividends_mn": "Common dividends paid (thousands)",
    "preferred_dividends_mn": "Preferred dividends paid (thousands)",
    "nwc_current_mn": "Net working capital - current period (thousands)",
    "nwc_prior_mn": "Net working capital - prior period (thousands)",
    "lt_operating_assets_current_mn": "Long-term operating assets - current (thousands)",
    "lt_operating_assets_prior_mn": "Long-term operating assets - prior (thousands)",
    "assets_current_mn": "Total assets - current period (thousands)",
    "assets_prior_mn": "Total assets - prior period (thousands)",
    "avg_capital_mn": "Average capital invested (thousands)",
}

# Section headers that indicate financial statements (in priority order)
_SECTION_MARKERS = [
    # Primary financial statements
    "statement of comprehensive income",
    "income statement",
    "profit or loss",
    "profit and loss",
    "statement of financial position",
    "balance sheet",
    "statement of cash flows",
    "cash flow statement",
    "statement of changes in equity",
    # Key line items (fallback if no headers found)
    "revenue",
    "total assets",
    "total equity",
    "cash flows from operating",
    "profit before tax",
]


def _find_financial_sections(raw_text: str) -> list:
    """Scan text for financial statement sections, classifying each as primary or secondary.

    Returns list of (start, end, marker, is_primary) tuples.
    """
    text_lower = raw_text.lower()
    sections = []

    for marker in _SECTION_MARKERS:
        start = 0
        while True:
            idx = text_lower.find(marker, start)
            if idx == -1:
                break

            context = raw_text[idx:min(len(raw_text), idx + 400)]
            number_count = len(re.findall(r"\d{3,}", context))

            if number_count >= 3:
                sec_start = max(0, idx - 100)
                sec_end = min(len(raw_text), idx + 3000)
                sections.append((sec_start, sec_end, marker, True))
            elif number_count >= 1:
                sec_start = max(0, idx - 50)
                sec_end = min(len(raw_text), idx + 1500)
                sections.append((sec_start, sec_end, marker, False))

            start = idx + len(marker)

    return sections


def _merge_overlapping_sections(secs):
    """Sort sections by position and merge overlapping ones (within 200 char gap)."""
    secs.sort(key=lambda x: x[0])
    merged = []
    for start, end, marker in secs:
        if merged and start <= merged[-1][1] + 200:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end), merged[-1][2])
        else:
            merged.append((start, end, marker))
    return merged


def _collect_text_within_budget(raw_text, section_groups, max_chars):
    """Collect text chunks from section groups up to max_chars budget.

    Args:
        section_groups: list of merged section lists, in priority order
    Returns:
        list of text chunks
    """
    parts = []
    total_chars = 0

    for sections in section_groups:
        for start, end, _marker in sections:
            chunk = raw_text[start:end]
            if total_chars + len(chunk) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 500:
                    parts.append(chunk[:remaining])
                    total_chars += remaining
                return parts
            parts.append(chunk)
            total_chars += len(chunk)

    return parts


def _extract_relevant_sections(raw_text: str, max_chars: int = 20000) -> str:
    """Extract the most financially-relevant sections from raw PDF text.

    Finds financial statement headers, prioritises sections with numeric data,
    and deduplicates overlapping sections within a character budget.
    Falls back to first max_chars characters if no sections found.
    """
    if len(raw_text) <= max_chars:
        return raw_text

    sections = _find_financial_sections(raw_text)
    if not sections:
        return raw_text[:max_chars]

    primary = [(s, e, m) for s, e, m, is_primary in sections if is_primary]
    secondary = [(s, e, m) for s, e, m, is_primary in sections if not is_primary]

    primary_merged = _merge_overlapping_sections(primary)
    secondary_merged = _merge_overlapping_sections(secondary)

    parts = _collect_text_within_budget(raw_text, [primary_merged, secondary_merged], max_chars)

    result = "\n...\n".join(parts)
    logger.info(
        f"Extracted {len(result)} relevant chars from {len(raw_text)} total "
        f"({len(primary_merged)} primary + {len(secondary_merged)} secondary sections)"
    )
    return result


def _build_table_text(tables: List[Dict[str, Any]]) -> str:
    """Build formatted table context from extracted tables."""
    table_text = ""
    if tables:
        table_text = "\n\nExtracted Tables:\n"
        for i, table in enumerate(tables[:5], 1):
            caption = table.get("caption", f"Table {i}")
            columns = table.get("columns", [])
            rows = table.get("rows", [])[:10]
            table_text += f"\n{caption}:\n"
            if columns:
                table_text += " | ".join(columns) + "\n"
                table_text += "-" * 60 + "\n"
            for row in rows:
                table_text += " | ".join(row) + "\n"
    return table_text


def _build_extraction_prompt(relevant_text: str, table_text: str) -> str:
    """Build the Claude API prompt for financial extraction."""
    fields_str = "\n".join(
        f"- {field}: {desc}" for field, desc in FINANCIAL_FIELDS.items()
    )
    return f"""You are a financial data extraction expert. Extract financial data from the following financial statement.

DOCUMENT TEXT:
{relevant_text}
{table_text}

TASK:
Extract the following financial fields from the document above. Only extract values that you can identify with reasonable confidence.

IMPORTANT - UNIT CONVERSION:
Report ALL values in THOUSANDS (000s) of the local currency.

STEP 1: Determine the document's reporting unit FIRST by looking for explicit indicators:
- "$000", "'000", "Expressed in thousands", "in thousands of NZ dollars" → THOUSANDS (use values as-is)
- "$M", "in millions", "NZ$m" → MILLIONS (multiply by 1,000 to get thousands)
- "$B", "in billions" → BILLIONS (multiply by 1,000,000 to get thousands)
- "$", "NZ$" with NO scale indicator → WHOLE DOLLARS (divide by 1,000 to get thousands)

STEP 2: Verify by checking if the resulting thousands values make sense:
- A small NZ company typically has revenue of 500-50,000 (i.e. $500K-$50M)
- A large NZ company typically has revenue of 50,000-10,000,000 (i.e. $50M-$10B)
- If revenue comes out as 0.5-50 in thousands (i.e. $500-$50,000), you likely divided by too much
- If revenue comes out as 500,000,000+ in thousands (i.e. $500B+), you likely multiplied too much

STEP 3: Common NZ annual report patterns:
- Many NZ companies report in WHOLE DOLLARS with values like "1,562,674" or "37,678,302"
- If you see numbers with 6+ digits and commas (e.g., "1,234,567") and NO "$000" indicator, these are WHOLE DOLLARS → divide by 1,000
- If you see numbers with 3-4 digits (e.g., "1,234") and a "$000" indicator, they are already in thousands
- Property companies may show values in tens of millions in whole dollars — still divide by 1,000

FIELDS TO EXTRACT:
{fields_str}

RESPONSE FORMAT:
Return ONLY a valid JSON object with this structure (no other text):
{{
  "fields": {{
    "field_name": number_in_thousands,
    "another_field": null
  }},
  "confidence": {{
    "field_name": 0.0_to_1.0,
    "another_field": null
  }},
  "currency": "USD|NZD|GBP|etc or UNKNOWN",
  "fiscal_period": "FY2024|Q1 2024|etc or UNKNOWN",
  "source_units": "thousands|millions|dollars|unknown",
  "notes": "any important notes about the extraction including what unit the document uses"
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
3. All numbers must be converted to THOUSANDS
4. If a field is 0 or missing, return null, not 0
5. Validate debt components sum reasonably if multiple debt fields found
6. Pay careful attention to the units used in the document (look for "$000", "in thousands", "$M", etc.)
"""


def _validate_and_clean_response(result: dict) -> tuple:
    """Validate and clean the API response, returning fields, confidence, and errors."""
    fields = result.get("fields", {})
    confidence = result.get("confidence", {})
    fields = {k: v for k, v in fields.items() if v is not None}
    confidence = {k: v for k, v in confidence.items() if confidence.get(k) is not None}

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
        elif value > 1_000_000_000:
            logger.warning(f"{field} value {value} seems too large for thousands")

    return fields, confidence, errors


def _extract_json_from_response(response_text: str) -> dict:
    """Parse JSON from Claude response, handling markdown code blocks."""
    json_str = response_text
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0]
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0]
    return json.loads(json_str.strip())


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

    table_text = _build_table_text(tables)
    relevant_text = _extract_relevant_sections(raw_text, max_chars=20000)
    prompt = _build_extraction_prompt(relevant_text, table_text)

    try:
        logger.debug("Calling Claude API for financial field extraction")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text
        result = _extract_json_from_response(response_text)
        fields, confidence, errors = _validate_and_clean_response(result)

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

                            # Convert to thousands
                            if "billion" in context or "b)" in context:
                                value *= 1_000_000  # billions to thousands
                            elif "million" in context or "mn" in context:
                                value *= 1_000  # millions to thousands
                            # If already in thousands ($000) or raw dollars,
                            # leave as-is (most NZ financials report in $000)

                            # Only accept if reasonable range (in thousands)
                            if 0 < value < 1_000_000_000:
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
