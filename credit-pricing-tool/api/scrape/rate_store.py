"""
Rate history storage.

Stores individual product rates over time in a local JSON file.
Each scrape appends a timestamped snapshot, enabling historical tracking.

Storage format:
{
    "snapshots": [
        {
            "scraped_at": "2026-03-11T08:00:00Z",
            "products": [...],
            "ocr": {...},
        },
        ...
    ]
}

The file grows over time. We keep the last 365 days of snapshots
and prune older entries on each write.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

STORE_DIR = Path(__file__).parent
STORE_FILE = STORE_DIR / ".rate_history.json"
MAX_AGE_DAYS = 365  # Keep 1 year of history


def _read_store() -> Dict[str, Any]:
    """Read the rate store file."""
    if not STORE_FILE.exists():
        return {"snapshots": []}

    try:
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read rate store: {e}")
        return {"snapshots": []}


def _write_store(data: Dict[str, Any]) -> bool:
    """Write the rate store file."""
    try:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        with open(STORE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to write rate store: {e}")
        return False


def save_snapshot(scrape_result: Dict[str, Any]) -> bool:
    """
    Save a scrape result as a new snapshot.

    Args:
        scrape_result: Output from scrape_all_bank_products()

    Returns:
        True if saved successfully
    """
    store = _read_store()

    snapshot = {
        "scraped_at": scrape_result.get("scraped_at", datetime.utcnow().isoformat() + "Z"),
        "products": scrape_result.get("products", []),
        "ocr": scrape_result.get("ocr"),
        "bkbm_swap_rates": scrape_result.get("bkbm_swap_rates", []),
        "banks_scraped": scrape_result.get("banks_scraped", []),
        "product_count": scrape_result.get("product_count", 0),
    }

    store["snapshots"].append(snapshot)

    # Prune old snapshots
    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)
    cutoff_str = cutoff.isoformat() + "Z"
    store["snapshots"] = [
        s for s in store["snapshots"]
        if s.get("scraped_at", "") >= cutoff_str
    ]

    return _write_store(store)


def get_latest_snapshot() -> Optional[Dict[str, Any]]:
    """Get the most recent snapshot."""
    store = _read_store()
    snapshots = store.get("snapshots", [])
    if not snapshots:
        return None
    return snapshots[-1]


def get_product_history(
    bank: str,
    product_name: str,
    days: int = 90,
) -> List[Dict[str, Any]]:
    """
    Get rate history for a specific product.

    Returns a list of {date, rate_pct} entries sorted by date.
    """
    store = _read_store()
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_str = cutoff.isoformat() + "Z"

    history = []
    for snapshot in store.get("snapshots", []):
        if snapshot.get("scraped_at", "") < cutoff_str:
            continue

        for product in snapshot.get("products", []):
            if (
                product.get("bank") == bank
                and product.get("product_name") == product_name
            ):
                history.append({
                    "date": snapshot["scraped_at"],
                    "rate_pct": product["rate_pct"],
                })
                break

    return sorted(history, key=lambda x: x["date"])


def get_all_products_latest() -> List[Dict[str, Any]]:
    """
    Get the latest rate for every product across all banks.

    Deduplicates by (bank, product_name), keeping the most recent entry.
    """
    snapshot = get_latest_snapshot()
    if not snapshot:
        return []
    return snapshot.get("products", [])


def get_ocr_history(days: int = 365) -> List[Dict[str, Any]]:
    """Get OCR rate history."""
    store = _read_store()
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_str = cutoff.isoformat() + "Z"

    history = []
    seen_rates = set()

    for snapshot in store.get("snapshots", []):
        if snapshot.get("scraped_at", "") < cutoff_str:
            continue

        ocr = snapshot.get("ocr")
        if ocr:
            rate = ocr.get("rate_pct")
            date = ocr.get("decision_date", snapshot["scraped_at"])
            key = f"{date}_{rate}"
            if key not in seen_rates:
                seen_rates.add(key)
                history.append({
                    "date": snapshot["scraped_at"],
                    "rate_pct": rate,
                    "decision_date": date,
                })

    return sorted(history, key=lambda x: x["date"])
