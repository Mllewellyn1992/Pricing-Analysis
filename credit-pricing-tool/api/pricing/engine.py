"""
Pricing computation module
Loads pricing matrix and computes spread and rate expectations.
Uses live scraped base rates from interest.co.nz when available.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Any
import yaml

from api.scrape.scraper import get_cached_rates, compute_market_average

logger = logging.getLogger(__name__)

# Static fallback — only used if scraper AND cache AND defaults all fail
_FALLBACK_BASE_RATES = {
    "corporate": 5.50,
    "working_capital": 7.25,
}


def load_pricing_matrix() -> Dict[str, Any]:
    """
    Load pricing matrix from YAML.
    Path: engines/configs/moodys/pricing_matrix.yaml

    Returns:
        dict with structure:
        {
            "id": "...",
            "name": "...",
            "tenors": {
                "1": { "AAA": {min_bps, max_bps}, ... },
                "2": { ... },
                ...
            }
        }
    """
    config_path = (
        Path(__file__).resolve().parent.parent.parent
        / "engines" / "configs" / "moodys" / "pricing_matrix.yaml"
    )

    if not config_path.exists():
        raise FileNotFoundError(f"Pricing matrix not found at {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Invalid pricing matrix YAML structure")

    return data


def lookup_spread(
    rating: str,
    tenor: int,
    matrix: Dict[str, Any]
) -> Dict[str, float]:
    """
    Look up spread for a given rating and tenor in the pricing matrix.

    Args:
        rating: S&P rating (e.g., "BBB", "A+")
        tenor: Years (1-5)
        matrix: Pricing matrix dict from load_pricing_matrix()

    Returns:
        dict with:
        {
            "min_bps": float,
            "max_bps": float,
            "mid_bps": float
        }

    Raises:
        ValueError if rating or tenor not found in matrix
    """
    tenor_str = str(tenor)
    tenors = matrix.get("tenors", {})

    if tenor_str not in tenors:
        raise ValueError(f"Tenor {tenor} not found in pricing matrix")

    tenor_data = tenors[tenor_str]

    if rating not in tenor_data:
        raise ValueError(f"Rating {rating} not found for tenor {tenor}")

    spread_data = tenor_data[rating]
    min_bps = float(spread_data.get("min_bps", 0.0))
    max_bps = float(spread_data.get("max_bps", 0.0))
    mid_bps = (min_bps + max_bps) / 2.0

    return {
        "min_bps": min_bps,
        "max_bps": max_bps,
        "mid_bps": mid_bps,
    }


def compute_expected_rate(spread_bps: float, base_rate_pct: float) -> float:
    """
    Compute expected rate from base rate and spread.

    Args:
        spread_bps: Spread in basis points (e.g., 120 for 1.20%)
        base_rate_pct: Base rate as percentage (e.g., 5.50 for 5.50%)

    Returns:
        Expected rate as percentage (e.g., 6.70 for 6.70%)
    """
    spread_pct = spread_bps / 100.0
    return base_rate_pct + spread_pct


def get_live_base_rates() -> Dict[str, float]:
    """
    Fetch current NZ base rates from live scraper data.

    Computes market average across all banks for corporate and working_capital.
    Falls back to static defaults if scraper is unavailable.

    Returns:
        Dict with "corporate" and "working_capital" keys, values as percentages
    """
    try:
        rates = get_cached_rates()
        averages = compute_market_average(rates)

        live_rates = {}

        avg_corporate = averages.get("average_corporate_rate", 0.0)
        avg_wc = averages.get("average_working_capital_rate", 0.0)

        if avg_corporate > 0:
            live_rates["corporate"] = round(avg_corporate, 2)
        else:
            live_rates["corporate"] = _FALLBACK_BASE_RATES["corporate"]

        if avg_wc > 0:
            live_rates["working_capital"] = round(avg_wc, 2)
        else:
            live_rates["working_capital"] = _FALLBACK_BASE_RATES["working_capital"]

        logger.info(f"Live base rates: {live_rates}")
        return live_rates

    except Exception as e:
        logger.error(f"Failed to get live rates, using fallback: {e}")
        return _FALLBACK_BASE_RATES.copy()


def get_base_rate(
    facility_type: str,
    custom_rates: Optional[Dict[str, float]] = None
) -> float:
    """
    Get the NZ base rate for a facility type.

    Uses live scraped rates by default. If custom_rates provided, uses those instead.

    Args:
        facility_type: "corporate" or "working_capital"
        custom_rates: Optional override dict {facility_type: rate_pct}

    Returns:
        Base rate as percentage (e.g., 5.50)

    Raises:
        ValueError if facility_type not recognized
    """
    if custom_rates:
        rates = custom_rates
    else:
        rates = get_live_base_rates()

    # Map "working-capital" to "working_capital" for API compatibility
    normalized_type = facility_type.replace("-", "_")

    if normalized_type not in rates:
        raise ValueError(
            f"Unknown facility type '{facility_type}'. "
            f"Must be one of: {list(rates.keys())}"
        )

    return rates[normalized_type]


def compute_expected_rate_range(
    spread_min_bps: float,
    spread_max_bps: float,
    base_rate_pct: float
) -> Dict[str, float]:
    """
    Compute expected rate range (min, mid, max) from spread range and base rate.

    Args:
        spread_min_bps: Minimum spread in basis points
        spread_max_bps: Maximum spread in basis points
        base_rate_pct: Base rate as percentage

    Returns:
        dict with:
        {
            "min_rate": float,
            "mid_rate": float,
            "max_rate": float
        }
    """
    min_rate = compute_expected_rate(spread_min_bps, base_rate_pct)
    max_rate = compute_expected_rate(spread_max_bps, base_rate_pct)
    mid_rate = (min_rate + max_rate) / 2.0

    return {
        "min_rate": min_rate,
        "mid_rate": mid_rate,
        "max_rate": max_rate,
    }
