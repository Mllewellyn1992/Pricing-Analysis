"""
Scrape routes for NZ bank base rates.

Legacy endpoints (backwards compatible):
  GET /api/base-rates         - Aggregated rates per bank
  GET /api/base-rates/refresh - Forces fresh scrape
  GET /api/base-rates/average - Market average rates

Granular product endpoints:
  GET /api/rates/products     - All individual products across all banks
  GET /api/rates/products/refresh - Fresh scrape of all sources
  GET /api/rates/ocr          - Current Official Cash Rate
  GET /api/rates/history      - Rate history for a specific product
  GET /api/rates/bank-history - All product history for a bank
  GET /api/rates/banks        - List of banks and their product counts
  GET /api/rates/wholesale    - BKBM + swap rates with history

Scrape trigger & audit endpoints:
  POST /api/rates/scrape      - Trigger a full scrape and save to DB
  GET  /api/rates/audit       - Scrape audit log
  GET  /api/rates/audit/{id}  - Detailed audit for a single scrape run
  GET  /api/rates/audit/summary - Data summary (counts, date ranges)
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from datetime import datetime

from .scraper import get_cached_rates, compute_market_average, force_refresh
from .bank_scrapers import scrape_all_bank_products, scrape_bkbm_swap_rates, scrape_bkbm_swap_history
from .rate_store import (
    save_snapshot,
    get_latest_snapshot,
    get_all_products_latest,
    get_product_history,
    get_all_history,
    get_wholesale_history,
    get_ocr_history,
    get_audit_log,
    get_audit_detail,
    get_data_summary,
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


# ─── Legacy Endpoints (backwards compatible) ─────────────────────────────────


@router.get("/base-rates")
def get_base_rates():
    """Get current NZ bank base rates (legacy format)."""
    rates = get_cached_rates()
    return rates


@router.get("/base-rates/refresh", response_model=RefreshResponse)
def refresh_base_rates() -> RefreshResponse:
    """Force a fresh scrape of NZ bank base rates, bypassing cache."""
    result = force_refresh()
    return RefreshResponse(
        success=result["success"],
        message=result["message"],
        rates=result["rates"],
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/base-rates/average", response_model=AverageRatesResponse)
def get_average_rates() -> AverageRatesResponse:
    """Get market average NZ bank base rates."""
    rates = get_cached_rates()
    avg = compute_market_average(rates)
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


# ─── Granular Product Endpoints ──────────────────────────────────────────────


@router.get("/rates/products")
def get_all_products(
    bank: Optional[str] = Query(None, description="Filter by bank name"),
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """Get all individual product rates across all banks."""
    products = get_all_products_latest()

    if not products:
        # No stored data yet — trigger a fresh scrape
        result = scrape_all_bank_products()
        save_snapshot(result, trigger_type="on_demand")
        products = result.get("products", [])

    if bank:
        products = [p for p in products if p.get("bank", "").lower() == bank.lower()]
    if category:
        products = [p for p in products if p.get("category", "").lower() == category.lower()]

    return products


@router.get("/rates/products/refresh")
def refresh_all_products():
    """Force a fresh scrape of all bank product rates and save to database."""
    result = scrape_all_bank_products()
    save_snapshot(result, trigger_type="manual")

    return {
        "success": True,
        "product_count": result["product_count"],
        "banks_scraped": result["banks_scraped"],
        "ocr": result.get("ocr"),
        "bkbm_swap_count": len(result.get("bkbm_swap_rates", [])),
        "errors": result.get("errors", []),
        "scraped_at": result["scraped_at"],
    }


@router.get("/rates/ocr")
def get_ocr():
    """Get the current RBNZ Official Cash Rate."""
    snapshot = get_latest_snapshot()
    if snapshot and snapshot.get("ocr"):
        return snapshot["ocr"]

    result = scrape_all_bank_products()
    save_snapshot(result, trigger_type="on_demand")

    if result.get("ocr"):
        return result["ocr"]

    raise HTTPException(status_code=404, detail="OCR rate not available")


@router.get("/rates/history")
def get_rate_history(
    bank: str = Query(..., description="Bank name"),
    product: str = Query(..., description="Product name"),
    days: int = Query(0, description="Number of days of history (0 = all)"),
):
    """Get rate history for a specific bank product."""
    history = get_product_history(bank, product, days)
    return {
        "bank": bank,
        "product": product,
        "days": days,
        "data_points": len(history),
        "history": history,
    }


@router.get("/rates/bank-history")
def get_bank_history(
    bank: str = Query(..., description="Bank name"),
    days: int = Query(0, description="Number of days of history (0 = all)"),
):
    """
    Get rate history for ALL products of a bank.

    Returns: {"bank": "ANZ", "products": {"product_name": [{"date":..., "rate_pct":...}], ...}}
    """
    history = get_all_history(bank, days)
    return {
        "bank": bank,
        "days": days,
        "products": history,
        "product_count": len(history),
    }


@router.get("/rates/banks")
def get_banks_summary():
    """Get a summary of all banks and their products."""
    products = get_all_products_latest()

    if not products:
        result = scrape_all_bank_products()
        save_snapshot(result, trigger_type="on_demand")
        products = result.get("products", [])

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

    result = []
    for bank_data in banks.values():
        bank_data["categories"] = sorted(bank_data["categories"])
        result.append(bank_data)

    return sorted(result, key=lambda x: x["bank"])


# ─── Wholesale Rates (BKBM, Swap) ────────────────────────────────────────────


def _try_live_scrape() -> tuple:
    """Attempt live BKBM/swap scrape, returning rates and success flag."""
    warnings = []
    latest_rates = []
    live_scrape_ok = False
    try:
        latest_rates = scrape_bkbm_swap_rates()
        if latest_rates:
            live_scrape_ok = True
        else:
            warnings.append("Live RBNZ scrape returned no data (Cloudflare 403). Using stored data from Supabase.")
    except Exception as scrape_err:
        warnings.append(f"Live RBNZ scrape failed: {str(scrape_err)}. Using stored data from Supabase.")
    return latest_rates, live_scrape_ok, warnings


def _build_rate_chart(history: List[Dict], rate_type_key: str) -> dict:
    """Build chart-friendly format from rate history by date."""
    by_date = {}
    for r in history:
        date = r["date"][:10] if r.get("date") else r.get("scraped_at", "")[:10]
        if date not in by_date:
            by_date[date] = {"date": date}
        by_date[date][r["tenor"]] = r["rate_pct"]
    return sorted(by_date.values(), key=lambda x: x["date"])


def _populate_missing_swap_rates(latest_swap: List[Dict], swap_chart: List[Dict]) -> None:
    """Populate latest swap rates from history if live scrape returned nothing."""
    if not latest_swap and swap_chart:
        last_entry = swap_chart[-1]
        for tenor, rate in last_entry.items():
            if tenor != "date" and isinstance(rate, (int, float)):
                latest_swap.append({
                    "rate_name": f"Swap {tenor}",
                    "rate_pct": rate,
                    "tenor": tenor,
                    "rate_type": "swap",
                    "source": "Supabase (browser-scraped from interest.co.nz)",
                })


def _populate_missing_bkbm_rates(latest_bkbm: List[Dict], bkbm_chart: List[Dict]) -> None:
    """Populate latest BKBM rates from history if live scrape returned nothing."""
    if not latest_bkbm and bkbm_chart:
        seen_tenors = {}
        for entry in reversed(bkbm_chart):
            for tenor, rate in entry.items():
                if tenor != "date" and isinstance(rate, (int, float)) and tenor not in seen_tenors:
                    seen_tenors[tenor] = rate
            if len(seen_tenors) >= 10:
                break
        for tenor, rate in seen_tenors.items():
            latest_bkbm.append({
                "rate_name": f"{tenor}",
                "rate_pct": rate,
                "tenor": tenor,
                "rate_type": "bkbm",
                "source": "Supabase (browser-scraped from interest.co.nz)",
            })


@router.get("/rates/wholesale")
def get_wholesale_rates(
    history_days: int = Query(0, description="Number of days of history (0 = all)")
):
    """
    Get BKBM and swap rates with historical data for charting.

    Returns current rates + time series history from the database.
    """
    try:
        latest_rates, live_scrape_ok, warnings = _try_live_scrape()

        bkbm_history = get_wholesale_history("bkbm", history_days)
        swap_history = get_wholesale_history("swap", history_days)

        bkbm_chart = _build_rate_chart(bkbm_history, "bkbm")
        swap_chart = _build_rate_chart(swap_history, "swap")

        latest_bkbm = [r for r in latest_rates if r.get("rate_type") == "bkbm"]
        latest_swap = [r for r in latest_rates if r.get("rate_type") == "swap"]

        data_source = "live_scrape" if live_scrape_ok else "supabase_stored"
        _populate_missing_swap_rates(latest_swap, swap_chart)
        _populate_missing_bkbm_rates(latest_bkbm, bkbm_chart)

        return {
            "latest_rates": latest_swap + latest_bkbm,
            "latest": {
                "bkbm": latest_bkbm,
                "swap": latest_swap,
            },
            "history": {
                "bkbm": bkbm_chart,
                "swap": swap_chart,
            },
            "data_source": data_source,
            "warnings": warnings,
            "history_days": history_days,
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "source": "interest.co.nz / Supabase history",
        }

    except Exception as e:
        logger.error(f"Failed to get wholesale rates: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve wholesale rates: {str(e)}"
        )


# ─── Browser-Scraped Wholesale Rate Injection ────────────────────────────────


@router.post("/rates/wholesale/inject")
def inject_wholesale_rates(payload: Dict[str, Any] = Body(...)):
    """
    Receive wholesale rates scraped via browser automation (Claude in Chrome).

    Accepts a list of rate objects and saves them to Supabase.
    This endpoint is called by the frontend after browser-scraping
    the interest.co.nz swap rates page.

    Body: { "rates": [...], "source": "interest.co.nz (browser)" }
    """
    from .rate_store import _get_supabase

    rate_list = payload.get("rates", [])
    source = payload.get("source", "browser")

    if not rate_list:
        raise HTTPException(status_code=400, detail="No rates provided")

    client = _get_supabase()
    if not client:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    now = datetime.utcnow().isoformat() + "Z"
    saved = 0
    errors = []

    for r in rate_list:
        try:
            client.table("wholesale_rate_snapshots").insert({
                "scraped_at": now,
                "rate_name": r.get("rate_name", ""),
                "rate_pct": r.get("rate_pct", 0),
                "tenor": r.get("tenor", ""),
                "rate_type": r.get("rate_type", "swap"),
                "rate_date": r.get("date", now[:10]),
                "source": r.get("source", source),
            }).execute()
            saved += 1
        except Exception as e:
            errors.append(f"{r.get('rate_name', '?')}: {e}")

    return {
        "success": saved > 0,
        "saved": saved,
        "total": len(rate_list),
        "errors": errors,
        "scraped_at": now,
    }


# ─── Scrape Trigger ──────────────────────────────────────────────────────────


@router.post("/rates/scrape")
def trigger_scrape(
    trigger_type: str = Query("manual", description="Trigger type: manual, scheduled")
):
    """
    Trigger a full scrape of all sources and save to database.

    This is the endpoint that should be called by a cron job for daily scraping.
    Can also be called manually via the audit page.
    """
    try:
        result = scrape_all_bank_products()
        success = save_snapshot(result, trigger_type=trigger_type)

        return {
            "success": success,
            "product_count": result["product_count"],
            "banks_scraped": result["banks_scraped"],
            "ocr_rate": result["ocr"]["rate_pct"] if result.get("ocr") else None,
            "wholesale_count": len(result.get("bkbm_swap_rates", [])),
            "errors": result.get("errors", []),
            "scraped_at": result["scraped_at"],
        }

    except Exception as e:
        logger.error(f"Scrape trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scrape failed: {str(e)}")


# Also support GET for easy cron job integration
@router.get("/rates/scrape")
def trigger_scrape_get():
    """GET version of scrape trigger for easy cron job integration."""
    return trigger_scrape(trigger_type="scheduled")


# ─── Audit Endpoints ─────────────────────────────────────────────────────────


@router.get("/rates/audit")
def get_audit(
    limit: int = Query(50, description="Number of audit entries to return")
):
    """
    Get the scrape audit log — most recent scrape runs with details.

    Shows every scrape that has been run: when, what was collected,
    any errors, duration, etc. Use this to verify data collection is working.
    """
    audit = get_audit_log(limit)
    summary = get_data_summary()

    return {
        "audit_log": audit,
        "summary": summary,
        "total_entries": len(audit),
    }


@router.get("/rates/audit/summary")
def get_audit_summary_endpoint():
    """Get a high-level summary of all stored rate data."""
    return get_data_summary()


@router.get("/rates/audit/{audit_id}")
def get_audit_entry(audit_id: int):
    """Get detailed audit information for a specific scrape run."""
    detail = get_audit_detail(audit_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    return detail
