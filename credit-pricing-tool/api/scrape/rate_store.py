"""
Rate history storage — Supabase PostgreSQL backend.

Stores every scraped rate persistently in Supabase so data survives
container restarts. NO pruning — all historical data is kept forever.

Tables (created via migrations/001_rate_history_tables.sql):
    rate_snapshots          — one row per bank product per scrape
    wholesale_rate_snapshots — BKBM, swap, govt bond rates
    ocr_snapshots           — Official Cash Rate over time
    scrape_audit_log        — detailed log of every scrape run

Falls back to local JSON file if Supabase is not configured.
"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Local JSON fallback (used only when Supabase is unavailable)
STORE_DIR = Path(__file__).parent
STORE_FILE = STORE_DIR / ".rate_history.json"


def _get_supabase():
    """Get Supabase client, or None if not configured."""
    try:
        from api.db.supabase_client import get_client
        return get_client()
    except Exception:
        try:
            from ..db.supabase_client import get_client
            return get_client()
        except Exception:
            return None


# ─── Save Operations ─────────────────────────────────────────────────────────


def save_snapshot(scrape_result: Dict[str, Any], trigger_type: str = "manual") -> bool:
    """
    Save a full scrape result to Supabase (or local JSON fallback).

    Saves individual product rates, wholesale rates, OCR, and an audit log entry.
    NO pruning — all data is kept forever.

    Args:
        scrape_result: Output from scrape_all_bank_products()
        trigger_type: 'manual', 'scheduled', or 'on_demand'

    Returns:
        True if saved successfully
    """
    start_ms = time.time()
    client = _get_supabase()

    if client:
        return _save_to_supabase(client, scrape_result, trigger_type, start_ms)
    else:
        logger.warning("Supabase not configured — falling back to local JSON")
        return _save_to_json(scrape_result)


def _save_to_supabase(
    client, scrape_result: Dict[str, Any], trigger_type: str, start_ms: float
) -> bool:
    """Save scrape result to Supabase tables."""
    now = datetime.utcnow().isoformat() + "Z"
    errors = []

    # 1. Save bank product rates
    products = scrape_result.get("products", [])
    if products:
        try:
            rows = []
            for p in products:
                rows.append({
                    "scraped_at": now,
                    "bank": p.get("bank", ""),
                    "product_name": p.get("product_name", ""),
                    "rate_pct": p.get("rate_pct", 0),
                    "rate_type": p.get("rate_type", ""),
                    "category": p.get("category", ""),
                    "source_url": p.get("source_url", ""),
                })
            # Insert in batches of 50 to avoid payload limits
            for i in range(0, len(rows), 50):
                batch = rows[i:i + 50]
                client.table("rate_snapshots").insert(batch).execute()
            logger.info(f"Saved {len(rows)} product rates to Supabase")
        except Exception as e:
            errors.append(f"rate_snapshots: {e}")
            logger.error(f"Failed to save rate_snapshots: {e}")

    # 2. Save wholesale rates (BKBM, swap, govt bond)
    wholesale = scrape_result.get("bkbm_swap_rates", [])
    if wholesale:
        try:
            rows = []
            for w in wholesale:
                rows.append({
                    "scraped_at": now,
                    "rate_name": w.get("rate_name", ""),
                    "rate_pct": w.get("rate_pct", 0),
                    "tenor": w.get("tenor", ""),
                    "rate_type": w.get("rate_type", ""),
                    "rate_date": w.get("date", ""),
                    "source": w.get("source", ""),
                })
            client.table("wholesale_rate_snapshots").insert(rows).execute()
            logger.info(f"Saved {len(rows)} wholesale rates to Supabase")
        except Exception as e:
            errors.append(f"wholesale_rate_snapshots: {e}")
            logger.error(f"Failed to save wholesale_rate_snapshots: {e}")

    # 3. Save OCR rate
    ocr = scrape_result.get("ocr")
    if ocr:
        try:
            client.table("ocr_snapshots").insert({
                "scraped_at": now,
                "rate_pct": ocr.get("rate_pct", 0),
                "decision_date": ocr.get("decision_date", ""),
                "source": ocr.get("source", ""),
            }).execute()
            logger.info(f"Saved OCR rate {ocr.get('rate_pct')}% to Supabase")
        except Exception as e:
            errors.append(f"ocr_snapshots: {e}")
            logger.error(f"Failed to save ocr_snapshots: {e}")

    # 4. Write audit log entry
    duration_ms = int((time.time() - start_ms) * 1000)
    try:
        audit_row = {
            "scraped_at": now,
            "trigger_type": trigger_type,
            "duration_ms": duration_ms,
            "banks_scraped": scrape_result.get("banks_scraped", []),
            "product_count": scrape_result.get("product_count", 0),
            "ocr_rate": ocr.get("rate_pct") if ocr else None,
            "wholesale_count": len(wholesale),
            "errors": scrape_result.get("errors", []) + errors,
            "raw_result": json.dumps(scrape_result, default=str),
        }
        client.table("scrape_audit_log").insert(audit_row).execute()
        logger.info(f"Saved audit log entry (duration={duration_ms}ms)")
    except Exception as e:
        logger.error(f"Failed to save audit log: {e}")

    return len(errors) == 0


def _save_to_json(scrape_result: Dict[str, Any]) -> bool:
    """Fallback: save to local JSON file (no pruning)."""
    try:
        store = {"snapshots": []}
        if STORE_FILE.exists():
            with open(STORE_FILE, "r") as f:
                store = json.load(f)

        snapshot = {
            "scraped_at": scrape_result.get("scraped_at", datetime.utcnow().isoformat() + "Z"),
            "products": scrape_result.get("products", []),
            "ocr": scrape_result.get("ocr"),
            "bkbm_swap_rates": scrape_result.get("bkbm_swap_rates", []),
            "banks_scraped": scrape_result.get("banks_scraped", []),
            "product_count": scrape_result.get("product_count", 0),
        }
        store["snapshots"].append(snapshot)

        STORE_DIR.mkdir(parents=True, exist_ok=True)
        with open(STORE_FILE, "w") as f:
            json.dump(store, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to write JSON store: {e}")
        return False


# ─── Read Operations ─────────────────────────────────────────────────────────


def get_latest_snapshot() -> Optional[Dict[str, Any]]:
    """Get the most recent scrape snapshot (products + OCR + wholesale)."""
    client = _get_supabase()

    if client:
        try:
            # Get latest products (most recent scraped_at)
            resp = (
                client.table("rate_snapshots")
                .select("scraped_at")
                .order("scraped_at", desc=True)
                .limit(1)
                .execute()
            )
            if not resp.data:
                return None

            latest_ts = resp.data[0]["scraped_at"]

            # Get all products from that scrape
            products_resp = (
                client.table("rate_snapshots")
                .select("*")
                .eq("scraped_at", latest_ts)
                .execute()
            )

            # Get latest OCR
            ocr_resp = (
                client.table("ocr_snapshots")
                .select("*")
                .order("scraped_at", desc=True)
                .limit(1)
                .execute()
            )

            # Get latest wholesale rates
            wholesale_resp = (
                client.table("wholesale_rate_snapshots")
                .select("*")
                .order("scraped_at", desc=True)
                .limit(20)
                .execute()
            )

            products = [
                {
                    "bank": r["bank"],
                    "product_name": r["product_name"],
                    "rate_pct": float(r["rate_pct"]),
                    "rate_type": r.get("rate_type", ""),
                    "category": r.get("category", ""),
                    "source_url": r.get("source_url", ""),
                    "scraped_at": r["scraped_at"],
                }
                for r in (products_resp.data or [])
            ]

            ocr = None
            if ocr_resp.data:
                o = ocr_resp.data[0]
                ocr = {
                    "rate_name": "Official Cash Rate (OCR)",
                    "rate_pct": float(o["rate_pct"]),
                    "decision_date": o.get("decision_date", ""),
                    "source": o.get("source", ""),
                    "scraped_at": o["scraped_at"],
                }

            wholesale = [
                {
                    "rate_name": r["rate_name"],
                    "rate_pct": float(r["rate_pct"]),
                    "tenor": r["tenor"],
                    "rate_type": r["rate_type"],
                    "date": r.get("rate_date", ""),
                    "source": r.get("source", ""),
                }
                for r in (wholesale_resp.data or [])
            ]

            return {
                "scraped_at": latest_ts,
                "products": products,
                "ocr": ocr,
                "bkbm_swap_rates": wholesale,
                "banks_scraped": sorted(set(p["bank"] for p in products)),
                "product_count": len(products),
            }

        except Exception as e:
            logger.error(f"Failed to read latest snapshot from Supabase: {e}")
            return None

    # JSON fallback
    if STORE_FILE.exists():
        try:
            with open(STORE_FILE, "r") as f:
                store = json.load(f)
            snapshots = store.get("snapshots", [])
            return snapshots[-1] if snapshots else None
        except Exception:
            return None

    return None


def get_all_products_latest() -> List[Dict[str, Any]]:
    """Get the latest rate for every product across all banks."""
    snapshot = get_latest_snapshot()
    if not snapshot:
        return []
    return snapshot.get("products", [])


def get_product_history(
    bank: str,
    product_name: str,
    days: int = 0,
) -> List[Dict[str, Any]]:
    """
    Get rate history for a specific product. days=0 means ALL history (no limit).

    Returns a list of {date, rate_pct} entries sorted by date.
    """
    client = _get_supabase()

    if client:
        try:
            query = (
                client.table("rate_snapshots")
                .select("scraped_at, rate_pct")
                .eq("bank", bank)
                .eq("product_name", product_name)
                .order("scraped_at", desc=False)
            )

            if days > 0:
                cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
                query = query.gte("scraped_at", cutoff)

            resp = query.execute()

            return [
                {
                    "date": r["scraped_at"],
                    "rate_pct": float(r["rate_pct"]),
                }
                for r in (resp.data or [])
            ]
        except Exception as e:
            logger.error(f"Failed to get product history from Supabase: {e}")
            return []

    # JSON fallback
    return _get_product_history_json(bank, product_name, days)


def _get_product_history_json(bank: str, product_name: str, days: int) -> List[Dict[str, Any]]:
    """Fallback: get product history from local JSON."""
    if not STORE_FILE.exists():
        return []

    try:
        with open(STORE_FILE, "r") as f:
            store = json.load(f)

        cutoff_str = ""
        if days > 0:
            cutoff = datetime.utcnow() - timedelta(days=days)
            cutoff_str = cutoff.isoformat() + "Z"

        history = []
        for snapshot in store.get("snapshots", []):
            if cutoff_str and snapshot.get("scraped_at", "") < cutoff_str:
                continue
            for product in snapshot.get("products", []):
                if product.get("bank") == bank and product.get("product_name") == product_name:
                    history.append({
                        "date": snapshot["scraped_at"],
                        "rate_pct": product["rate_pct"],
                    })
                    break

        return sorted(history, key=lambda x: x["date"])
    except Exception:
        return []


def get_all_history(bank: str, days: int = 0) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get rate history for ALL products of a given bank.

    Returns: {"product_name": [{"date": ..., "rate_pct": ...}, ...], ...}
    """
    client = _get_supabase()

    if client:
        try:
            query = (
                client.table("rate_snapshots")
                .select("scraped_at, product_name, rate_pct")
                .eq("bank", bank)
                .order("scraped_at", desc=False)
            )

            if days > 0:
                cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
                query = query.gte("scraped_at", cutoff)

            resp = query.execute()

            history = {}
            for r in (resp.data or []):
                pname = r["product_name"]
                if pname not in history:
                    history[pname] = []
                history[pname].append({
                    "date": r["scraped_at"],
                    "rate_pct": float(r["rate_pct"]),
                })

            return history
        except Exception as e:
            logger.error(f"Failed to get bank history from Supabase: {e}")
            return {}

    return {}


def get_wholesale_history(rate_type: str = "", days: int = 0) -> List[Dict[str, Any]]:
    """
    Get wholesale rate history (BKBM, swap, govt bond).

    Args:
        rate_type: Filter by 'bkbm', 'swap', or 'govt_bond'. Empty = all.
        days: Number of days of history. 0 = all.

    Returns:
        List of rate records sorted by date.
    """
    client = _get_supabase()

    if client:
        try:
            query = (
                client.table("wholesale_rate_snapshots")
                .select("*")
                .order("scraped_at", desc=False)
                .limit(10000)
            )

            if rate_type:
                query = query.eq("rate_type", rate_type)

            if days > 0:
                cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
                query = query.gte("scraped_at", cutoff)

            resp = query.execute()

            return [
                {
                    "rate_name": r["rate_name"],
                    "rate_pct": float(r["rate_pct"]),
                    "tenor": r["tenor"],
                    "rate_type": r["rate_type"],
                    "date": r.get("rate_date", r["scraped_at"]),
                    "scraped_at": r["scraped_at"],
                }
                for r in (resp.data or [])
            ]
        except Exception as e:
            logger.error(f"Failed to get wholesale history from Supabase: {e}")
            return []

    return []


def get_ocr_history(days: int = 0) -> List[Dict[str, Any]]:
    """Get OCR rate history. days=0 means ALL history."""
    client = _get_supabase()

    if client:
        try:
            query = (
                client.table("ocr_snapshots")
                .select("*")
                .order("scraped_at", desc=False)
            )

            if days > 0:
                cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
                query = query.gte("scraped_at", cutoff)

            resp = query.execute()

            return [
                {
                    "date": r["scraped_at"],
                    "rate_pct": float(r["rate_pct"]),
                    "decision_date": r.get("decision_date", ""),
                }
                for r in (resp.data or [])
            ]
        except Exception as e:
            logger.error(f"Failed to get OCR history from Supabase: {e}")
            return []

    # JSON fallback
    if STORE_FILE.exists():
        try:
            with open(STORE_FILE, "r") as f:
                store = json.load(f)
            history = []
            seen = set()
            for snapshot in store.get("snapshots", []):
                ocr = snapshot.get("ocr")
                if ocr:
                    rate = ocr.get("rate_pct")
                    date = snapshot["scraped_at"]
                    key = f"{date}_{rate}"
                    if key not in seen:
                        seen.add(key)
                        history.append({
                            "date": date,
                            "rate_pct": rate,
                            "decision_date": ocr.get("decision_date", ""),
                        })
            return sorted(history, key=lambda x: x["date"])
        except Exception:
            return []

    return []


# ─── Audit Operations ────────────────────────────────────────────────────────


def get_audit_log(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get the scrape audit log — most recent entries first.

    Returns detailed records of every scrape run including:
    - timestamp, trigger type, duration
    - banks scraped, product count, OCR rate
    - any errors that occurred
    """
    client = _get_supabase()

    if not client:
        return []

    try:
        resp = (
            client.table("scrape_audit_log")
            .select("*")
            .order("scraped_at", desc=True)
            .limit(limit)
            .execute()
        )

        results = []
        for r in (resp.data or []):
            entry = {
                "id": r.get("id"),
                "scraped_at": r["scraped_at"],
                "trigger_type": r.get("trigger_type", "unknown"),
                "duration_ms": r.get("duration_ms", 0),
                "banks_scraped": r.get("banks_scraped", []),
                "product_count": r.get("product_count", 0),
                "ocr_rate": float(r["ocr_rate"]) if r.get("ocr_rate") else None,
                "wholesale_count": r.get("wholesale_count", 0),
                "errors": r.get("errors", []),
            }
            results.append(entry)

        return results

    except Exception as e:
        logger.error(f"Failed to get audit log from Supabase: {e}")
        return []


def get_audit_detail(audit_id: int) -> Optional[Dict[str, Any]]:
    """Get full audit detail including raw scrape result."""
    client = _get_supabase()
    if not client:
        return None

    try:
        resp = (
            client.table("scrape_audit_log")
            .select("*")
            .eq("id", audit_id)
            .execute()
        )
        if resp.data:
            entry = resp.data[0]
            # Parse raw_result from JSON string
            raw = entry.get("raw_result")
            if isinstance(raw, str):
                try:
                    entry["raw_result"] = json.loads(raw)
                except Exception:
                    pass
            return entry
        return None
    except Exception as e:
        logger.error(f"Failed to get audit detail: {e}")
        return None


def get_data_summary() -> Dict[str, Any]:
    """
    Get a summary of all stored rate data for the audit page.

    Returns counts, date ranges, and latest values for all data types.
    """
    client = _get_supabase()

    if not client:
        return {"supabase_connected": False}

    summary = {"supabase_connected": True}

    try:
        # Rate snapshots summary
        resp = client.table("rate_snapshots").select("id", count="exact").execute()
        summary["total_rate_records"] = resp.count or 0

        # Get distinct banks
        resp = client.table("rate_snapshots").select("bank").execute()
        banks = sorted(set(r["bank"] for r in (resp.data or [])))
        summary["banks"] = banks

        # Get date range
        oldest = (
            client.table("rate_snapshots")
            .select("scraped_at")
            .order("scraped_at", desc=False)
            .limit(1)
            .execute()
        )
        newest = (
            client.table("rate_snapshots")
            .select("scraped_at")
            .order("scraped_at", desc=True)
            .limit(1)
            .execute()
        )
        if oldest.data:
            summary["earliest_record"] = oldest.data[0]["scraped_at"]
        if newest.data:
            summary["latest_record"] = newest.data[0]["scraped_at"]

        # Wholesale count
        resp = client.table("wholesale_rate_snapshots").select("id", count="exact").execute()
        summary["total_wholesale_records"] = resp.count or 0

        # OCR count
        resp = client.table("ocr_snapshots").select("id", count="exact").execute()
        summary["total_ocr_records"] = resp.count or 0

        # Audit log count
        resp = client.table("scrape_audit_log").select("id", count="exact").execute()
        summary["total_scrape_runs"] = resp.count or 0

    except Exception as e:
        logger.error(f"Failed to get data summary: {e}")
        summary["error"] = str(e)

    return summary
