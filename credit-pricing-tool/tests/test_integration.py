"""
End-to-End Integration Test
============================
Tests the complete pipeline: financials → rating → pricing → comparison.
Validates all components work together correctly.

Usage:
    cd credit-pricing-tool/
    python -m tests.test_integration
"""

import sys
import os
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.sp_engine import rate_company_sp
from engines.sp_defaults import get_defaults, SP_INDUSTRY_DEFAULTS
from engines.moodys_wrapper import (
    rate_company_moodys, moody_to_sp_rating, list_moodys_methodologies,
    compute_universal_metrics, compute_total_debt, compute_ffo, compute_rcf,
)
from api.pricing.engine import load_pricing_matrix, lookup_spread, get_live_base_rates


# ── Test Data ────────────────────────────────────────────────────────────────

SAMPLE_FINANCIALS = {
    "revenue_mn": 120.0,
    "ebit_mn": 25.0,
    "depreciation_mn": 8.0,
    "amortization_mn": 3.0,
    "interest_expense_mn": 4.0,
    "cash_interest_paid_mn": 3.5,
    "cash_taxes_paid_mn": 6.0,
    "total_debt_mn": 55.0,
    "cash_mn": 12.0,
    "cash_like_mn": 3.0,
    "avg_capital_mn": 80.0,
    "cfo_mn": 30.0,
    "capex_mn": 10.0,
    "common_dividends_mn": 4.0,
    "preferred_dividends_mn": 0.0,
    "minority_dividends_mn": 0.0,
    "dividends_paid_mn": 4.0,
    "share_buybacks_mn": 0.0,
    # Moody's specifics
    "st_debt_mn": 5.0,
    "cpltd_mn": 8.0,
    "lt_debt_net_mn": 40.0,
    "capital_leases_mn": 2.0,
    "nwc_current_mn": 20.0,
    "nwc_prior_mn": 17.0,
    "lt_operating_assets_current_mn": 60.0,
    "lt_operating_assets_prior_mn": 55.0,
    "assets_current_mn": 150.0,
    "assets_prior_mn": 140.0,
    "total_equity_mn": 70.0,
    "minority_interest_mn": 2.0,
    "deferred_taxes_mn": 5.0,
}

SP_SCALE = [
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
    "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D"
]

SP_TO_MOODYS_SECTOR = {
    "technology_software_and_services": "software",
    "mining": "steel",
    "regulated_utilities": "telecommunications_service_providers",
    "retail_and_restaurants": "retail_and_apparel",
    "engineering_and_construction": "construction",
    "pharmaceuticals": "pharmaceuticals",
    "aerospace_and_defense": "aerospace_defense",
    "building_materials": "building_materials",
    "chemicals": "chemicals",
    "consumer_durables": "consumer_durables",
}

passed = 0
failed = 0
errors = []


def run_test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  ✓ {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ✗ {name}: {e}")


# ── Test 1: S&P Engine ───────────────────────────────────────────────────────

def test_sp_engine_basic():
    """S&P engine returns a valid rating."""
    defaults = get_defaults("building_materials")
    result = rate_company_sp(
        financials=SAMPLE_FINANCIALS,
        sector_id="building_materials",
        cyclicality=defaults["cyclicality"],
        competitive_risk=defaults["competitive_risk"],
        country_risk=2,
        quant_only=True,
    )
    assert result["final_rating"] in SP_SCALE, f"Bad rating: {result['final_rating']}"
    assert 1 <= result["business_risk_score"] <= 6
    assert 1 <= result["financial_risk_score"] <= 6
    assert "computed_ratios" in result


def test_sp_all_sectors():
    """S&P engine works for all defined sectors."""
    failures = []
    for sector_id in SP_INDUSTRY_DEFAULTS.keys():
        try:
            defaults = get_defaults(sector_id)
            result = rate_company_sp(
                financials=SAMPLE_FINANCIALS,
                sector_id=sector_id,
                cyclicality=defaults["cyclicality"],
                competitive_risk=defaults["competitive_risk"],
                country_risk=2,
                quant_only=True,
            )
            if result["final_rating"] not in SP_SCALE:
                failures.append(f"{sector_id}: bad rating {result['final_rating']}")
        except Exception as e:
            failures.append(f"{sector_id}: {e}")
    assert not failures, f"Failures: {failures}"


def test_sp_sector_differentiation():
    """Different sectors produce different ratings (not all BBB)."""
    ratings = set()
    for sector_id in ["technology_software_and_services", "mining", "regulated_utilities",
                       "retail_and_restaurants", "building_materials"]:
        defaults = get_defaults(sector_id)
        result = rate_company_sp(
            financials=SAMPLE_FINANCIALS,
            sector_id=sector_id,
            cyclicality=defaults["cyclicality"],
            competitive_risk=defaults["competitive_risk"],
            country_risk=2,
            quant_only=True,
        )
        ratings.add(result["final_rating"])
    assert len(ratings) >= 2, f"No differentiation — all ratings same: {ratings}"


# ── Test 2: Moody's Engine ───────────────────────────────────────────────────

def test_moodys_engine_basic():
    """Moody's engine returns a valid rating."""
    result = rate_company_moodys(
        financials=SAMPLE_FINANCIALS,
        methodology_id="building_materials",
        quant_only=True,
    )
    assert result["moody_rating"] is not None, "No rating returned"
    assert result["sp_equivalent"] is not None, "No SP equivalent"
    assert result["composite_score"] > 0


def test_moodys_metrics():
    """Universal metrics are computed correctly."""
    metrics = compute_universal_metrics(SAMPLE_FINANCIALS)
    assert metrics["revenue_usd_billion"] == 0.12  # 120/1000
    assert abs(metrics["debt_ebitda_x"] - (55.0 / 36.0)) < 0.01  # total_debt/ebitda
    assert metrics["total_debt"] == 55.0  # 5+8+40+2
    assert metrics["ebitda"] == 36.0  # 25+8+3


def test_moodys_all_mapped_sectors():
    """Moody's engine works for all mapped sectors."""
    failures = []
    for moodys_id in SP_TO_MOODYS_SECTOR.values():
        try:
            result = rate_company_moodys(
                financials=SAMPLE_FINANCIALS,
                methodology_id=moodys_id,
                quant_only=True,
            )
            if result["moody_rating"] is None:
                failures.append(f"{moodys_id}: no rating")
        except Exception as e:
            failures.append(f"{moodys_id}: {e}")
    assert not failures, f"Failures: {failures}"


# ── Test 3: Pricing Engine ───────────────────────────────────────────────────

def test_pricing_matrix_load():
    """Pricing matrix loads correctly."""
    matrix = load_pricing_matrix()
    tenors = matrix.get("tenors", matrix)  # Support both formats
    assert "1" in tenors, "Missing tenor 1"
    assert "5" in tenors, "Missing tenor 5"
    assert "BBB" in tenors["3"], "Missing BBB in tenor 3"
    assert tenors["3"]["BBB"]["min_bps"] < tenors["3"]["BBB"]["max_bps"]


def test_pricing_lookup_all_ratings():
    """Spread lookup works for all investment-grade ratings."""
    matrix = load_pricing_matrix()
    for rating in ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]:
        spread = lookup_spread(rating, 3, matrix)
        assert spread["min_bps"] > 0, f"{rating}: min_bps should be > 0"
        assert spread["max_bps"] > spread["min_bps"], f"{rating}: max should > min"
        assert spread["mid_bps"] == (spread["min_bps"] + spread["max_bps"]) / 2


def test_pricing_tenor_curve():
    """Longer tenors have higher spreads."""
    matrix = load_pricing_matrix()
    for rating in ["BBB", "A", "BB"]:
        spread_1y = lookup_spread(rating, 1, matrix)
        spread_5y = lookup_spread(rating, 5, matrix)
        assert spread_5y["mid_bps"] > spread_1y["mid_bps"], \
            f"{rating}: 5yr should > 1yr"


def test_pricing_credit_curve():
    """Lower credit quality has higher spreads."""
    matrix = load_pricing_matrix()
    spread_aa = lookup_spread("AA", 3, matrix)
    spread_bbb = lookup_spread("BBB", 3, matrix)
    spread_b = lookup_spread("B", 3, matrix)
    assert spread_bbb["mid_bps"] > spread_aa["mid_bps"], "BBB should > AA"
    assert spread_b["mid_bps"] > spread_bbb["mid_bps"], "B should > BBB"


# ── Test 4: Full Pipeline ────────────────────────────────────────────────────

def test_full_pipeline():
    """Complete pipeline: financials → S&P + Moody's → pricing → comparison."""
    sector_id = "building_materials"
    moodys_id = "building_materials"
    actual_rate = 7.50  # %

    # Step 1: Rate with S&P
    defaults = get_defaults(sector_id)
    sp = rate_company_sp(
        financials=SAMPLE_FINANCIALS,
        sector_id=sector_id,
        cyclicality=defaults["cyclicality"],
        competitive_risk=defaults["competitive_risk"],
        country_risk=2,
        quant_only=True,
    )

    # Step 2: Rate with Moody's
    moodys = rate_company_moodys(
        financials=SAMPLE_FINANCIALS,
        methodology_id=moodys_id,
        quant_only=True,
    )

    # Step 3: Blend ratings (simple: use S&P for now)
    blended_rating = sp["final_rating"]

    # Step 4: Look up spread
    matrix = load_pricing_matrix()
    spread = lookup_spread(blended_rating, 3, matrix)

    # Step 5: Compute expected rate
    base_rate = get_live_base_rates()["corporate"]
    expected_min = base_rate + spread["min_bps"] / 100.0
    expected_max = base_rate + spread["max_bps"] / 100.0
    expected_mid = base_rate + spread["mid_bps"] / 100.0

    # Step 6: Compare
    delta = actual_rate - expected_mid

    # Validate all steps produced reasonable results
    assert sp["final_rating"] in SP_SCALE
    assert moodys["moody_rating"] is not None
    assert spread["min_bps"] > 0
    assert expected_min < expected_max
    assert expected_mid > base_rate
    assert isinstance(delta, float)

    return {
        "sp_rating": sp["final_rating"],
        "moodys_rating": moodys["moody_rating"],
        "moodys_sp_equiv": moodys["sp_equivalent"],
        "blended_rating": blended_rating,
        "spread_bps": f"{spread['min_bps']:.0f}-{spread['max_bps']:.0f}",
        "base_rate": f"{base_rate:.2f}%",
        "expected_rate": f"{expected_min:.2f}%-{expected_max:.2f}%",
        "actual_rate": f"{actual_rate:.2f}%",
        "delta": f"{delta:+.2f}%",
        "assessment": "OVERPAYING" if delta > 0.25 else "FAIR" if delta > -0.25 else "GOOD DEAL",
    }


def test_multi_sector_pipeline():
    """Run full pipeline across multiple sectors and verify consistency."""
    sectors = [
        ("technology_software_and_services", "software"),
        ("mining", "steel"),
        ("regulated_utilities", "telecommunications_service_providers"),
        ("building_materials", "building_materials"),
        ("pharmaceuticals", "pharmaceuticals"),
    ]
    matrix = load_pricing_matrix()
    results = []

    for sp_sector, moodys_sector in sectors:
        defaults = get_defaults(sp_sector)
        sp = rate_company_sp(
            financials=SAMPLE_FINANCIALS,
            sector_id=sp_sector,
            cyclicality=defaults["cyclicality"],
            competitive_risk=defaults["competitive_risk"],
            country_risk=2,
            quant_only=True,
        )
        moodys = rate_company_moodys(
            financials=SAMPLE_FINANCIALS,
            methodology_id=moodys_sector,
            quant_only=True,
        )
        spread = lookup_spread(sp["final_rating"], 3, matrix)

        results.append({
            "sp_sector": sp_sector,
            "sp_rating": sp["final_rating"],
            "moodys_rating": moodys["moody_rating"],
            "spread_mid": spread["mid_bps"],
        })

    # At least 2 different ratings across sectors
    ratings = set(r["sp_rating"] for r in results)
    assert len(ratings) >= 2, f"All sectors same rating: {ratings}"

    # Higher-risk sectors should have wider spreads
    tech_spread = next(r["spread_mid"] for r in results if r["sp_sector"] == "technology_software_and_services")
    mining_spread = next(r["spread_mid"] for r in results if r["sp_sector"] == "mining")
    # Tech (low cyclicality) should get tighter spread than mining (high cyclicality)
    # This validates the full chain: defaults → rating → pricing
    assert tech_spread <= mining_spread, \
        f"Tech spread ({tech_spread}) should be ≤ mining ({mining_spread})"


# ── Test 5: Base Rate Scraper ────────────────────────────────────────────────

def test_base_rates_defaults():
    """NZ base rates are available (live or fallback)."""
    rates = get_live_base_rates()
    assert "corporate" in rates
    assert "working_capital" in rates
    assert rates["corporate"] > 0
    assert rates["working_capital"] > rates["corporate"]


def test_scraper_import():
    """Scraper module imports correctly."""
    from api.scrape.scraper import get_cached_rates, compute_market_average, HARDCODED_DEFAULTS
    assert len(HARDCODED_DEFAULTS) == 5
    assert all("bank" in d for d in HARDCODED_DEFAULTS)


# ── Test 6: Extraction Pipeline ──────────────────────────────────────────────

def test_extraction_imports():
    """Extraction modules import correctly."""
    from extraction.pdf_extractor import extract_text_from_pdf
    from extraction.financial_mapper import map_financials_heuristic
    from extraction.sector_classifier import classify_sector_heuristic


def test_sector_classifier_heuristic():
    """Heuristic sector classifier returns valid sectors."""
    from extraction.sector_classifier import classify_sector_heuristic
    result = classify_sector_heuristic("We develop enterprise software and cloud computing solutions")
    assert "sp_sector" in result
    assert "moodys_sector" in result
    assert result["confidence"] > 0


# ── Test 7: Rating Scale Consistency ─────────────────────────────────────────

def test_moody_sp_conversion():
    """Moody's to S&P rating conversion works."""
    assert moody_to_sp_rating("Aaa") == "AAA"
    assert moody_to_sp_rating("Baa2") == "BBB"
    assert moody_to_sp_rating("Ba1") == "BB+"
    assert moody_to_sp_rating("B3") == "B-"


# ── Run All Tests ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 80)
    print("CREDIT PRICING TOOL — INTEGRATION TEST SUITE")
    print("=" * 80)

    print("\n[1] S&P Engine")
    run_test("Basic rating", test_sp_engine_basic)
    run_test("All sectors", test_sp_all_sectors)
    run_test("Sector differentiation", test_sp_sector_differentiation)

    print("\n[2] Moody's Engine")
    run_test("Basic rating", test_moodys_engine_basic)
    run_test("Metric computation", test_moodys_metrics)
    run_test("All mapped sectors", test_moodys_all_mapped_sectors)

    print("\n[3] Pricing Engine")
    run_test("Matrix loading", test_pricing_matrix_load)
    run_test("All ratings lookup", test_pricing_lookup_all_ratings)
    run_test("Tenor curve (longer = wider)", test_pricing_tenor_curve)
    run_test("Credit curve (lower quality = wider)", test_pricing_credit_curve)

    print("\n[4] Full Pipeline")
    run_test("Single company pipeline", test_full_pipeline)
    run_test("Multi-sector pipeline", test_multi_sector_pipeline)

    print("\n[5] Base Rates")
    run_test("Defaults configured", test_base_rates_defaults)
    run_test("Scraper imports", test_scraper_import)

    print("\n[6] Extraction Pipeline")
    run_test("Module imports", test_extraction_imports)
    run_test("Heuristic sector classifier", test_sector_classifier_heuristic)

    print("\n[7] Rating Scale")
    run_test("Moody's ↔ S&P conversion", test_moody_sp_conversion)

    # Print full pipeline result
    print("\n" + "=" * 80)
    print("FULL PIPELINE DEMO")
    print("=" * 80)
    try:
        result = test_full_pipeline()
        for k, v in result.items():
            print(f"  {k:>20}: {v}")
    except Exception as e:
        print(f"  Pipeline demo failed: {e}")

    # Summary
    total = passed + failed
    print(f"\n{'=' * 80}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    if errors:
        print("\nFailed tests:")
        for name, err in errors:
            print(f"  ✗ {name}: {err}")
    print(f"{'=' * 80}")

    sys.exit(1 if failed else 0)
