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


def _call_claude_with_retry(client, model: str, max_tokens: int, prompt: str, max_retries: int = 2) -> str:
    """Call Claude API with exponential backoff retry on transient errors.

    Returns the response text on success.
    Raises on permanent errors or after all retries exhausted.
    """
    import time as _time

    for attempt in range(max_retries + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                timeout=45.0,  # 45 second timeout per API call
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text

        except Exception as e:
            error_str = str(e).lower()
            # Permanent errors — don't retry
            is_permanent = any(kw in error_str for kw in [
                "invalid_api_key", "authentication", "permission",
                "invalid_request", "model_not_found",
            ])
            if is_permanent:
                logger.error(f"Permanent API error (attempt {attempt + 1}): {e}")
                raise

            # Transient errors — retry with backoff
            if attempt < max_retries:
                wait = 2 ** attempt  # 1s, 2s
                logger.warning(f"Transient API error (attempt {attempt + 1}/{max_retries + 1}), retrying in {wait}s: {e}")
                _time.sleep(wait)
            else:
                logger.error(f"API failed after {max_retries + 1} attempts: {e}")
                raise


def map_financials_with_ai(
    raw_text: str,
    tables: List[Dict[str, Any]],
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Use Claude API to intelligently extract financial fields from documents.

    Analyzes both raw text and structured table data to identify and extract
    financial fields. Returns confidence scores for each field.
    Includes retry logic with exponential backoff for transient API errors.

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
        response_text = _call_claude_with_retry(
            client,
            model="claude-sonnet-4-6",
            max_tokens=2048,
            prompt=prompt,
            max_retries=2,
        )

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

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        return map_financials_heuristic(raw_text, tables)
    except Exception as e:
        logger.error(f"API call failed: {e}")
        return map_financials_heuristic(raw_text, tables)


def _arithmetic_validation(fields: dict) -> list:
    """Run zero-cost arithmetic cross-checks on extracted fields.

    Returns a list of dicts: {check, expected, actual, diff, severity, field_hint}
    where severity is 'warning' (>5% off) or 'error' (>15% off).
    """
    issues = []

    def _get(name):
        return fields.get(name)

    def _check(check_name, expected, actual, tolerance_pct, field_hint):
        if expected is None or actual is None:
            return
        if expected == 0 and actual == 0:
            return
        diff = abs(expected - actual)
        base = max(abs(expected), abs(actual), 1)
        pct = (diff / base) * 100
        if pct > tolerance_pct:
            severity = "error" if pct > 15 else "warning"
            issues.append({
                "check": check_name,
                "expected": expected,
                "actual": actual,
                "diff": round(diff, 1),
                "pct_off": round(pct, 1),
                "severity": severity,
                "field_hint": field_hint,
            })

    # 1. Total debt = ST debt + LT debt (+ CPLTD if separate)
    st = _get("st_debt_mn")
    lt = _get("lt_debt_net_mn")
    cpltd = _get("cpltd_mn") or 0
    td = _get("total_debt_mn")
    if st is not None and lt is not None and td is not None:
        calc_total = st + lt + cpltd
        _check("total_debt = st_debt + lt_debt + cpltd", td, calc_total, 5, "total_debt_mn")

    # 2. NWC sanity: NWC_current should roughly = total_assets - lt_assets - (total_assets - equity - debt-ish)
    # Simpler: if we have assets and equity, total_liabilities = assets - equity
    assets = _get("assets_current_mn")
    equity = _get("total_equity_mn")
    if assets is not None and equity is not None and td is not None:
        implied_total_liab = assets - equity
        # implied_total_liab should be >= total_debt (debt is a subset of liabilities)
        if implied_total_liab > 0 and td > implied_total_liab * 1.05:
            issues.append({
                "check": "total_debt should be <= total_liabilities (assets - equity)",
                "expected": round(implied_total_liab, 1),
                "actual": td,
                "diff": round(td - implied_total_liab, 1),
                "pct_off": round(((td - implied_total_liab) / implied_total_liab) * 100, 1),
                "severity": "error",
                "field_hint": "total_debt_mn",
            })

    # 3. Capex should be positive (or zero), CFO can be either sign
    capex = _get("capex_mn")
    if capex is not None and capex < 0:
        issues.append({
            "check": "capex should be positive (represents spending)",
            "expected": abs(capex),
            "actual": capex,
            "diff": abs(capex) * 2,
            "pct_off": 100,
            "severity": "warning",
            "field_hint": "capex_mn",
        })

    # 4. EBIT/EBITDA relationship: EBIT + D&A should ≈ EBITDA
    ebit = _get("ebit_mn")
    dep = _get("depreciation_mn") or 0
    amort = _get("amortization_mn") or 0
    revenue = _get("revenue_mn")

    # 5. EBIT should be < Revenue in absolute terms
    if ebit is not None and revenue is not None and revenue != 0:
        if abs(ebit) > abs(revenue) * 1.5:
            issues.append({
                "check": "abs(EBIT) should be <= 1.5x Revenue",
                "expected": revenue,
                "actual": ebit,
                "diff": round(abs(ebit) - abs(revenue), 1),
                "pct_off": round((abs(ebit) / abs(revenue)) * 100, 1),
                "severity": "error",
                "field_hint": "ebit_mn",
            })

    # 6. Assets current vs prior — shouldn't differ by >200%
    a_cur = _get("assets_current_mn")
    a_pri = _get("assets_prior_mn")
    if a_cur is not None and a_pri is not None and a_pri != 0:
        ratio = abs(a_cur / a_pri)
        if ratio > 3.0 or ratio < 0.33:
            issues.append({
                "check": "current vs prior total assets shouldn't differ by >200%",
                "expected": a_pri,
                "actual": a_cur,
                "diff": round(abs(a_cur - a_pri), 1),
                "pct_off": round(abs(ratio - 1) * 100, 1),
                "severity": "error",
                "field_hint": "assets_prior_mn",
            })

    # 7. NWC = current assets - current liabilities (cross-check if we can infer)
    nwc = _get("nwc_current_mn")
    lt_assets = _get("lt_operating_assets_current_mn")
    if nwc is not None and assets is not None and lt_assets is not None and equity is not None:
        # current_assets = total_assets - lt_operating_assets (approximately)
        implied_current_assets = assets - lt_assets
        # current_liabilities = total_assets - equity - non_current_liab
        # NWC = current_assets - current_liabilities
        # If we know debt: non_current_liab ≈ lt_debt
        if lt is not None:
            implied_current_liab = (assets - equity) - lt
            implied_nwc = implied_current_assets - implied_current_liab
            _check("NWC cross-check (assets - lt_assets - current_liab)", nwc, round(implied_nwc, 1), 10, "nwc_current_mn")

    # 8. Cash should be < total assets
    cash = _get("cash_mn")
    if cash is not None and assets is not None and cash > assets:
        issues.append({
            "check": "cash should be <= total assets",
            "expected": assets,
            "actual": cash,
            "diff": round(cash - assets, 1),
            "pct_off": round(((cash - assets) / assets) * 100, 1),
            "severity": "error",
            "field_hint": "cash_mn",
        })

    return issues


def _build_reextraction_prompt(relevant_text: str, flagged_fields: list, original_values: dict) -> str:
    """Build a targeted prompt to re-extract only the flagged fields.

    Uses ~500-1000 tokens per call — very cheap.
    """
    field_descriptions = {k: v for k, v in FINANCIAL_FIELDS.items()}
    field_list = []
    for item in flagged_fields:
        fname = item["field_hint"]
        desc = field_descriptions.get(fname, fname)
        field_list.append(
            f"- {fname} ({desc}): originally extracted as {original_values.get(fname, 'N/A')}, "
            f"flagged because: {item['check']} (off by {item.get('pct_off', '?')}%)"
        )

    return f"""You are a financial data extraction expert. A previous extraction pass had validation errors on specific fields. Re-extract ONLY the flagged fields below, being extra careful.

DOCUMENT TEXT:
{relevant_text}

FLAGGED FIELDS TO RE-EXTRACT:
{chr(10).join(field_list)}

IMPORTANT:
- Report ALL values in THOUSANDS (000s)
- Check the document's reporting unit ($000, whole dollars, millions, etc.)
- Double-check your arithmetic carefully
- If you see the same value as before and are confident, keep it
- If the number was clearly misread (OCR artifact), try to correct it

Return ONLY a JSON object:
{{
  "fields": {{"field_name": corrected_value_in_thousands, ...}},
  "confidence": {{"field_name": 0.0_to_1.0, ...}},
  "corrections": {{"field_name": "brief explanation of what changed"}}
}}"""


def validate_and_fix_extraction(
    extraction_result: dict,
    raw_text: str,
    tables: list,
    api_key: str = None,
    enable_ai_fix: bool = True,
) -> dict:
    """Run arithmetic validation on extraction, optionally re-extract flagged fields with AI.

    Step 1: Pure arithmetic checks (zero tokens)
    Step 2: If errors found and enable_ai_fix=True, targeted AI re-extraction (~500-1000 tokens)

    Args:
        extraction_result: Output from map_financials_with_ai()
        raw_text: The original PDF text
        tables: The original extracted tables
        api_key: Anthropic API key (for AI fix step)
        enable_ai_fix: Whether to spend tokens on re-extraction

    Returns:
        Updated extraction_result with added 'validation' key
    """
    fields = extraction_result.get("fields", {})
    confidence = extraction_result.get("confidence", {})

    # Step 1: Arithmetic validation (free)
    issues = _arithmetic_validation(fields)

    validation = {
        "checks_run": True,
        "issues": issues,
        "errors": [i for i in issues if i["severity"] == "error"],
        "warnings": [i for i in issues if i["severity"] == "warning"],
        "ai_reextraction": False,
        "corrections": {},
    }

    # Step 2: AI re-extraction of flagged fields (only for errors, not warnings)
    error_items = validation["errors"]
    if error_items and enable_ai_fix:
        try:
            import anthropic
            import os

            api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning("No API key for re-extraction fix")
                extraction_result["validation"] = validation
                return extraction_result

            client = anthropic.Anthropic(api_key=api_key)
            relevant_text = _extract_relevant_sections(raw_text, max_chars=15000)
            prompt = _build_reextraction_prompt(relevant_text, error_items, fields)

            logger.info(f"Running targeted AI re-extraction for {len(error_items)} flagged fields")
            response_text = _call_claude_with_retry(
                client,
                model="claude-sonnet-4-6",
                max_tokens=1024,
                prompt=prompt,
                max_retries=1,
            )

            fix_result = _extract_json_from_response(response_text)
            fix_fields = fix_result.get("fields", {})
            fix_confidence = fix_result.get("confidence", {})
            corrections = fix_result.get("corrections", {})

            # Apply corrections where the AI is more confident
            for fname, new_val in fix_fields.items():
                if new_val is None:
                    continue
                old_val = fields.get(fname)
                new_conf = fix_confidence.get(fname, 0.5)
                old_conf = confidence.get(fname, 0.5)

                if new_conf >= old_conf or new_val != old_val:
                    fields[fname] = new_val
                    confidence[fname] = new_conf
                    correction_note = corrections.get(fname, "re-extracted")
                    validation["corrections"][fname] = {
                        "old": old_val,
                        "new": new_val,
                        "reason": correction_note,
                    }
                    logger.info(f"Corrected {fname}: {old_val} → {new_val} ({correction_note})")

            validation["ai_reextraction"] = True

            # Re-run validation after corrections
            post_fix_issues = _arithmetic_validation(fields)
            validation["post_fix_issues"] = post_fix_issues
            validation["post_fix_errors"] = [i for i in post_fix_issues if i["severity"] == "error"]

        except Exception as e:
            logger.warning(f"AI re-extraction failed: {e}")
            validation["ai_reextraction_error"] = str(e)

    extraction_result["fields"] = fields
    extraction_result["confidence"] = confidence
    extraction_result["validation"] = validation
    return extraction_result


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
