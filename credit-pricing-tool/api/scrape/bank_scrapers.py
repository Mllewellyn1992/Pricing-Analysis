"""
Per-bank rate scrapers.

Each bank has its own scraper function that returns a list of BankProduct dicts.
Products are tracked by their EXACT name as shown on the bank's website.

Sources:
- ASB: Public REST API (api.asb.co.nz/public/v1/interest-rates)
- BNZ: Embedded JSON in page data-parameters attributes
- ANZ: interest.co.nz aggregation (individual pages don't publish rates)
- Westpac: interest.co.nz aggregation (individual pages don't publish rates)
- Kiwibank: interest.co.nz aggregation (individual pages don't publish rates)
- interest.co.nz: Cross-bank business base rates table
- OCR: global-rates.com (RBNZ Official Cash Rate)
"""

import re
import json
import csv
import io
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


# ─── Data Model ────────────────────────────────────────────────────────────────

def _product(
    bank: str,
    product_name: str,
    rate_pct: float,
    rate_type: str = "base_rate",
    category: str = "business_lending",
    source_url: str = "",
) -> Dict[str, Any]:
    """Create a standardised product rate dict."""
    return {
        "bank": bank,
        "product_name": product_name,
        "rate_pct": round(rate_pct, 4),
        "rate_type": rate_type,           # base_rate, overdraft, indicator, floating, etc.
        "category": category,             # business_lending, rural, housing, overdraft, etc.
        "source_url": source_url,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }


# ─── ASB ───────────────────────────────────────────────────────────────────────

ASB_API_URL = "https://api.asb.co.nz/public/v1/interest-rates"
ASB_API_KEY = "l7xx93b1538ae6564c3fa170f899b645c605"
ASB_SOURCE = "https://www.asb.co.nz/business-loans/interest-rates-fees.html"

# ASB products we want (productGroup, productName, category, display_name)
ASB_PRODUCTS = [
    ("Lending", "Business Base", "business_lending", "Business base rate"),
    ("Lending", "Rural Base", "rural", "Rural base rate"),
    ("Lending", "Floating Base Rate", "business_lending", "Floating base rate"),
    ("Lending", "Housing Variable", "housing", "Housing Variable"),
    ("Lending", "Flexible Finance Facility", "business_lending", "Flexible Finance Facility"),
    ("Lending", "Societies Clubs and Churches", "business_lending", "Societies Clubs and Churches"),
]


def scrape_asb() -> List[Dict[str, Any]]:
    """
    Fetch ASB business lending rates from their public API.

    ASB exposes a REST API that the website itself calls to populate rate tables.
    We query it directly for each business lending product.
    """
    products = []

    try:
        headers = {
            **HEADERS,
            "apikey": ASB_API_KEY,
            "Accept": "application/json",
            "Referer": "https://www.asb.co.nz/",
        }

        # Fetch all lending rates in one call
        resp = httpx.get(
            ASB_API_URL,
            headers=headers,
            params={"productGroup": "Lending"},
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.warning(f"ASB API returned {resp.status_code}")
            return []

        data = resp.json()
        api_rates = {}
        for item in data.get("value", []):
            name = item.get("productName", "")
            rate = item.get("interestRate")
            rate_type = item.get("type", "Standard")
            if name and rate is not None and rate_type == "Standard":
                api_rates[name] = rate

        # Map to our products
        for pg, pn, category, display_name in ASB_PRODUCTS:
            if pn in api_rates:
                rate_type = "overdraft" if "overdraft" in display_name.lower() else "base_rate"
                products.append(_product(
                    bank="ASB",
                    product_name=display_name,
                    rate_pct=api_rates[pn],
                    rate_type=rate_type,
                    category=category,
                    source_url=ASB_SOURCE,
                ))

        # Also try to get Corporate Indicator and Special Purpose rates
        # (these use different productGroup values)
        for pg_name, display, cat in [
            ("Corporate Indicator Rate", "Corporate Indicator rate", "corporate"),
            ("Special Purpose Base Rate", "Special Purpose base rate", "business_lending"),
        ]:
            try:
                r = httpx.get(
                    ASB_API_URL,
                    headers=headers,
                    params={"productGroup": pg_name},
                    timeout=REQUEST_TIMEOUT,
                )
                if r.status_code == 200:
                    vals = r.json().get("value", [])
                    if vals:
                        products.append(_product(
                            bank="ASB",
                            product_name=display,
                            rate_pct=vals[0].get("interestRate", 0),
                            rate_type="indicator" if "indicator" in display.lower() else "base_rate",
                            category=cat,
                            source_url=ASB_SOURCE,
                        ))
            except Exception:
                pass

        # Unarranged overdraft rate (fixed, not from API)
        products.append(_product(
            bank="ASB",
            product_name="Unarranged overdraft interest rate",
            rate_pct=22.50,
            rate_type="overdraft",
            category="overdraft",
            source_url=ASB_SOURCE,
        ))

        logger.info(f"ASB: scraped {len(products)} products")
        return products

    except Exception as e:
        logger.error(f"ASB scraper failed: {e}")
        return []


# ─── BNZ ───────────────────────────────────────────────────────────────────────

BNZ_SOURCE = "https://www.bnz.co.nz/business-banking/loans-and-finance/interest-rates-and-fees"


def scrape_bnz() -> List[Dict[str, Any]]:
    """
    Fetch BNZ business lending rates from embedded page data.

    BNZ embeds rate data in `data-parameters` JSON attributes on div elements.
    Some rates are static (in the JSON), others are loaded dynamically via
    <personalloanrate> custom elements (we can't get those without JS).
    """
    products = []

    try:
        resp = httpx.get(BNZ_SOURCE, headers=HEADERS, follow_redirects=True, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"BNZ page returned {resp.status_code}")
            return []

        html = resp.text

        # Extract data-parameters JSON blobs
        params_raw = re.findall(r'data-parameters="({.*?})">', html, re.DOTALL)

        for raw in params_raw:
            # Unescape HTML entities
            decoded = (
                raw.replace("&quot;", '"')
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&amp;", "&")
            )

            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                continue

            if "table" not in data:
                continue

            title = data.get("title", "")
            table = data["table"]

            # Skip header row (index 0), process data rows
            for row in table[1:]:
                if len(row) < 2:
                    continue

                product_name = re.sub(r"<[^>]+>", "", str(row[0])).strip()
                rate_str = re.sub(r"<[^>]+>", "", str(row[1])).strip()

                # Extract numeric rate from strings like "10.95 + margin*"
                rate_match = re.search(r"(\d+\.?\d*)", rate_str)
                if not rate_match:
                    # Dynamic rate (personalloanrate tag) - skip for now
                    logger.debug(f"BNZ: skipping dynamic rate for {product_name}")
                    continue

                rate = float(rate_match.group(1))
                if rate < 0.5 or rate > 25:
                    continue

                # Classify
                lower_name = product_name.lower()
                if "overdraft" in lower_name:
                    category = "overdraft"
                    rate_type = "overdraft"
                elif "cashflow" in lower_name or "invoice" in lower_name:
                    category = "invoice_finance"
                    rate_type = "base_rate"
                elif "project" in lower_name or "revolving" in lower_name:
                    category = "revolving_credit"
                    rate_type = "base_rate"
                elif "term" in lower_name:
                    category = "term_loan"
                    rate_type = "base_rate"
                else:
                    category = "business_lending"
                    rate_type = "base_rate"

                products.append(_product(
                    bank="BNZ",
                    product_name=product_name,
                    rate_pct=rate,
                    rate_type=rate_type,
                    category=category,
                    source_url=BNZ_SOURCE,
                ))

        logger.info(f"BNZ: scraped {len(products)} products")
        return products

    except Exception as e:
        logger.error(f"BNZ scraper failed: {e}")
        return []


# ─── interest.co.nz (ANZ, Westpac, Kiwibank + cross-bank) ─────────────────────

INTEREST_NZ_URL = "https://www.interest.co.nz/borrowing/business-base-rates"


def scrape_interest_co_nz_products() -> List[Dict[str, Any]]:
    """
    Scrape individual product rates from interest.co.nz business base rates table.

    This provides rates for ALL banks including ANZ, Westpac, Kiwibank
    which don't publish base rates on their own websites.

    Returns one product entry per row in the table.
    """
    products = []

    try:
        resp = httpx.get(INTEREST_NZ_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"interest.co.nz returned {resp.status_code}")
            return []

        html = resp.text
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)

        current_bank = None

        for row_html in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)
            if len(cells) < 5:
                continue

            institution = re.sub(r"<[^>]+>", "", cells[0]).strip()
            product = re.sub(r"<[^>]+>", "", cells[1]).strip()
            rate_text = re.sub(r"<[^>]+>", "", cells[4]).strip()

            rate_match = re.search(r"(\d+\.?\d*)", rate_text)
            if not rate_match:
                continue

            rate = float(rate_match.group(1))
            if not (1.0 <= rate <= 25.0):
                continue

            if institution:
                current_bank = institution
            if not current_bank:
                continue

            # Classify product
            lower_prod = product.lower()
            if "corporate" in lower_prod or "indicator" in lower_prod:
                category = "corporate"
                rate_type = "indicator"
            elif "working capital" in lower_prod:
                category = "working_capital"
                rate_type = "base_rate"
            elif "overdraft" in lower_prod:
                category = "overdraft"
                rate_type = "overdraft"
            elif "rural" in lower_prod:
                category = "rural"
                rate_type = "base_rate"
            elif "home equity" in lower_prod or "housing" in lower_prod:
                category = "housing"
                rate_type = "base_rate"
            elif "business lending" in lower_prod:
                category = "business_lending"
                rate_type = "base_rate"
            else:
                category = "business_lending"
                rate_type = "base_rate"

            products.append(_product(
                bank=current_bank,
                product_name=product,
                rate_pct=rate,
                rate_type=rate_type,
                category=category,
                source_url=INTEREST_NZ_URL,
            ))

        logger.info(f"interest.co.nz: scraped {len(products)} products")
        return products

    except Exception as e:
        logger.error(f"interest.co.nz scraper failed: {e}")
        return []


# ─── OCR (Official Cash Rate) ─────────────────────────────────────────────────

OCR_URL = "https://www.global-rates.com/en/interest-rates/central-banks/23/new-zealand-official-cash-rate/"


def scrape_ocr() -> Optional[Dict[str, Any]]:
    """
    Fetch the current RBNZ Official Cash Rate.

    Uses global-rates.com which publishes a clean table of OCR decisions.
    """
    try:
        resp = httpx.get(OCR_URL, headers=HEADERS, follow_redirects=True, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"OCR page returned {resp.status_code}")
            return None

        html = resp.text

        # Find the first data row in the rate table (most recent)
        table_match = re.search(r"<table.*?>(.*?)</table>", html, re.DOTALL | re.IGNORECASE)
        if not table_match:
            return None

        rows = re.findall(r"<tr.*?>(.*?)</tr>", table_match.group(1), re.DOTALL)
        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            if len(cells) >= 2:
                date_str = re.sub(r"<[^>]+>", "", cells[0]).strip()
                rate_str = re.sub(r"<[^>]+>", "", cells[1]).strip().replace("%", "").strip()
                try:
                    rate = float(rate_str)
                    return {
                        "rate_name": "Official Cash Rate (OCR)",
                        "rate_pct": rate,
                        "decision_date": date_str,
                        "source": "RBNZ via global-rates.com",
                        "scraped_at": datetime.utcnow().isoformat() + "Z",
                    }
                except ValueError:
                    continue

        return None

    except Exception as e:
        logger.error(f"OCR scraper failed: {e}")
        return None


# ─── BKBM & Swap Rates ───────────────────────────────────────────────────────
#
# Primary: interest.co.nz swap rates page (reliable, no Cloudflare block)
# Fallback: RBNZ B1 CSV (often blocked by Cloudflare 403)
#

INTEREST_NZ_SWAP_URL = "https://www.interest.co.nz/charts/interest-rates/swap-rates"

SWAP_TENOR_SHORT = {
    "1 year": "1Y", "2 year": "2Y", "3 year": "3Y",
    "4 year": "4Y", "5 year": "5Y", "7 year": "7Y", "10 year": "10Y",
    "1 yr": "1Y", "2 yr": "2Y", "3 yr": "3Y",
    "4 yr": "4Y", "5 yr": "5Y", "7 yr": "7Y", "10 yr": "10Y",
}

BKBM_TENOR_SHORT = {
    "1 month": "1M", "2 month": "2M", "3 month": "3M", "6 month": "6M",
    "1 mth": "1M", "2 mth": "2M", "3 mth": "3M", "6 mth": "6M",
    "30 day": "1M", "60 day": "2M", "90 day": "3M", "180 day": "6M",
}


def scrape_bkbm_swap_rates() -> List[Dict[str, Any]]:
    """
    Fetch the latest BKBM and swap rates.

    Note: The primary source (RBNZ B1 CSV) is blocked by Cloudflare, and
    interest.co.nz renders chart data via JavaScript (not scrapable server-side).

    This function currently cannot reliably fetch live BKBM/swap rates.
    Wholesale rate data must be entered manually or sourced from a paid API.

    The rates will be stored in Supabase once entered and tracked over time.
    """
    rates = []
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Attempt 1: Try RBNZ CSV (usually blocked by Cloudflare)
    try:
        rbnz_url = "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b1/hb1-daily.csv"
        resp = httpx.get(
            rbnz_url,
            headers={
                **HEADERS,
                "Accept": "text/csv,application/csv,*/*",
                "Referer": "https://www.rbnz.govt.nz/statistics",
            },
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code == 200 and "date" in resp.text[:200].lower():
            rates = _parse_rbnz_csv(resp.text, today)
            if rates:
                logger.info(f"BKBM/Swap: scraped {len(rates)} rates from RBNZ CSV")
                return rates

        logger.info(f"RBNZ CSV returned status {resp.status_code} — trying fallback")

    except Exception as e:
        logger.info(f"RBNZ CSV unavailable: {e}")

    # If we get here, no source worked
    logger.info("BKBM/swap rates: no accessible source available (RBNZ blocked by Cloudflare)")
    return rates


def _parse_rbnz_csv(csv_text: str, today: str) -> List[Dict[str, Any]]:
    """Parse RBNZ B1 CSV if we manage to download it."""
    rates = []

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = [row for row in reader if row]
        if not rows:
            return rates

        latest_row = rows[-1]

        # Find date column
        date_str = today
        for key in latest_row.keys():
            if key.lower().strip() in ["date", "dates", "series id"]:
                date_str = latest_row[key].strip() or today
                break

        # Extract rates by column name patterns
        for key, value in latest_row.items():
            key_lower = key.lower().strip()
            try:
                rate = float(value.strip())
            except (ValueError, AttributeError):
                continue

            if rate < 0.1 or rate > 15.0:
                continue

            # BKBM rates
            for tenor_key, tenor_short in BKBM_TENOR_SHORT.items():
                if tenor_key in key_lower and ("bkbm" in key_lower or "bank bill" in key_lower):
                    rates.append({
                        "rate_name": f"BKBM {tenor_short}",
                        "rate_pct": round(rate, 4),
                        "tenor": tenor_short,
                        "rate_type": "bkbm",
                        "date": date_str,
                        "source": "RBNZ B1 daily series",
                    })
                    break

            # Swap rates
            for tenor_key, tenor_short in SWAP_TENOR_SHORT.items():
                if tenor_key in key_lower and "swap" in key_lower:
                    rates.append({
                        "rate_name": f"Swap {tenor_short}",
                        "rate_pct": round(rate, 4),
                        "tenor": tenor_short,
                        "rate_type": "swap",
                        "date": date_str,
                        "source": "RBNZ B1 daily series",
                    })
                    break

    except Exception as e:
        logger.error(f"Failed to parse RBNZ CSV: {e}")

    return rates


def scrape_bkbm_swap_history(days: int = 90) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get BKBM and swap rate history.

    Note: interest.co.nz only provides current rates, not historical.
    Historical data is built up from daily scrapes stored in Supabase.
    This function now returns only the current snapshot as a single data point.
    Full history is served from Supabase via the rate_store module.
    """
    history = {"bkbm": [], "swap": []}
    today = datetime.utcnow().strftime("%Y-%m-%d")

    rates = scrape_bkbm_swap_rates()
    if not rates:
        return history

    # Build current snapshot entries
    bkbm_entry = {"date": today}
    swap_entry = {"date": today}

    for rate in rates:
        if rate["rate_type"] == "bkbm":
            bkbm_entry[rate["tenor"]] = rate["rate_pct"]
        elif rate["rate_type"] == "swap":
            swap_entry[rate["tenor"]] = rate["rate_pct"]

    if len(bkbm_entry) > 1:
        history["bkbm"].append(bkbm_entry)
    if len(swap_entry) > 1:
        history["swap"].append(swap_entry)

    return history


# ─── Master Scraper ────────────────────────────────────────────────────────────

def scrape_all_bank_products() -> Dict[str, Any]:
    """
    Run all scrapers and return a consolidated result.

    Returns:
        {
            "products": [list of all product dicts],
            "ocr": {OCR rate dict or None},
            "bkbm_swap_rates": [list of swap rate dicts],
            "banks_scraped": ["ASB", "BNZ", ...],
            "scraped_at": "ISO timestamp",
            "errors": ["error messages"],
        }
    """
    all_products = []
    errors = []
    banks_scraped = set()

    # 1. ASB (direct API)
    try:
        asb = scrape_asb()
        all_products.extend(asb)
        if asb:
            banks_scraped.add("ASB")
    except Exception as e:
        errors.append(f"ASB: {e}")

    # 2. BNZ (embedded page data)
    try:
        bnz = scrape_bnz()
        all_products.extend(bnz)
        if bnz:
            banks_scraped.add("BNZ")
    except Exception as e:
        errors.append(f"BNZ: {e}")

    # 3. interest.co.nz (all banks, especially ANZ/Westpac/Kiwibank)
    try:
        inz = scrape_interest_co_nz_products()
        all_products.extend(inz)
        for p in inz:
            banks_scraped.add(p["bank"])
    except Exception as e:
        errors.append(f"interest.co.nz: {e}")

    # 4. OCR
    ocr = None
    try:
        ocr = scrape_ocr()
    except Exception as e:
        errors.append(f"OCR: {e}")

    # 5. BKBM swap rates (best effort)
    bkbm = []
    bkbm_history = {}
    try:
        bkbm = scrape_bkbm_swap_rates()
        bkbm_history = scrape_bkbm_swap_history()
    except Exception as e:
        errors.append(f"BKBM: {e}")

    result = {
        "products": all_products,
        "ocr": ocr,
        "bkbm_swap_rates": bkbm,
        "bkbm_swap_history": bkbm_history,
        "banks_scraped": sorted(banks_scraped),
        "product_count": len(all_products),
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "errors": errors,
    }

    logger.info(
        f"Scraped {len(all_products)} products from {len(banks_scraped)} banks, "
        f"OCR={'yes' if ocr else 'no'}, BKBM={len(bkbm)} rates, "
        f"errors={len(errors)}"
    )

    return result
