"""
NZ Bank Base Rate Scraper
Fetches current NZ bank base rates from interest.co.nz/borrowing/business-base-rates

This module provides functions to:
- Scrape live rates from interest.co.nz
- Cache rates for 24 hours to reduce load
- Fall back to hardcoded defaults if scraping fails
- Compute market average rates
"""

import json
import re
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import httpx

logger = logging.getLogger(__name__)

# Cache file location
CACHE_DIR = Path(__file__).parent
CACHE_FILE = CACHE_DIR / ".rate_cache.json"

# Hardcoded fallback rates (NZD) — approximate as of early 2025
HARDCODED_DEFAULTS = [
    {"bank": "ANZ", "corporate_rate": 4.86, "working_capital_rate": 10.65},
    {"bank": "ASB", "corporate_rate": 5.93, "working_capital_rate": 11.52},
    {"bank": "BNZ", "working_capital_rate": 10.95, "overdraft_rate": 10.95},
    {"bank": "Westpac", "working_capital_rate": 13.95, "overdraft_rate": 13.95},
    {"bank": "Kiwibank", "working_capital_rate": 7.50, "overdraft_rate": 7.50},
]

# Scraping constants
TARGET_URL = "https://www.interest.co.nz/borrowing/business-base-rates"
REQUEST_TIMEOUT = 10  # seconds
CACHE_TTL = 86400  # 24 hours in seconds


def scrape_interest_co_nz() -> Optional[List[Dict[str, Any]]]:
    """
    Fetch and parse NZ bank base rates from interest.co.nz.

    Uses httpx to fetch the page, then extracts rate data from HTML table.
    Handles various HTML format variations gracefully.

    Returns:
        List of dicts with keys: bank, corporate_rate, working_capital_rate,
        overdraft_rate (if available), last_updated
        Returns None if scraping fails.

    Raises:
        No exceptions - logs errors and returns None on failure
    """
    try:
        logger.info(f"Scraping base rates from {TARGET_URL}")

        # Fetch the page
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            response = client.get(
                TARGET_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            response.raise_for_status()

        html = response.text

        # Extract rates table - look for common HTML patterns
        rates = _parse_html_table(html)

        if not rates:
            logger.warning("Could not extract rates from HTML")
            return None

        # Add timestamp
        for rate in rates:
            rate["last_updated"] = datetime.utcnow().isoformat() + "Z"

        logger.info(f"Successfully scraped {len(rates)} banks")
        return rates

    except httpx.RequestError as e:
        logger.error(f"HTTP request failed: {e}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during scraping: {e}")
        return None


def _parse_html_table(html: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse HTML content to extract bank rates from interest.co.nz.

    The table structure on interest.co.nz has:
    - Columns: Institution | Product | Type | Security | Base rate % pa | ...
    - First row for a bank has the bank name in the Institution column
    - Continuation rows (additional products) have an EMPTY Institution cell
    - Each bank may have multiple products (corporate, working capital, overdraft, etc.)

    We classify products into categories based on product name keywords:
    - Corporate: "corporate indicator", "corporate"
    - Working Capital: "working capital", "business lending base"
    - Overdraft: "overdraft", "business overdraft"
    - Rural: "rural" (stored separately)
    - Other: anything else (e.g., "home equity")

    For each bank, we pick the best rate for corporate and working_capital tiers.

    Args:
        html: Raw HTML content

    Returns:
        List of bank rate dicts or None if parsing fails
    """
    # Known NZ banks we care about
    KNOWN_BANKS = {"ANZ", "ASB", "BNZ", "Westpac", "Kiwibank"}

    # Product name -> category mapping (checked in order, first match wins)
    PRODUCT_CATEGORIES = [
        ("corporate indicator", "corporate"),
        ("corporate", "corporate"),
        ("working capital", "working_capital"),
        ("business lending base", "working_capital"),
        ("business overdraft", "overdraft"),
        ("overdraft", "overdraft"),
        ("rural", "rural"),
        ("home equity", "other"),
    ]

    def _classify_product(product_name: str) -> str:
        """Classify a product name into a rate category."""
        lower = product_name.lower()
        for keyword, category in PRODUCT_CATEGORIES:
            if keyword in lower:
                return category
        return "other"

    def _strip_tags(text: str) -> str:
        """Remove HTML tags and decode entities."""
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
        return text.strip()

    try:
        # Extract all <tr> rows from the HTML
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)

        if not rows:
            logger.warning("No table rows found in HTML")
            return None

        # Parse each row into cells, tracking current bank
        current_bank = None
        bank_products: Dict[str, List[Dict[str, Any]]] = {}  # bank -> list of {product, category, rate}

        for row_html in rows:
            # Extract all <td> cells from this row
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)

            if len(cells) < 5:
                # Not a data row (header, spacer, etc.)
                continue

            # Cell 0 = Institution, Cell 1 = Product, Cell 4 = Base rate % pa
            institution_text = _strip_tags(cells[0])
            product_text = _strip_tags(cells[1])

            # Extract base rate from cell 4 (the "Base rate % pa" column)
            rate_text = _strip_tags(cells[4])
            rate_match = re.search(r"([0-9]+\.?[0-9]*)", rate_text)

            if not rate_match:
                continue

            base_rate = float(rate_match.group(1))

            # Validate rate is in reasonable range (1-20%)
            if not (1.0 <= base_rate <= 20.0):
                continue

            # Determine which bank this row belongs to
            if institution_text:
                # Check if this is one of our known banks
                matched_bank = None
                for bank in KNOWN_BANKS:
                    if bank.lower() in institution_text.lower():
                        matched_bank = bank
                        break
                if matched_bank:
                    current_bank = matched_bank
                elif institution_text.strip():
                    # Some other institution we don't track — skip
                    current_bank = None
                    continue
            # If institution_text is empty, this is a continuation row for current_bank

            if current_bank is None:
                continue

            # Classify the product
            category = _classify_product(product_text)

            if current_bank not in bank_products:
                bank_products[current_bank] = []

            bank_products[current_bank].append({
                "product": product_text,
                "category": category,
                "rate": base_rate,
            })

            logger.debug(
                f"Parsed: {current_bank} | {product_text} | {category} | {base_rate}%"
            )

        if not bank_products:
            logger.warning("No bank products extracted from HTML")
            return None

        # Build final rate entries per bank
        rates = []
        for bank, products in bank_products.items():
            entry: Dict[str, Any] = {"bank": bank}

            # Group by category and pick best rate for each
            by_category: Dict[str, List[float]] = {}
            for p in products:
                cat = p["category"]
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(p["rate"])

            # Corporate rate: prefer "corporate", lowest if multiple
            if "corporate" in by_category:
                entry["corporate_rate"] = min(by_category["corporate"])

            # Working capital rate: prefer "working_capital"
            if "working_capital" in by_category:
                entry["working_capital_rate"] = min(by_category["working_capital"])

            # Overdraft rate
            if "overdraft" in by_category:
                entry["overdraft_rate"] = min(by_category["overdraft"])

            # If a bank only has overdraft (like BNZ/Westpac), use it as working_capital too
            if "working_capital_rate" not in entry and "overdraft_rate" in entry:
                entry["working_capital_rate"] = entry["overdraft_rate"]

            # If a bank has no corporate rate, try to infer from other products
            # (some banks might not have a dedicated corporate indicator rate)

            # Store all products for transparency
            entry["products"] = [
                {"name": p["product"], "category": p["category"], "rate": p["rate"]}
                for p in products
            ]

            rates.append(entry)
            logger.info(
                f"{bank}: corporate={entry.get('corporate_rate', 'N/A')}, "
                f"working_capital={entry.get('working_capital_rate', 'N/A')}, "
                f"overdraft={entry.get('overdraft_rate', 'N/A')}"
            )

        return rates if rates else None

    except Exception as e:
        logger.error(f"HTML parsing error: {e}")
        return None


def _read_cache() -> Optional[Dict[str, Any]]:
    """
    Read rates from cache file if it exists and is fresh.

    Returns:
        Cache dict with 'rates' and 'timestamp' or None if cache is missing/stale
    """
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)

        # Check if cache is fresh (within TTL)
        timestamp_str = cache.get("timestamp", "1970-01-01")
        # Handle ISO format with Z suffix
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1]
        cache_time = datetime.fromisoformat(timestamp_str)
        age_seconds = (datetime.utcnow() - cache_time).total_seconds()

        if age_seconds < CACHE_TTL:
            logger.info(f"Using cached rates (age: {age_seconds:.0f}s)")
            return cache

        logger.info(f"Cache expired (age: {age_seconds:.0f}s > {CACHE_TTL}s)")
        return None

    except Exception as e:
        logger.error(f"Error reading cache: {e}")
        return None


def _write_cache(rates: List[Dict[str, Any]]) -> bool:
    """
    Write rates to cache file.

    Args:
        rates: List of rate dicts to cache

    Returns:
        True if successful, False otherwise
    """
    try:
        cache = {
            "rates": rates,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Ensure directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Write with restricted permissions (0600)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)

        CACHE_FILE.chmod(0o600)
        logger.info("Rates cached successfully")
        return True

    except Exception as e:
        logger.error(f"Error writing cache: {e}")
        return False


def get_cached_rates() -> List[Dict[str, Any]]:
    """
    Get current base rates, using cache if available.

    Strategy:
    1. Check if fresh cache exists, return it
    2. Otherwise, attempt live scrape
    3. If scrape succeeds, cache and return it
    4. If scrape fails, try to return stale cache (if any)
    5. Fall back to hardcoded defaults

    Returns:
        List of rate dicts with keys: bank, corporate_rate, working_capital_rate,
        overdraft_rate (if available), last_updated
    """
    # Try cache first (must be fresh)
    cache = _read_cache()
    if cache:
        return cache["rates"]

    # Try live scrape
    scraped_rates = scrape_interest_co_nz()
    if scraped_rates:
        _write_cache(scraped_rates)
        return scraped_rates

    # Try stale cache as fallback
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                logger.warning("Returning stale cached rates (scrape failed)")
                return cache["rates"]
    except Exception as e:
        logger.error(f"Could not read stale cache: {e}")

    # Final fallback: hardcoded defaults
    logger.warning("Using hardcoded default rates (scrape failed, no cache)")
    for rate in HARDCODED_DEFAULTS:
        rate["last_updated"] = datetime.utcnow().isoformat() + "Z"

    return HARDCODED_DEFAULTS


def compute_market_average(rates: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Compute market average rates across all banks.

    Args:
        rates: List of rate dicts

    Returns:
        Dict with average_corporate_rate and average_working_capital_rate
    """
    if not rates:
        return {
            "average_corporate_rate": 0.0,
            "average_working_capital_rate": 0.0,
        }

    corporate_rates = [r.get("corporate_rate", 0) for r in rates if "corporate_rate" in r]
    working_capital_rates = [
        r.get("working_capital_rate", 0) for r in rates if "working_capital_rate" in r
    ]

    return {
        "average_corporate_rate": (
            sum(corporate_rates) / len(corporate_rates) if corporate_rates else 0.0
        ),
        "average_working_capital_rate": (
            sum(working_capital_rates) / len(working_capital_rates)
            if working_capital_rates
            else 0.0
        ),
        "bank_count": len(rates),
    }


def force_refresh() -> Dict[str, Any]:
    """
    Force a fresh scrape, bypassing cache.

    Returns:
        Dict with success status, rates (if successful), and message
    """
    logger.info("Force refresh requested")

    scraped_rates = scrape_interest_co_nz()

    if scraped_rates:
        _write_cache(scraped_rates)
        return {
            "success": True,
            "rates": scraped_rates,
            "message": f"Successfully refreshed {len(scraped_rates)} bank rates",
        }

    # Try stale cache
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                return {
                    "success": False,
                    "rates": cache["rates"],
                    "message": "Scrape failed, returned stale cache",
                }
    except Exception:
        pass

    return {
        "success": False,
        "rates": HARDCODED_DEFAULTS,
        "message": "Scrape failed, using hardcoded defaults",
    }
