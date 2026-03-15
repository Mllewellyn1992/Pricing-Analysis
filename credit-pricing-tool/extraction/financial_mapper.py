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
    "ebit_mn": "EBIT or operating income EXCLUDING impairments (thousands) — recurring operating earnings only",
    "ebitda_mn": "EBITDA or EBITDAF EXCLUDING impairments (thousands) — if explicitly stated in report",
    "impairment_mn": "Impairment charges — asset write-downs, goodwill impairment, etc. (thousands, POSITIVE number)",
    "operating_expenses_mn": "Total operating expenses before D&A and before impairments (thousands, POSITIVE number)",
    # ── IFRS-16 lease breakdown: depreciation ──
    "depreciation_mn": "TOTAL depreciation incl. ROU assets (thousands) — must equal depreciation_ppe_mn + depreciation_rou_mn",
    "depreciation_ppe_mn": "Depreciation of property, plant & equipment ONLY, excluding right-of-use assets (thousands)",
    "depreciation_rou_mn": "Depreciation/amortisation of right-of-use (ROU) lease assets ONLY (thousands)",
    "amortization_mn": "Amortization of intangibles (thousands)",
    # ── IFRS-16 lease breakdown: interest ──
    "interest_expense_mn": "TOTAL interest expense incl. lease interest (thousands) — must equal interest_debt_mn + interest_lease_mn",
    "interest_debt_mn": "Interest on borrowings/bank debt ONLY, excluding lease interest (thousands)",
    "interest_lease_mn": "Interest on lease liabilities ONLY (thousands)",
    "cash_interest_paid_mn": "Cash interest paid (thousands)",
    "cash_taxes_paid_mn": "Cash taxes paid (thousands)",
    # ── IFRS-16 lease breakdown: balance sheet ──
    "total_debt_mn": "Total borrowings/bank debt excluding lease liabilities (thousands)",
    "st_debt_mn": "Short-term debt (thousands)",
    "cpltd_mn": "Current portion of long-term debt (thousands)",
    "lt_debt_net_mn": "Long-term debt net (thousands)",
    "lease_liabilities_mn": "TOTAL lease liabilities (current + non-current) under IFRS-16 (thousands)",
    "lease_liabilities_current_mn": "Current portion of lease liabilities (thousands)",
    "lease_liabilities_noncurrent_mn": "Non-current portion of lease liabilities (thousands)",
    "rou_assets_mn": "Right-of-use assets on balance sheet (thousands)",
    "cash_mn": "Cash and equivalents (thousands)",
    "cash_like_mn": "Cash-like securities (thousands)",
    "total_equity_mn": "Total equity (thousands)",
    "minority_interest_mn": "Minority interest (thousands)",
    "deferred_taxes_mn": "Deferred taxes (thousands)",
    # ── IFRS-16 lease breakdown: cash flow ──
    "cfo_mn": "Cash flow from operations (thousands)",
    "capex_mn": "Capital expenditures (thousands)",
    "lease_principal_payments_mn": "Principal portion of lease payments in financing activities (thousands)",
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
# "Critical" markers get the widest capture window (5000 chars) to avoid
# truncating dense pages where income statement + balance sheet share a page.
_CRITICAL_MARKERS = [
    "consolidated income statement",
    "income statement",
    "profit or loss",
    "profit and loss",
    "consolidated balance sheet",
    "statement of financial position",
    "balance sheet",
    "consolidated statement of cash flows",
    "statement of cash flows",
    "cash flow statement",
]

_PRIMARY_MARKERS = [
    "statement of comprehensive income",
    "statement of changes in equity",
    "net debt",
    "bank and debt facilities",
    "borrowings",
    "segment information",
    "operating performance",
    "right-of-use",
    "lease liabilities",
    "depreciation and amortisation",
    "depreciation and amortization",
]

_SECONDARY_MARKERS = [
    "revenue",
    "retail sales",
    "total assets",
    "total equity",
    "cash flows from operating",
    "profit before tax",
    "net cash flows from operating",
    "operating profit",
    "earnings before interest",
]


def _find_financial_sections(raw_text: str) -> list:
    """Scan text for financial statement sections, classifying each by priority.

    Returns list of (start, end, marker, priority) tuples.
    Priority: 0 = critical (income stmt, balance sheet, cash flow)
              1 = primary  (comprehensive income, equity changes, debt notes)
              2 = secondary (individual line items as fallback)
    """
    text_lower = raw_text.lower()
    sections = []

    def _scan(markers, priority, context_before, context_after_dense, context_after_sparse):
        for marker in markers:
            start = 0
            while True:
                idx = text_lower.find(marker, start)
                if idx == -1:
                    break

                # Look ahead to see how number-dense the following text is
                context = raw_text[idx:min(len(raw_text), idx + 600)]
                number_count = len(re.findall(r"\d{3,}", context))

                if number_count >= 3:
                    sec_start = max(0, idx - context_before)
                    sec_end = min(len(raw_text), idx + context_after_dense)
                    sections.append((sec_start, sec_end, marker, priority))
                elif number_count >= 1:
                    sec_start = max(0, idx - 50)
                    sec_end = min(len(raw_text), idx + context_after_sparse)
                    sections.append((sec_start, sec_end, marker, priority))

                start = idx + len(marker)

    # Critical statements: capture up to 5000 chars after (handles dense pages
    # where income statement + balance sheet share one PDF page)
    _scan(_CRITICAL_MARKERS, priority=0, context_before=200, context_after_dense=5000, context_after_sparse=2000)
    # Primary supplementary statements/notes
    _scan(_PRIMARY_MARKERS, priority=1, context_before=100, context_after_dense=3000, context_after_sparse=1500)
    # Secondary line-item fallbacks
    _scan(_SECONDARY_MARKERS, priority=2, context_before=50, context_after_dense=2000, context_after_sparse=1000)

    return sections


def _merge_overlapping_sections(secs):
    """Sort sections by position and merge overlapping ones (within 300 char gap)."""
    secs.sort(key=lambda x: x[0])
    merged = []
    for start, end, marker in secs:
        if merged and start <= merged[-1][1] + 300:
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
    seen_ranges = set()

    for sections in section_groups:
        for start, end, _marker in sections:
            # Deduplicate: skip if this range is largely contained in an already-added range
            chunk_key = (start // 500, end // 500)
            if chunk_key in seen_ranges:
                continue
            seen_ranges.add(chunk_key)

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


def _extract_relevant_sections(raw_text: str, max_chars: int = 50000) -> str:
    """Extract the most financially-relevant sections from raw PDF text.

    Finds financial statement headers, prioritises sections with numeric data,
    and deduplicates overlapping sections within a character budget.
    Falls back to first max_chars characters if no sections found.

    Budget: 50,000 chars by default — enough for income statement + balance sheet
    + cash flow + key notes (debt, equity, leases, depreciation) even when
    pages are dense or notes are spread across many pages.
    """
    if len(raw_text) <= max_chars:
        return raw_text

    sections = _find_financial_sections(raw_text)
    if not sections:
        return raw_text[:max_chars]

    critical = [(s, e, m) for s, e, m, prio in sections if prio == 0]
    primary = [(s, e, m) for s, e, m, prio in sections if prio == 1]
    secondary = [(s, e, m) for s, e, m, prio in sections if prio == 2]

    critical_merged = _merge_overlapping_sections(critical)
    primary_merged = _merge_overlapping_sections(primary)
    secondary_merged = _merge_overlapping_sections(secondary)

    parts = _collect_text_within_budget(
        raw_text,
        [critical_merged, primary_merged, secondary_merged],
        max_chars,
    )

    result = "\n...\n".join(parts)
    logger.info(
        f"Extracted {len(result)} relevant chars from {len(raw_text)} total "
        f"({len(critical_merged)} critical + {len(primary_merged)} primary "
        f"+ {len(secondary_merged)} secondary sections)"
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
    return f"""You are a financial data extraction expert specialising in New Zealand annual reports.

DOCUMENT TEXT:
{relevant_text}
{table_text}

TASK:
Extract the following financial fields from the MOST RECENT YEAR in the document.

═══════════════════════════════════════════════════════════
CRITICAL WARNING — NOTE REFERENCES ARE NOT VALUES!
═══════════════════════════════════════════════════════════
NZ annual reports put note references (e.g. "2.1", "3.3", "4.2", "8.1", "10.3", "11.2")
inline BEFORE the actual numeric values. For example:

   "Cash and cash equivalents  11.2    39,206"
     → "11.2" is a NOTE REFERENCE, "39,206" is the VALUE
   "Depreciation and amortisation expense  3.3  156,524"
     → "3.3" is a NOTE REFERENCE, "156,524" is the VALUE
   "Retail sales  2.1  3,086,725"
     → "2.1" is a NOTE REFERENCE, "3,086,725" is the VALUE
   "Minority interest  11.5  337"
     → "11.5" is a NOTE REFERENCE, "337" is the VALUE

NEVER extract note references as financial values.
Note references are typically 1-2 digit numbers with a decimal (e.g. "2.1", "11.2").
Financial values are typically 3+ digit numbers, often with commas (e.g. "39,206", "3,086,725").

Also NEVER extract reporting period numbers as values:
   "53 Weeks" / "52 Weeks" → these describe the reporting period, NOT financial values.

═══════════════════════════════════════════════════════════
UNIT CONVERSION — Report ALL values in THOUSANDS (000s)
═══════════════════════════════════════════════════════════

STEP 1: Determine the document's reporting unit:
- "$000", "'000", "$ 000", "in thousands" → THOUSANDS (use values as-is)
- "$M", "in millions", "NZ$m" → MILLIONS (multiply by 1,000)
- "$B", "in billions" → BILLIONS (multiply by 1,000,000)
- "$", "NZ$" with NO scale indicator → WHOLE DOLLARS (divide by 1,000)

STEP 2: Sanity check — NZ companies:
- Small: revenue 500–50,000 ($000) i.e. $500K–$50M
- Medium: revenue 50,000–500,000 ($000) i.e. $50M–$500M
- Large: revenue 500,000–10,000,000 ($000) i.e. $500M–$10B

═══════════════════════════════════════════════════════════
WHERE TO FIND EACH FIELD
═══════════════════════════════════════════════════════════
- revenue_mn: Look for "Revenue", "Retail sales", "Net sales", "Sales" in the INCOME STATEMENT
  (NOT in narrative summaries or "at a glance" sections)
- ebit_mn: RECURRING operating earnings EXCLUDING impairments. This is critical for credit analysis.
  Look for "Operating profit", "Earnings before interest and tax", "EBIT" in INCOME STATEMENT.
  If no explicit EBIT line exists, CALCULATE it using ONE of these methods (in priority order):
  METHOD 1: Total Revenue - Operating Expenses - Depreciation & Amortisation (EXCLUDE impairments)
  METHOD 2: EBITDA/EBITDAF - Depreciation - Amortisation (EXCLUDE impairments)
  METHOD 3: Profit before tax + Finance costs (EXCLUDE impairments, EXCLUDE imputed interest on deposits)
  *** CRITICAL: ALWAYS EXCLUDE impairment charges from EBIT. Impairments are non-recurring. ***
  *** Also EXCLUDE imputed interest income/charges on accommodation deposits (retirement village accounting) ***
- ebitda_mn: Only extract if explicitly stated (e.g. "EBITDA", "EBITDAF"). Exclude impairments.
- impairment_mn: "Impairment loss", "Impairment of assets", "Write-down" — report as POSITIVE number.
  This is extracted separately so EBIT can be cross-validated.
- operating_expenses_mn: Total operating expenses BEFORE D&A and BEFORE impairments — report as POSITIVE.
  Look for "Operating expenses", "Total operating expenses". Exclude D&A and impairments.
- cfo_mn: "Net cash flows from operating activities" in CASH FLOW STATEMENT
- capex_mn: "Purchase of property, plant and equipment" or "Capital expenditure" in CASH FLOW STATEMENT
  (report as POSITIVE number even if shown as negative in the statement)
- cash_mn: "Cash and cash equivalents" in BALANCE SHEET
- total_equity_mn: "Total equity" in BALANCE SHEET
- total_debt_mn: "Borrowings" or total of short-term + long-term debt in BALANCE SHEET
  (EXCLUDE lease liabilities — those go in lease_liabilities_mn)
- assets_current_mn: "Total assets" for CURRENT YEAR in BALANCE SHEET
- assets_prior_mn: "Total assets" for PRIOR YEAR in BALANCE SHEET
- common_dividends_mn: "Dividends paid" in CASH FLOW STATEMENT or dividend notes

═══════════════════════════════════════════════════════════
IFRS-16 LEASE BREAKDOWN — CRITICAL
═══════════════════════════════════════════════════════════
Most NZ companies report under IFRS-16, which capitalises leases onto the balance sheet.
You MUST break out lease vs non-lease components for cross-validation:

DEPRECIATION (Income Statement or Notes):
- depreciation_mn: TOTAL depreciation = PPE depreciation + ROU asset depreciation
- depreciation_ppe_mn: Depreciation of property, plant & equipment ONLY
- depreciation_rou_mn: Depreciation of right-of-use (ROU) assets ONLY
  Look for "Depreciation of right-of-use assets", "ROU depreciation", or in the notes
  breaking down depreciation by asset class. Often in the same note as total D&A.
  RULE: depreciation_mn MUST = depreciation_ppe_mn + depreciation_rou_mn

INTEREST (Income Statement):
- interest_expense_mn: TOTAL interest = debt interest + lease interest
- interest_debt_mn: Interest on borrowings/bank debt ONLY
  Look for "Interest on borrowings", "Other net interest", "Finance costs" excluding leases
- interest_lease_mn: Interest on lease liabilities ONLY
  Look for "Interest on lease liabilities", "Lease interest", "Interest on leases"
  RULE: interest_expense_mn MUST = interest_debt_mn + interest_lease_mn

BALANCE SHEET — LEASES:
- lease_liabilities_mn: TOTAL lease liabilities (current + non-current)
- lease_liabilities_current_mn: Current portion of lease liabilities
- lease_liabilities_noncurrent_mn: Non-current portion of lease liabilities
- rou_assets_mn: Right-of-use assets (often shown separately or in PPE notes)
  RULE: lease_liabilities_mn = lease_liabilities_current_mn + lease_liabilities_noncurrent_mn

CASH FLOW — LEASES:
- lease_principal_payments_mn: Principal portion of lease payments (financing activities)
  Look for "Payment of lease liabilities", "Lease payments - principal"

FIELDS TO EXTRACT:
{fields_str}

RESPONSE FORMAT:
Return ONLY a valid JSON object (no other text):
{{
  "fields": {{
    "field_name": number_in_thousands,
    "another_field": null
  }},
  "confidence": {{
    "field_name": 0.0_to_1.0,
    "another_field": null
  }},
  "currency": "NZD|USD|GBP|etc or UNKNOWN",
  "fiscal_period": "FY2025|FY2024|etc or UNKNOWN",
  "source_units": "thousands|millions|dollars|unknown",
  "notes": "brief notes about the extraction"
}}

CONFIDENCE SCORING:
- 0.95+: Found exact labeled value in a primary financial statement
- 0.80-0.94: High confidence from financial statement but slight ambiguity
- 0.60-0.79: Reasonable confidence, calculated or inferred
- 0.40-0.59: Low confidence, uncertain
- Below 0.40: Use null

RULES:
1. Only include fields with confidence >= 0.40
2. Return null for fields you cannot find
3. All numbers must be in THOUSANDS
4. Use null (not 0) for missing fields
5. Extract from the FORMAL FINANCIAL STATEMENTS, not from narrative summaries, "at a glance" pages, or management commentary
6. Capex should be a POSITIVE number (it represents cash spent)
7. Break out IFRS-16 lease components wherever possible — see the IFRS-16 section above
8. depreciation_mn MUST be the TOTAL (PPE + ROU), NOT just one component
9. interest_expense_mn MUST be the TOTAL (debt + lease), NOT just one component
10. ebit_mn MUST EXCLUDE impairment charges — S&P and Moody's both strip these out for credit analysis
11. impairment_mn should be POSITIVE (e.g. if income statement shows "(87,513)", extract as 87513)
12. operating_expenses_mn should be POSITIVE and EXCLUDE D&A and impairments
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


def _compute_ifrs16_totals(fields: dict, confidence: dict) -> list:
    """Compute IFRS-16 totals from components and vice-versa.

    If the AI extracted components but not the total, sum them up.
    If it extracted a total but not the components, leave components as-is (unknown).

    Returns a list of computation notes for logging.
    """
    notes = []

    def _get(name):
        return fields.get(name)

    def _set(name, value, conf, note):
        fields[name] = value
        confidence[name] = conf
        notes.append(note)

    # ── Depreciation: total = PPE + ROU ──
    dep_total = _get("depreciation_mn")
    dep_ppe = _get("depreciation_ppe_mn")
    dep_rou = _get("depreciation_rou_mn")

    if dep_ppe is not None and dep_rou is not None and dep_total is None:
        _set("depreciation_mn", dep_ppe + dep_rou,
             min(confidence.get("depreciation_ppe_mn", 0.8), confidence.get("depreciation_rou_mn", 0.8)),
             f"Computed depreciation_mn = {dep_ppe} + {dep_rou} = {dep_ppe + dep_rou}")
    elif dep_total is not None and dep_ppe is not None and dep_rou is None:
        computed_rou = dep_total - dep_ppe
        if computed_rou >= 0:
            _set("depreciation_rou_mn", computed_rou,
                 min(confidence.get("depreciation_mn", 0.8), confidence.get("depreciation_ppe_mn", 0.8)),
                 f"Computed depreciation_rou_mn = {dep_total} - {dep_ppe} = {computed_rou}")
    elif dep_total is not None and dep_rou is not None and dep_ppe is None:
        computed_ppe = dep_total - dep_rou
        if computed_ppe >= 0:
            _set("depreciation_ppe_mn", computed_ppe,
                 min(confidence.get("depreciation_mn", 0.8), confidence.get("depreciation_rou_mn", 0.8)),
                 f"Computed depreciation_ppe_mn = {dep_total} - {dep_rou} = {computed_ppe}")

    # ── Interest: total = debt + lease ──
    int_total = _get("interest_expense_mn")
    int_debt = _get("interest_debt_mn")
    int_lease = _get("interest_lease_mn")

    if int_debt is not None and int_lease is not None and int_total is None:
        _set("interest_expense_mn", int_debt + int_lease,
             min(confidence.get("interest_debt_mn", 0.8), confidence.get("interest_lease_mn", 0.8)),
             f"Computed interest_expense_mn = {int_debt} + {int_lease} = {int_debt + int_lease}")
    elif int_total is not None and int_debt is not None and int_lease is None:
        computed_lease = int_total - int_debt
        if computed_lease >= 0:
            _set("interest_lease_mn", computed_lease,
                 min(confidence.get("interest_expense_mn", 0.8), confidence.get("interest_debt_mn", 0.8)),
                 f"Computed interest_lease_mn = {int_total} - {int_debt} = {computed_lease}")
    elif int_total is not None and int_lease is not None and int_debt is None:
        computed_debt = int_total - int_lease
        if computed_debt >= 0:
            _set("interest_debt_mn", computed_debt,
                 min(confidence.get("interest_expense_mn", 0.8), confidence.get("interest_lease_mn", 0.8)),
                 f"Computed interest_debt_mn = {int_total} - {int_lease} = {computed_debt}")

    # ── Lease liabilities: total = current + non-current ──
    ll_total = _get("lease_liabilities_mn")
    ll_cur = _get("lease_liabilities_current_mn")
    ll_nc = _get("lease_liabilities_noncurrent_mn")

    if ll_cur is not None and ll_nc is not None and ll_total is None:
        _set("lease_liabilities_mn", ll_cur + ll_nc,
             min(confidence.get("lease_liabilities_current_mn", 0.8), confidence.get("lease_liabilities_noncurrent_mn", 0.8)),
             f"Computed lease_liabilities_mn = {ll_cur} + {ll_nc} = {ll_cur + ll_nc}")
    elif ll_total is not None and ll_cur is not None and ll_nc is None:
        computed_nc = ll_total - ll_cur
        if computed_nc >= 0:
            _set("lease_liabilities_noncurrent_mn", computed_nc,
                 min(confidence.get("lease_liabilities_mn", 0.8), confidence.get("lease_liabilities_current_mn", 0.8)),
                 f"Computed lease_liabilities_noncurrent_mn = {ll_total} - {ll_cur} = {computed_nc}")
    elif ll_total is not None and ll_nc is not None and ll_cur is None:
        computed_cur = ll_total - ll_nc
        if computed_cur >= 0:
            _set("lease_liabilities_current_mn", computed_cur,
                 min(confidence.get("lease_liabilities_mn", 0.8), confidence.get("lease_liabilities_noncurrent_mn", 0.8)),
                 f"Computed lease_liabilities_current_mn = {ll_total} - {ll_nc} = {computed_cur}")

    # ── Backward compat: map old capital_leases_mn to lease_liabilities_mn ──
    if _get("capital_leases_mn") is not None and _get("lease_liabilities_mn") is None:
        _set("lease_liabilities_mn", fields["capital_leases_mn"],
             confidence.get("capital_leases_mn", 0.8),
             f"Mapped capital_leases_mn → lease_liabilities_mn = {fields['capital_leases_mn']}")

    # ── EBIT fallback computation ──
    ebit = _get("ebit_mn")
    ebitda = _get("ebitda_mn")
    dep_total = _get("depreciation_mn") or 0
    amort = _get("amortization_mn") or 0
    revenue = _get("revenue_mn")
    opex = _get("operating_expenses_mn")

    if ebit is None:
        # Try EBITDA - D&A first (most reliable)
        if ebitda is not None:
            calc_ebit = ebitda - dep_total - amort
            _set("ebit_mn", round(calc_ebit, 1),
                 confidence.get("ebitda_mn", 0.8) * 0.95,
                 f"Computed ebit_mn = EBITDA({ebitda}) - D&A({dep_total + amort}) = {round(calc_ebit, 1)}")
        # Try Revenue - OpEx - D&A
        elif revenue is not None and opex is not None:
            calc_ebit = revenue - opex - dep_total - amort
            _set("ebit_mn", round(calc_ebit, 1),
                 min(confidence.get("revenue_mn", 0.8), confidence.get("operating_expenses_mn", 0.8)) * 0.9,
                 f"Computed ebit_mn = Revenue({revenue}) - OpEx({opex}) - D&A({dep_total + amort}) = {round(calc_ebit, 1)}")

    return notes


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
                timeout=90.0,  # 90 second timeout per API call (large prompts ~15k tokens need more time)
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

    # Key fields that a well-extracted financial statement should have
    _CORE_FIELDS = {
        "revenue_mn", "ebit_mn", "depreciation_mn", "cash_mn",
        "total_equity_mn", "cfo_mn", "capex_mn", "assets_current_mn",
        "interest_expense_mn", "lease_liabilities_mn",
    }
    _MIN_FIELDS_THRESHOLD = 10  # Retry if fewer than this many fields extracted

    table_text = _build_table_text(tables)
    relevant_text = _extract_relevant_sections(raw_text, max_chars=50000)
    prompt = _build_extraction_prompt(relevant_text, table_text)

    try:
        logger.debug("Calling Claude API for financial field extraction")
        response_text = _call_claude_with_retry(
            client,
            model="claude-sonnet-4-6",
            max_tokens=4096,
            prompt=prompt,
            max_retries=2,
        )

        result = _extract_json_from_response(response_text)
        fields, confidence, errors = _validate_and_clean_response(result)

        # ── Compute IFRS-16 totals from components (or back-fill components from totals) ──
        ifrs16_notes = _compute_ifrs16_totals(fields, confidence)
        if ifrs16_notes:
            logger.info(f"IFRS-16 computed fields: {'; '.join(ifrs16_notes)}")

        # ── Field completeness check: retry with expanded context if too few fields ──
        extracted_core = set(fields.keys()) & _CORE_FIELDS
        if len(fields) < _MIN_FIELDS_THRESHOLD or len(extracted_core) < 5:
            logger.warning(
                f"Incomplete extraction: {len(fields)} fields ({len(extracted_core)} core). "
                f"Retrying with expanded context."
            )
            # Retry with full text (up to 45k chars) to capture anything missed
            expanded_text = _extract_relevant_sections(raw_text, max_chars=60000)
            if len(expanded_text) > len(relevant_text) + 1000:
                retry_prompt = _build_extraction_prompt(expanded_text, table_text)
                retry_response = _call_claude_with_retry(
                    client,
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    prompt=retry_prompt,
                    max_retries=1,
                )
                retry_result = _extract_json_from_response(retry_response)
                retry_fields, retry_confidence, retry_errors = _validate_and_clean_response(retry_result)

                # Compute IFRS-16 totals for retry result too
                _compute_ifrs16_totals(retry_fields, retry_confidence)

                # Use retry result if it found more fields
                if len(retry_fields) > len(fields):
                    logger.info(
                        f"Retry improved extraction: {len(fields)} → {len(retry_fields)} fields"
                    )
                    fields = retry_fields
                    confidence = retry_confidence
                    errors = retry_errors
                    result = retry_result
                else:
                    logger.info("Retry did not improve extraction, keeping original")

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

    # 4. EBIT cross-validation: Revenue - OpEx - D&A should ≈ EBIT (excluding impairments)
    ebit = _get("ebit_mn")
    dep = _get("depreciation_mn") or 0
    amort = _get("amortization_mn") or 0
    revenue = _get("revenue_mn")
    opex = _get("operating_expenses_mn")
    ebitda = _get("ebitda_mn")
    impairment = _get("impairment_mn") or 0

    # 4a. If we have Revenue and OpEx, cross-check EBIT = Revenue - OpEx - D&A
    if ebit is not None and revenue is not None and opex is not None:
        # OpEx is stored as positive, so subtract it
        calc_ebit = revenue - opex - dep - amort
        _check("EBIT should ≈ Revenue - OpEx - D&A (ex-impairment)", ebit, round(calc_ebit, 1), 10, "ebit_mn")

    # 4b. If we have EBITDA, cross-check EBIT = EBITDA - D&A
    if ebit is not None and ebitda is not None:
        calc_ebit_from_ebitda = ebitda - dep - amort
        _check("EBIT should ≈ EBITDA - D&A", ebit, round(calc_ebit_from_ebitda, 1), 10, "ebit_mn")

    # 4c. Impairment sanity: if impairment exists, it should be < revenue
    if impairment > 0 and revenue is not None and revenue > 0:
        if impairment > revenue:
            issues.append({
                "check": "impairment should be < revenue",
                "expected": revenue,
                "actual": impairment,
                "diff": round(impairment - revenue, 1),
                "pct_off": round((impairment / revenue) * 100, 1),
                "severity": "warning",
                "field_hint": "impairment_mn",
            })

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

    # ═══ IFRS-16 LEASE CROSS-VALIDATION ═══

    # 9. Depreciation completeness: total = PPE + ROU
    dep_total = _get("depreciation_mn")
    dep_ppe = _get("depreciation_ppe_mn")
    dep_rou = _get("depreciation_rou_mn")
    if dep_total is not None and dep_ppe is not None and dep_rou is not None:
        calc_dep = dep_ppe + dep_rou
        _check("depreciation_mn should = depreciation_ppe_mn + depreciation_rou_mn",
               dep_total, calc_dep, 3, "depreciation_mn")

    # 10. Interest completeness: total = debt + lease
    int_total = _get("interest_expense_mn")
    int_debt = _get("interest_debt_mn")
    int_lease = _get("interest_lease_mn")
    if int_total is not None and int_debt is not None and int_lease is not None:
        calc_int = int_debt + int_lease
        _check("interest_expense_mn should = interest_debt_mn + interest_lease_mn",
               int_total, calc_int, 3, "interest_expense_mn")

    # 11. Lease consistency: if lease interest > 0, then ROU depreciation should > 0
    if int_lease is not None and int_lease > 0 and dep_rou is not None and dep_rou == 0:
        issues.append({
            "check": "lease interest > 0 but ROU depreciation = 0 (IFRS-16 inconsistency)",
            "expected": "depreciation_rou_mn > 0",
            "actual": 0,
            "diff": 0,
            "pct_off": 100,
            "severity": "warning",
            "field_hint": "depreciation_rou_mn",
        })
    if dep_rou is not None and dep_rou > 0 and int_lease is not None and int_lease == 0:
        issues.append({
            "check": "ROU depreciation > 0 but lease interest = 0 (IFRS-16 inconsistency)",
            "expected": "interest_lease_mn > 0",
            "actual": 0,
            "diff": 0,
            "pct_off": 100,
            "severity": "warning",
            "field_hint": "interest_lease_mn",
        })

    # 12. Balance sheet lease consistency: if lease liabilities > 0, then ROU assets > 0
    ll = _get("lease_liabilities_mn")
    rou = _get("rou_assets_mn")
    if ll is not None and ll > 0 and rou is not None and rou == 0:
        issues.append({
            "check": "lease liabilities > 0 but ROU assets = 0 (IFRS-16 inconsistency)",
            "expected": "rou_assets_mn > 0",
            "actual": 0,
            "diff": 0,
            "pct_off": 100,
            "severity": "warning",
            "field_hint": "rou_assets_mn",
        })
    if rou is not None and rou > 0 and ll is not None and ll == 0:
        issues.append({
            "check": "ROU assets > 0 but lease liabilities = 0 (IFRS-16 inconsistency)",
            "expected": "lease_liabilities_mn > 0",
            "actual": 0,
            "diff": 0,
            "pct_off": 100,
            "severity": "warning",
            "field_hint": "lease_liabilities_mn",
        })

    # 13. Lease liabilities = current + non-current
    ll_cur = _get("lease_liabilities_current_mn")
    ll_nc = _get("lease_liabilities_noncurrent_mn")
    if ll is not None and ll_cur is not None and ll_nc is not None:
        calc_ll = ll_cur + ll_nc
        _check("lease_liabilities_mn should = current + non-current",
               ll, calc_ll, 3, "lease_liabilities_mn")

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

    return f"""You are a financial data extraction expert specialising in New Zealand IFRS-16 annual reports. A previous extraction pass had validation errors on specific fields. Re-extract ONLY the flagged fields below, being extra careful.

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

IFRS-16 LEASE RULES:
- depreciation_mn MUST = depreciation_ppe_mn + depreciation_rou_mn
- interest_expense_mn MUST = interest_debt_mn + interest_lease_mn
- lease_liabilities_mn MUST = lease_liabilities_current_mn + lease_liabilities_noncurrent_mn
- If lease interest exists, ROU depreciation must also exist (and vice versa)
- If lease liabilities exist, ROU assets must also exist (and vice versa)

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
            relevant_text = _extract_relevant_sections(raw_text, max_chars=50000)
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
