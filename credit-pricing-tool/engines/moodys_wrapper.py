"""
Moody's Rating Engine Wrapper - Clean API on top of moodys_engine.py.
Computes all required metrics from raw financials and passes to the YAML-driven engine.

The Moody's engine has 35 methodologies, each requiring different metrics.
This wrapper computes the UNIVERSAL metrics that work across all methodologies,
then passes them to the scoring engine.

Key differences from S&P:
- FFO = CFO - Change in NWC - Change in LT Operating Assets (S&P: FFO = EBITDA - Cash Interest - Cash Taxes)
- Total Debt = ST Debt + CPLTD + LT Debt Net + Capital Leases
- RCF = FFO - All Dividends (common + preferred + minority)
- Score-to-rating uses Moody's scale (Aaa, Aa1, etc.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .moodys_engine import score_company, CONFIG_DIR as MOODYS_CONFIG_DIR

# Moody's configs are in configs/moodys/
CONFIG_DIR = Path(__file__).resolve().parent / "configs" / "moodys"


# ── Rating scale conversion ──────────────────────────────────────────────

MOODY_TO_SP = {
    "Aaa": "AAA", "Aa1": "AA+", "Aa2": "AA", "Aa3": "AA-", "Aa": "AA",
    "A1": "A+", "A2": "A", "A3": "A-", "A": "A",
    "Baa1": "BBB+", "Baa2": "BBB", "Baa3": "BBB-", "Baa": "BBB",
    "Ba1": "BB+", "Ba2": "BB", "Ba3": "BB-", "Ba": "BB",
    "B1": "B+", "B2": "B", "B3": "B-", "B": "B",
    "Caa1": "CCC+", "Caa2": "CCC", "Caa3": "CCC-", "Caa": "CCC",
    "Ca": "CCC-",
}

SP_TO_MOODY = {v: k for k, v in MOODY_TO_SP.items() if len(k) > 1}


def moody_to_sp_rating(moody_rating: str) -> Optional[str]:
    """Convert Moody's rating to S&P equivalent."""
    return MOODY_TO_SP.get(moody_rating)


def sp_to_moody_rating(sp_rating: str) -> Optional[str]:
    """Convert S&P rating to Moody's equivalent."""
    return SP_TO_MOODY.get(sp_rating)


# ── Universal metric computation ─────────────────────────────────────────

def compute_total_debt(financials: dict) -> float:
    """Total Debt = ST Debt + CPLTD + LT Debt Net + Capital Leases."""
    return (
        financials.get("st_debt_mn", 0.0)
        + financials.get("cpltd_mn", 0.0)
        + financials.get("lt_debt_net_mn", 0.0)
        + financials.get("capital_leases_mn", 0.0)
    )


def compute_net_debt(total_debt: float, financials: dict) -> float:
    """Net Debt = Total Debt - Cash - Cash-like Assets."""
    return (
        total_debt
        - financials.get("cash_mn", 0.0)
        - financials.get("cash_like_mn", 0.0)
    )


def compute_ffo(financials: dict) -> float:
    """
    Moody's FFO = CFO - Change in NWC - Change in LT Operating Assets.
    NOTE: This differs from S&P FFO = EBITDA - Cash Interest - Cash Taxes.
    """
    change_nwc = (
        financials.get("nwc_current_mn", 0.0)
        - financials.get("nwc_prior_mn", 0.0)
    )
    change_lt_assets = (
        financials.get("lt_operating_assets_current_mn", 0.0)
        - financials.get("lt_operating_assets_prior_mn", 0.0)
    )
    return financials.get("cfo_mn", 0.0) - change_nwc - change_lt_assets


def compute_rcf(ffo: float, financials: dict) -> float:
    """RCF = FFO - All Dividends (common + preferred + minority)."""
    return (
        ffo
        - financials.get("common_dividends_mn", 0.0)
        - financials.get("preferred_dividends_mn", 0.0)
        - financials.get("minority_dividends_mn", 0.0)
    )


def compute_debt_book_cap_pct(total_debt: float, financials: dict) -> float:
    """Debt / Book Capitalisation %."""
    equity = financials.get("total_equity_mn", 0.0)
    minority = financials.get("minority_interest_mn", 0.0)
    deferred_tax = financials.get("deferred_taxes_mn", 0.0)
    book_cap = total_debt + equity + minority + deferred_tax
    return (total_debt / book_cap) * 100.0 if book_cap else 0.0


def compute_avg_assets(financials: dict) -> float:
    """Average assets from current and prior year."""
    current = financials.get("assets_current_mn", 0.0)
    prior = financials.get("assets_prior_mn", 0.0)
    if current and prior:
        return (current + prior) / 2.0
    return current or prior


def compute_universal_metrics(financials: dict) -> dict:
    """
    Compute all universal Moody's metrics from raw financials.
    Returns a dict ready to pass to score_company().
    """
    revenue_mn = financials.get("revenue_mn", 0.0)
    ebit_mn = financials.get("ebit_mn", 0.0)
    dep_mn = financials.get("depreciation_mn", 0.0)
    amort_mn = financials.get("amortization_mn", 0.0)
    interest_mn = financials.get("interest_expense_mn", 0.0)
    capex_mn = financials.get("capex_mn", 0.0)
    cfo_mn = financials.get("cfo_mn", 0.0)

    ebitda = ebit_mn + dep_mn + amort_mn
    total_debt = compute_total_debt(financials)
    net_debt = compute_net_debt(total_debt, financials)
    ffo = compute_ffo(financials)
    rcf = compute_rcf(ffo, financials)
    avg_assets = compute_avg_assets(financials)

    # FCF = CFO - Capex - All Dividends
    fcf = (
        cfo_mn - capex_mn
        - financials.get("common_dividends_mn", 0.0)
        - financials.get("preferred_dividends_mn", 0.0)
        - financials.get("minority_dividends_mn", 0.0)
    )

    # Additional derived values for sector-specific methodologies
    cash_mn = financials.get("cash_mn", 0.0)
    cash_like_mn = financials.get("cash_like_mn", 0.0)
    marketable_securities_mn = financials.get("marketable_securities_mn", 0.0)
    cash_and_securities = cash_mn + cash_like_mn + marketable_securities_mn

    # Operating income ROA (net of cash & marketable securities)
    total_assets = financials.get("assets_current_mn", 0.0)
    net_assets_for_roa = total_assets - cash_and_securities if total_assets else avg_assets
    oi_roa_net = (ebit_mn / net_assets_for_roa) * 100.0 if net_assets_for_roa else 0.0

    metrics = {
        # Scale
        "revenue_usd_billion": revenue_mn / 1000.0,

        # Core ratios (appear in 25+ of 35 methodologies)
        "debt_ebitda_x": (total_debt / ebitda) if ebitda else 0.0,
        "ebit_interest_x": (ebit_mn / interest_mn) if interest_mn else 0.0,
        "ebitda_interest_x": (ebitda / interest_mn) if interest_mn else 0.0,
        "rcf_net_debt_pct": (rcf / net_debt) * 100.0 if net_debt else 0.0,

        # Additional universal ratios
        "ffo_debt_pct": (ffo / total_debt) * 100.0 if total_debt else 0.0,
        "operating_margin_pct": (ebit_mn / revenue_mn) * 100.0 if revenue_mn else 0.0,
        "ebitda_margin_pct": (ebitda / revenue_mn) * 100.0 if revenue_mn else 0.0,

        # Ratios used by 13-15 methodologies
        "ebita_interest_x": ((ebit_mn + amort_mn) / interest_mn) if interest_mn else 0.0,
        "ebitda_minus_capex_interest_x": ((ebitda - capex_mn) / interest_mn) if interest_mn else 0.0,
        "ebitda_capex_interest_x": ((ebitda - capex_mn) / interest_mn) if interest_mn else 0.0,
        "fcf_debt_pct": (fcf / total_debt) * 100.0 if total_debt else 0.0,

        # Software/tech specific
        "free_cash_flow_usd_billion": fcf / 1000.0,
        "operating_income_roa_net_cash_mktsec_pct": oi_roa_net,
        "cash_marketable_securities_debt_pct": (cash_and_securities / total_debt) * 100.0 if total_debt else 0.0,

        # Ratios used by 7-8 methodologies
        "debt_book_cap_pct": compute_debt_book_cap_pct(total_debt, financials),
        "return_avg_assets_pct": (ebit_mn / avg_assets) * 100.0 if avg_assets else 0.0,
        "ebit_avg_assets_pct": (ebit_mn / avg_assets) * 100.0 if avg_assets else 0.0,
        "ebit_margin_pct": (ebit_mn / revenue_mn) * 100.0 if revenue_mn else 0.0,
        "ebitda_margin_3yr_avg_pct": (ebitda / revenue_mn) * 100.0 if revenue_mn else 0.0,
        "operating_margin_volatility_pct": 5.0,  # Default estimate when no history available
        "revenue_volatility_pct": 10.0,  # Default estimate

        # Sector-specific metrics needed by individual methodologies
        "ebita_margin_pct": ((ebit_mn + amort_mn) / revenue_mn) * 100.0 if revenue_mn else 0.0,
        "total_sales_usd_billion": revenue_mn / 1000.0,  # Same as revenue, USD bn proxy
        "total_revenue_usd_billion": revenue_mn / 1000.0,
        "total_assets_usd_billion": financials.get("assets_current_mn", 0.0) / 1000.0,
        "net_income_avg_assets_pct": (ebit_mn * 0.7 / avg_assets) * 100.0 if avg_assets else 0.0,  # Approx
        "return_on_avg_assets_pct": (ebit_mn / avg_assets) * 100.0 if avg_assets else 0.0,
        "gross_margin_pct": (ebitda / revenue_mn) * 100.0 if revenue_mn else 0.0,  # Proxy

        # Media-specific: debt/EBITDA and coverage variants for broadcasters and publishers
        "debt_ebitda_other_x": (total_debt / ebitda) if ebitda else 0.0,
        "debt_ebitda_publishers_x": (total_debt / ebitda) if ebitda else 0.0,
        "ebitda_minus_capex_interest_other_x": ((ebitda - capex_mn) / interest_mn) if interest_mn else 0.0,
        "ebitda_minus_capex_interest_publishers_x": ((ebitda - capex_mn) / interest_mn) if interest_mn else 0.0,

        # Oil & Gas specific (sector-specific scale metrics)
        "avg_daily_production_mboed": financials.get("avg_daily_production_mboed", 50.0),
        "pd_reserves_mmboe": financials.get("pd_reserves_mmboe", 200.0),
        "proved_reserves_mmboe": financials.get("proved_reserves_mmboe", 200.0),
        "leveraged_full_cycle_ratio_x": financials.get("leveraged_full_cycle_ratio_x",
            (ebitda / total_debt) if total_debt else 1.0),
        "ep_debt_per_avg_daily_production_usd_per_boe_d": financials.get(
            "ep_debt_per_avg_daily_production_usd_per_boe_d",
            (total_debt * 1_000_000) / (financials.get("avg_daily_production_mboed", 50.0) * 1000) if financials.get("avg_daily_production_mboed", 50.0) else 0.0
        ),
        "ep_debt_per_pd_reserves_usd_per_boe": financials.get(
            "ep_debt_per_pd_reserves_usd_per_boe",
            (total_debt * 1_000_000) / (financials.get("pd_reserves_mmboe", 200.0) * 1_000_000) if financials.get("pd_reserves_mmboe", 200.0) else 0.0
        ),
        # Integrated oil & gas specific
        "crude_distillation_capacity_mbbld": financials.get("crude_distillation_capacity_mbbld", 100.0),
        "ebit_avg_book_cap_pct": (ebit_mn / (total_debt + financials.get("total_equity_mn", 0.0))) * 100.0 if (total_debt + financials.get("total_equity_mn", 0.0)) else 0.0,
        "downstream_ebit_per_throughput_usd_per_bbl": financials.get("downstream_ebit_per_throughput_usd_per_bbl", 5.0),

        # Auto manufacturers specific
        "market_share_change_pp": financials.get("market_share_change_pp", 0.0),

        # Additional core ratio aliases used by some configs
        "rcf_debt_pct": (rcf / total_debt) * 100.0 if total_debt else 0.0,

        # Raw values for special cases in the engine
        "total_debt": total_debt,
        "net_debt": net_debt,
        "ebitda": ebitda,
        "ebit": ebit_mn,
        "rcf": rcf,
        "interest_expense": interest_mn,
    }

    return metrics


# ── Main rating function ─────────────────────────────────────────────────

def rate_company_moodys(
    financials: dict,
    methodology_id: str,
    quant_only: bool = True,
    qualitative_overrides: Optional[Dict[str, str]] = None,
) -> dict:
    """
    Compute Moody's-style rating from financial metrics.

    Args:
        financials: dict with raw financial inputs (revenue_mn, ebit_mn, etc.)
        methodology_id: e.g. "building_materials", "software"
        quant_only: when True, skip qualitative factors (normalize_quantitative=True)
        qualitative_overrides: optional dict of {metric_code: band_value} for qual inputs

    Returns:
        dict with:
            moody_rating: e.g. "Baa2"
            sp_equivalent: e.g. "BBB"
            composite_score: float
            computed_metrics: dict of all computed ratios
            factor_scores: list
            subfactor_scores: list
            workings: detailed audit trail
    """
    # Compute metrics
    metrics = compute_universal_metrics(financials)

    # Add qualitative overrides if provided
    if qualitative_overrides and not quant_only:
        metrics.update(qualitative_overrides)

    # Run the engine
    result = score_company(
        methodology_id=methodology_id,
        metrics=metrics,
        config_dir=CONFIG_DIR,
        normalize_quantitative=quant_only,
    )

    moody_rating = result.get("anchor_rating")
    sp_equivalent = moody_to_sp_rating(moody_rating) if moody_rating else None

    return {
        "moody_rating": moody_rating,
        "sp_equivalent": sp_equivalent,
        "composite_score": result.get("composite_score"),
        "methodology_id": result.get("methodology_id"),
        "methodology_name": result.get("methodology_name"),
        "computed_metrics": metrics,
        "factor_scores": result.get("factor_scores", []),
        "subfactor_scores": result.get("subfactor_scores", []),
        "workings": {
            "input_financials": financials,
            "methodology_id": methodology_id,
            "quant_only": quant_only,
            "computed_metrics": metrics,
            "engine_result": result,
        },
    }


# ── Sector mapping (Moody's methodology IDs) ────────────────────────────

MOODYS_METHODOLOGIES = {
    "aerospace_defense": "Aerospace & Defense",
    "alcoholic_beverages": "Alcoholic Beverages",
    "auto_manufacturing": "Auto Manufacturing",
    "auto_suppliers": "Auto Suppliers",
    "building_materials": "Building Materials",
    "business_consumer_services": "Business & Consumer Services",
    "chemicals": "Chemicals",
    "communications_infrastructure": "Communications Infrastructure",
    "construction": "Construction",
    "consumer_durables": "Consumer Durables",
    "consumer_packaged_goods": "Consumer Packaged Goods",
    "distribution_supply_chain": "Distribution & Supply Chain",
    "diversified_manufacturing": "Diversified Manufacturing",
    "environmental_services": "Environmental Services & Waste Mgmt",
    "food_processing": "Food Processing",
    "gaming": "Gaming",
    "homebuilding": "Homebuilding & Property Development",
    "integrated_oil_gas": "Integrated Oil & Gas",
    "media": "Media",
    "metals_mining": "Metals & Mining",
    "oil_gas_e_and_p": "Oil & Gas Exploration & Production",
    "oil_gas_refining": "Oil & Gas Refining & Marketing",
    "oilfield_services": "Oilfield Services",
    "packaging": "Packaging",
    "paper_forest_products": "Paper & Forest Products",
    "pharmaceuticals": "Pharmaceuticals",
    "protein_agriculture": "Protein & Agriculture",
    "restaurants": "Restaurants",
    "retail_apparel": "Retail & Apparel",
    "semiconductors": "Semiconductors",
    "shipping": "Shipping",
    "software": "Software",
    "steel": "Steel",
    "surface_transportation": "Surface Transportation & Logistics",
    "telecommunications": "Telecommunications",
}


def list_moodys_methodologies() -> list:
    """Return list of available Moody's methodology IDs."""
    return list(MOODYS_METHODOLOGIES.keys())
