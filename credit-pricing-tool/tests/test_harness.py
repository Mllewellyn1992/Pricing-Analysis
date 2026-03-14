"""
Cross-Engine Test Harness
========================
Runs identical financial inputs through both the S&P and Moody's engines,
compares outputs, and identifies which engine performs better per sector.

Usage:
    cd credit-pricing-tool/
    python -m tests.test_harness
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.sp_engine import rate_company_sp
from engines.sp_defaults import get_defaults
from engines.moodys_wrapper import rate_company_moodys, moody_to_sp_rating


# ── Test companies ───────────────────────────────────────────────────────

TEST_COMPANIES = {
    "Healthy NZ Software Co": {
        "description": "Mid-size NZ software company, good margins, low debt",
        "sp_sector": "technology_software_and_services",
        "moodys_sector": "software",  # needs free_cash_flow_usd_billion etc
        "financials": {
            # Core (both engines)
            "revenue_mn": 50.0,
            "ebit_mn": 12.0,
            "depreciation_mn": 3.0,
            "amortization_mn": 2.0,
            "interest_expense_mn": 1.5,
            "cash_interest_paid_mn": 1.2,
            "cash_taxes_paid_mn": 2.8,
            "total_debt_mn": 20.0,
            "cash_mn": 8.0,
            "avg_capital_mn": 35.0,
            "cfo_mn": 15.0,
            "capex_mn": 4.0,
            "dividends_paid_mn": 2.0,
            "share_buybacks_mn": 0.0,
            # Moody's additional
            "st_debt_mn": 2.0,
            "cpltd_mn": 3.0,
            "lt_debt_net_mn": 14.0,
            "capital_leases_mn": 1.0,
            "cash_like_mn": 2.0,
            "nwc_current_mn": 10.0,
            "nwc_prior_mn": 9.0,
            "lt_operating_assets_current_mn": 25.0,
            "lt_operating_assets_prior_mn": 23.0,
            "common_dividends_mn": 2.0,
            "preferred_dividends_mn": 0.0,
            "minority_dividends_mn": 0.0,
        },
    },
    "Leveraged NZ Mining Co": {
        "description": "NZ mining company, cyclical, moderate leverage",
        "sp_sector": "mining",
        "moodys_sector": "steel",
        "financials": {
            "revenue_mn": 100.0,
            "ebit_mn": 20.0,
            "depreciation_mn": 6.0,
            "amortization_mn": 2.0,
            "interest_expense_mn": 4.0,
            "cash_interest_paid_mn": 3.5,
            "cash_taxes_paid_mn": 5.0,
            "total_debt_mn": 80.0,
            "cash_mn": 10.0,
            "avg_capital_mn": 60.0,
            "cfo_mn": 25.0,
            "capex_mn": 12.0,
            "dividends_paid_mn": 3.0,
            "share_buybacks_mn": 0.0,
            "st_debt_mn": 5.0,
            "cpltd_mn": 10.0,
            "lt_debt_net_mn": 60.0,
            "capital_leases_mn": 5.0,
            "cash_like_mn": 3.0,
            "nwc_current_mn": 15.0,
            "nwc_prior_mn": 12.0,
            "lt_operating_assets_current_mn": 80.0,
            "lt_operating_assets_prior_mn": 75.0,
            "common_dividends_mn": 3.0,
            "preferred_dividends_mn": 0.0,
            "minority_dividends_mn": 0.0,
        },
    },
    "Strong NZ Utility": {
        "description": "Regulated NZ utility, stable cash flows, low leverage",
        "sp_sector": "regulated_utilities",
        "moodys_sector": "telecommunications_service_providers",
        "financials": {
            "revenue_mn": 200.0,
            "ebit_mn": 60.0,
            "depreciation_mn": 15.0,
            "amortization_mn": 2.0,
            "interest_expense_mn": 5.0,
            "cash_interest_paid_mn": 4.8,
            "cash_taxes_paid_mn": 15.0,
            "total_debt_mn": 60.0,
            "cash_mn": 15.0,
            "avg_capital_mn": 120.0,
            "cfo_mn": 55.0,
            "capex_mn": 20.0,
            "dividends_paid_mn": 25.0,
            "share_buybacks_mn": 0.0,
            "st_debt_mn": 5.0,
            "cpltd_mn": 5.0,
            "lt_debt_net_mn": 48.0,
            "capital_leases_mn": 2.0,
            "cash_like_mn": 5.0,
            "nwc_current_mn": 20.0,
            "nwc_prior_mn": 18.0,
            "lt_operating_assets_current_mn": 150.0,
            "lt_operating_assets_prior_mn": 145.0,
            "common_dividends_mn": 25.0,
            "preferred_dividends_mn": 0.0,
            "minority_dividends_mn": 0.0,
        },
    },
    "Struggling NZ Retailer": {
        "description": "NZ retail company, thin margins, high leverage",
        "sp_sector": "retail_and_restaurants",
        "moodys_sector": "retail_and_apparel",
        "financials": {
            "revenue_mn": 150.0,
            "ebit_mn": 5.0,
            "depreciation_mn": 4.0,
            "amortization_mn": 1.0,
            "interest_expense_mn": 6.0,
            "cash_interest_paid_mn": 5.5,
            "cash_taxes_paid_mn": 1.0,
            "total_debt_mn": 70.0,
            "cash_mn": 5.0,
            "avg_capital_mn": 40.0,
            "cfo_mn": 8.0,
            "capex_mn": 5.0,
            "dividends_paid_mn": 0.0,
            "share_buybacks_mn": 0.0,
            "st_debt_mn": 10.0,
            "cpltd_mn": 10.0,
            "lt_debt_net_mn": 45.0,
            "capital_leases_mn": 5.0,
            "cash_like_mn": 1.0,
            "nwc_current_mn": 25.0,
            "nwc_prior_mn": 22.0,
            "lt_operating_assets_current_mn": 40.0,
            "lt_operating_assets_prior_mn": 38.0,
            "common_dividends_mn": 0.0,
            "preferred_dividends_mn": 0.0,
            "minority_dividends_mn": 0.0,
        },
    },
    "NZ Construction Firm": {
        "description": "Cyclical NZ construction company, moderate debt",
        "sp_sector": "engineering_and_construction",
        "moodys_sector": "construction",
        "financials": {
            "revenue_mn": 80.0,
            "ebit_mn": 8.0,
            "depreciation_mn": 5.0,
            "amortization_mn": 1.0,
            "interest_expense_mn": 3.0,
            "cash_interest_paid_mn": 2.8,
            "cash_taxes_paid_mn": 2.0,
            "total_debt_mn": 40.0,
            "cash_mn": 6.0,
            "avg_capital_mn": 50.0,
            "cfo_mn": 12.0,
            "capex_mn": 6.0,
            "dividends_paid_mn": 1.5,
            "share_buybacks_mn": 0.0,
            "st_debt_mn": 5.0,
            "cpltd_mn": 5.0,
            "lt_debt_net_mn": 28.0,
            "capital_leases_mn": 2.0,
            "cash_like_mn": 2.0,
            "nwc_current_mn": 18.0,
            "nwc_prior_mn": 15.0,
            "lt_operating_assets_current_mn": 35.0,
            "lt_operating_assets_prior_mn": 33.0,
            "common_dividends_mn": 1.5,
            "preferred_dividends_mn": 0.0,
            "minority_dividends_mn": 0.0,
        },
    },
}


# ── Rating scale for comparison ──────────────────────────────────────────

SP_SCALE = [
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
    "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D"
]


def rating_to_numeric(rating: str) -> int:
    """Convert S&P-scale rating to numeric (1=AAA, 22=D)."""
    if rating in SP_SCALE:
        return SP_SCALE.index(rating) + 1
    return 99


def notch_difference(rating_a: str, rating_b: str) -> int:
    """Number of notches between two S&P-scale ratings (positive = A is better)."""
    return rating_to_numeric(rating_b) - rating_to_numeric(rating_a)


# ── Main harness ─────────────────────────────────────────────────────────

def _run_sp_engine(financials, sp_sector):
    """Run S&P engine for a company. Returns (rating, ratios) or (error_str, None)."""
    defaults = get_defaults(sp_sector)
    try:
        result = rate_company_sp(
            financials=financials, sector_id=sp_sector,
            cyclicality=defaults["cyclicality"],
            competitive_risk=defaults["competitive_risk"],
            country_risk=2, quant_only=True,
        )
        ratios = result["computed_ratios"]
        print(f"\n  S&P Engine:")
        print(f"    Business Risk: {result['business_risk_score']}, Financial Risk: {result['financial_risk_score']}")
        print(f"    Anchor: {result['anchor_rating']}, Final: {result['final_rating']}")
        print(f"    Key ratios: Debt/EBITDA={ratios['debt_to_ebitda_x']:.2f}x, "
              f"FFO/Debt={ratios['ffo_to_debt_pct']:.1f}%, "
              f"EBITDA/Int={ratios['ebitda_to_interest_x']:.1f}x")
        return result["final_rating"], ratios
    except Exception as e:
        print(f"\n  S&P Engine: ERROR - {e}")
        return f"ERROR: {e}", None


def _run_moodys_engine(financials, moodys_sector):
    """Run Moody's engine for a company. Returns (sp_equiv, metrics) or (error_str, None)."""
    try:
        result = rate_company_moodys(
            financials=financials, methodology_id=moodys_sector, quant_only=True,
        )
        metrics = result["computed_metrics"]
        print(f"\n  Moody's Engine:")
        print(f"    Moody's Rating: {result['moody_rating']} (S&P equiv: {result['sp_equivalent']})")
        print(f"    Composite Score: {result['composite_score']:.2f}")
        print(f"    Key metrics: Debt/EBITDA={metrics['debt_ebitda_x']:.2f}x, "
              f"EBIT/Int={metrics['ebit_interest_x']:.1f}x, "
              f"RCF/NetDebt={metrics['rcf_net_debt_pct']:.1f}%")
        return result["sp_equivalent"], metrics
    except Exception as e:
        print(f"\n  Moody's Engine: ERROR - {e}")
        return f"ERROR: {e}", None


def _compare_ratings(sp_rating, sp_ratios, moody_sp_equiv, name):
    """Compare S&P and Moody's ratings. Returns a result dict."""
    if isinstance(sp_rating, str) and sp_rating in SP_SCALE and moody_sp_equiv in SP_SCALE:
        diff = notch_difference(sp_rating, moody_sp_equiv)
        if abs(diff) <= 1:
            agreement = "STRONG AGREEMENT"
        elif abs(diff) <= 2:
            agreement = "MODERATE AGREEMENT"
        else:
            agreement = f"DIVERGENCE ({abs(diff)} notches)"

        debt_ebitda = sp_ratios["debt_to_ebitda_x"] if sp_ratios else 0
        if debt_ebitda < 2.0: expected_range = "A to AA"
        elif debt_ebitda < 3.5: expected_range = "BBB to A"
        elif debt_ebitda < 5.0: expected_range = "BB to BBB"
        else: expected_range = "B to BB"

        print(f"\n  COMPARISON:")
        print(f"    S&P Final:     {sp_rating}")
        print(f"    Moody's equiv: {moody_sp_equiv}")
        print(f"    Notch diff:    {abs(diff)} ({agreement})")
        print(f"    Expected range (from Debt/EBITDA={debt_ebitda:.1f}x): {expected_range}")

        return {"company": name, "sp_rating": sp_rating, "moodys_sp_equiv": moody_sp_equiv,
                "notch_diff": abs(diff), "agreement": agreement, "debt_ebitda": debt_ebitda}
    else:
        print(f"\n  COMPARISON: Cannot compare (one or both engines errored)")
        return {"company": name, "sp_rating": str(sp_rating), "moodys_sp_equiv": str(moody_sp_equiv),
                "notch_diff": None, "agreement": "ERROR"}


def _print_summary(results):
    """Print the final summary table."""
    print(f"\n\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"\n{'Company':<30} {'S&P':<8} {'Moody→SP':<10} {'Diff':<6} {'Agreement'}")
    print("-" * 80)
    for r in results:
        diff_str = str(r["notch_diff"]) if r["notch_diff"] is not None else "N/A"
        print(f"{r['company']:<30} {r['sp_rating']:<8} {r['moodys_sp_equiv']:<10} {diff_str:<6} {r['agreement']}")

    valid = [r for r in results if r["notch_diff"] is not None]
    if valid:
        avg_diff = sum(r["notch_diff"] for r in valid) / len(valid)
        strong = sum(1 for r in valid if r["notch_diff"] <= 1)
        print(f"\nAverage notch difference: {avg_diff:.1f}")
        print(f"Strong agreement (≤1 notch): {strong}/{len(valid)}")
        print(f"Engines {'CONVERGE well' if avg_diff <= 2 else 'DIVERGE significantly'}")


def run_harness():
    print("=" * 80)
    print("CROSS-ENGINE TEST HARNESS")
    print("S&P Engine vs Moody's Engine — Same Financials, Different Methodologies")
    print("=" * 80)

    results = []
    for name, company in TEST_COMPANIES.items():
        print(f"\n{'=' * 70}")
        print(f"COMPANY: {name}")
        print(f"Description: {company['description']}")
        print(f"S&P sector: {company['sp_sector']}, Moody's sector: {company['moodys_sector']}")
        print(f"{'=' * 70}")

        sp_rating, sp_ratios = _run_sp_engine(company["financials"], company["sp_sector"])
        moody_sp_equiv, _ = _run_moodys_engine(company["financials"], company["moodys_sector"])
        results.append(_compare_ratings(sp_rating, sp_ratios, moody_sp_equiv, name))

    _print_summary(results)


if __name__ == "__main__":
    run_harness()
