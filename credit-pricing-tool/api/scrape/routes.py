"""
Scrape routes for NZ bank base rates.

Legacy endpoints (backwards compatible):
  GET /api/base-rates         - Aggregated rates per bank
  GET /api/base-rates/refresh - Forces fresh scrape
  GET /api/base-rates/average - Market average rates

New granular endpoints:
  GET /api/rates/products     - All individual products across all banks
  GET /api/rates/products/refresh - Fresh scrape of all sources
  GET /api/rates/ocr          - Current Official Cash Rate
  GET /api/rates/history      - Rate history for a specific product
  GET /api/rates/banks        - List of banks and their product counts
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime

from .scraper import get_cached_rates, compute_market_average, force_refresh
from .bank_scrapers import scrape_all_bank_products
from .rate_store import (
    save_snapshot,
    get_latest_snapshot,
    get_all_products_latest,
    get_product_history,
    get_ocr_history,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class BaseRateEntry(BaseModel):
    """Single bank's base rate entry."""

    bank: str
    corporate_rate: Optional[float] = None
    working_capital_rate: Optional[float] = None
    overdraft_rate: Optional[float] = None
    last_updated: Optional[str] = None
    products: Optional[list] = None


class AverageRatesResponse(BaseModel):
    """Market average rates response."""

    average_corporate_rate: float
    average_working_capital_rate: float
    bank_count: int
    source: str = "interest.co.nz"
    last_updated: str


class BaseRatesResponse(BaseModel):
    """Response wrapper for base rates endpoint."""

    rates: List[BaseRateEntry]
    source: str = "interest.co.nz"
    cache_hit: bool
    last_updated: str


class RefreshResponse(BaseModel):
    """Response for refresh endpoint."""

    success: bool
    message: str
    rates: List[Dict[str, Any]]
    timestamp: str


@router.get("/base-rates")
def get_base_rates():
    """
    Get current NZ bank base rates.

    Returns a list of NZ banks with their current corporate and working capital rates.
    Uses cached rates if available (max 24h old), otherwise scrapes live from
    interest.co.nz. Falls back to hardcoded defaults if scraping fails.

    Returns:
        List of {bank, corporate_rate, working_capital_rate, overdraft_rate, last_updated}

    Example response:
        [
            {
                "bank": "ANZ",
                "corporate_rate": 5.45,
                "working_capital_rate": 7.15,
                "overdraft_rate": 8.00,
                "last_updated": "2026-03-11T14:30:00Z"
            },
            ...
        ]
    """
    rates = get_cached_rates()
    return rates


@router.get("/base-rates/refresh", response_model=RefreshResponse)
def refresh_base_rates() -> RefreshResponse:
    """
    Force a fresh scrape of NZ bank base rates, bypassing cache.

    Useful for getting the latest rates or testing the scraper.
    Will still fall back to hardcoded defaults if live scraping fails.

    Returns:
        Refresh status with new rates and timestamp

    Example response:
        {
            "success": true,
            "message": "Successfully refreshed 5 bank rates",
            "rates": [...],
            "timestamp": "2026-03-11T14:30:00Z"
        }
    """
    result = force_refresh()

    return RefreshResponse(
        success=result["success"],
        message=result["message"],
        rates=result["rates"],
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/base-rates/average", response_model=AverageRatesResponse)
def get_average_rates() -> AverageRatesResponse:
    """
    Get market average NZ bank base rates.

    Computes the mean corporate and working capital rates across all banks.

    Returns:
        Average rates with bank count and timestamp

    Example response:
        {
            "average_corporate_rate": 5.52,
            "average_working_capital_rate": 7.25,
            "bank_count": 5,
            "source": "interest.co.nz",
            "last_updated": "2026-03-11T14:30:00Z"
        }
    """
    rates = get_cached_rates()
    avg = compute_market_average(rates)

    # Get most recent timestamp from rates
    last_updated = max(
        (r.get("last_updated", datetime.utcnow().isoformat() + "Z") for r in rates),
        default=datetime.utcnow().isoformat() + "Z",
    )

    return AverageRatesResponse(
        average_corporate_rate=round(avg["average_corporate_rate"], 2),
        average_working_capital_rate=round(avg["average_working_capital_rate"], 2),
        bank_count=avg["bank_count"],
        last_updated=last_updated,
    )


# ─── New Granular Product Endpoints ───────────────────────────────────────────


@router.get("/rates/products")
def get_all_products(
    bank: Optional[str] = Query(None, description="Filter by bank name"),
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """
    Get all individual product rates across all banks.

    Each product is tracked by its exact name as shown on the bank's website.
    Data comes from multiple sources: ASB API, BNZ page data, interest.co.nz.

    Query params:
        bank: Filter by bank name (e.g., "ASB", "BNZ")
        category: Filter by category (e.g., "corporate", "overdraft", "rural")

    Returns:
        List of product rate dicts with bank, product_name, rate_pct, category, etc.
    """
    products = get_all_products_latest()

    if not products:
        # No stored data yet — trigger a fresh scrape
        result = scrape_all_bank_products()
        save_snapshot(result)
        products = result.get("products", [])

    # Apply filters
    if bank:
        products = [p for p in products if p.get("bank", "").lower() == bank.lower()]
    if category:
        products = [p for p in products if p.get("category", "").lower() == category.lower()]

    return products


@router.get("/rates/products/refresh")
def refresh_all_products():
    """
    Force a fresh scrape of all bank product rates.

    Scrapes ASB (API), BNZ (page data), interest.co.nz (all banks),
    OCR, and BKBM swap rates. Saves a snapshot for historical tracking.
    """
    result = scrape_all_bank_products()
    save_snapshot(result)

    return {
        "success": True,
        "product_count": result["product_count"],
        "banks_scraped": result["banks_scraped"],
        "ocr": result.get("ocr"),
        "errors": result.get("errors", []),
        "scraped_at": result["scraped_at"],
    }


@router.get("/rates/ocr")
def get_ocr():
    """
    Get the current RBNZ Official Cash Rate.

    Returns the latest OCR rate and decision date.
    """
    snapshot = get_latest_snapshot()
    if snapshot and snapshot.get("ocr"):
        return snapshot["ocr"]

    # Trigger fresh scrape for OCR
    result = scrape_all_bank_products()
    save_snapshot(result)

    if result.get("ocr"):
        return result["ocr"]

    raise HTTPException(status_code=404, detail="OCR rate not available")


@router.get("/rates/history")
def get_rate_history(
    bank: str = Query(..., description="Bank name"),
    product: str = Query(..., description="Product name"),
    days: int = Query(90, description="Number of days of history"),
):
    """
    Get rate history for a specific bank product.

    Returns a time series of rate values for charting.
    """
    history = get_product_history(bank, product, days)
    return {
        "bank": bank,
        "product": product,
        "days": days,
        "data_points": len(history),
        "history": history,
    }


@router.get("/rates/banks")
def get_banks_summary():
    """
    Get a summary of all banks and their products.

    Returns a list of banks with product counts and categories.
    """
    products = get_all_products_latest()

    if not products:
        result = scrape_all_bank_products()
        save_snapshot(result)
        products = result.get("products", [])

    # Group by bank
    banks: Dict[str, Dict[str, Any]] = {}
    for p in products:
        bank = p.get("bank", "Unknown")
        if bank not in banks:
            banks[bank] = {
                "bank": bank,
                "product_count": 0,
                "categories": set(),
                "products": [],
            }
        banks[bank]["product_count"] += 1
        banks[bank]["categories"].add(p.get("category", "other"))
        banks[bank]["products"].append({
            "product_name": p.get("product_name"),
            "rate_pct": p.get("rate_pct"),
            "rate_type": p.get("rate_type"),
            "category": p.get("category"),
        })

    # Convert sets to lists for JSON serialization
    result = []
    for bank_data in banks.values():
        bank_data["categories"] = sorted(bank_data["categories"])
        result.append(bank_data)

    return sorted(result, key=lambda x: x["bank"])
