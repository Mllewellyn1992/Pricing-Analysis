"""
Test harness for S&P rating engine.
Run with: python -m pytest tests/test_sp.py -v
"""

import sys
from pathlib import Path

# Add engines to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.sp_engine import rate_company_sp


def test_sp_healthy_software_company():
    """
    Test: A healthy NZ software company with moderate leverage.
    Expected: BBB range rating (moderate risk)
    """
    financials = {
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
    }

    result = rate_company_sp(
        financials,
        sector_id="technology_software_and_services",
        quant_only=True
    )

    print("\n" + "=" * 60)
    print("TEST: Healthy Software Company")
    print("=" * 60)
    print(f"Anchor Rating: {result['anchor_rating']}")
    print(f"Final Rating: {result['final_rating']}")
    print(f"Business Risk Score: {result['business_risk_score']}")
    print(f"Financial Risk Score: {result['financial_risk_score']}")
    print("\nComputed Ratios:")
    for key, val in result['computed_ratios'].items():
        print(f"  {key}: {val:.2f}")

    # Assertions
    assert result['anchor_rating'] is not None, "Anchor rating should not be None"
    assert result['final_rating'] is not None, "Final rating should not be None"
    assert 1 <= result['business_risk_score'] <= 6, "Business risk score must be 1-6"
    assert 1 <= result['financial_risk_score'] <= 6, "Financial risk score must be 1-6"
    assert result['computed_ratios']['ebitda_mn'] > 0, "EBITDA should be positive"
    assert result['computed_ratios']['ffo_mn'] > 0, "FFO should be positive"

    print("\nTest PASSED: All assertions satisfied")
    return result


def test_sp_leveraged_company():
    """
    Test: A leveraged company with higher debt load.
    Expected: A rating potentially in the BB-B range (higher risk)
    """
    financials = {
        "revenue_mn": 100.0,
        "ebit_mn": 20.0,
        "depreciation_mn": 5.0,
        "amortization_mn": 3.0,
        "interest_expense_mn": 4.0,
        "cash_interest_paid_mn": 3.5,
        "cash_taxes_paid_mn": 4.0,
        "total_debt_mn": 80.0,
        "cash_mn": 10.0,
        "avg_capital_mn": 60.0,
        "cfo_mn": 25.0,
        "capex_mn": 8.0,
        "dividends_paid_mn": 3.0,
        "share_buybacks_mn": 0.0,
    }

    result = rate_company_sp(
        financials,
        sector_id="metals_production_and_processing",  # Higher industry risk
        cyclicality=5,
        competitive_risk=4,
        quant_only=True
    )

    print("\n" + "=" * 60)
    print("TEST: Leveraged Mining Company")
    print("=" * 60)
    print(f"Anchor Rating: {result['anchor_rating']}")
    print(f"Final Rating: {result['final_rating']}")
    print(f"Business Risk Score: {result['business_risk_score']}")
    print(f"Financial Risk Score: {result['financial_risk_score']}")
    print("\nComputed Ratios:")
    for key, val in result['computed_ratios'].items():
        print(f"  {key}: {val:.2f}")

    # Assertions
    assert result['anchor_rating'] is not None, "Anchor rating should not be None"
    assert result['final_rating'] is not None, "Final rating should not be None"
    assert result['computed_ratios']['debt_to_ebitda_x'] > 2, "Debt/EBITDA should be > 2 (leveraged)"

    print("\nTest PASSED: All assertions satisfied")
    return result


def test_sp_strong_utility():
    """
    Test: A strong regulated utility (low cyclicality, stable cash flows).
    Expected: A rating in the A-BBB range (lower risk)
    """
    financials = {
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
    }

    result = rate_company_sp(
        financials,
        sector_id="regulated_utilities",
        cyclicality=1,
        competitive_risk=2,
        quant_only=True
    )

    print("\n" + "=" * 60)
    print("TEST: Strong Regulated Utility")
    print("=" * 60)
    print(f"Anchor Rating: {result['anchor_rating']}")
    print(f"Final Rating: {result['final_rating']}")
    print(f"Business Risk Score: {result['business_risk_score']}")
    print(f"Financial Risk Score: {result['financial_risk_score']}")
    print("\nComputed Ratios:")
    for key, val in result['computed_ratios'].items():
        print(f"  {key}: {val:.2f}")

    # Assertions
    assert result['anchor_rating'] is not None, "Anchor rating should not be None"
    assert result['final_rating'] is not None, "Final rating should not be None"
    assert result['business_risk_score'] <= 3, "Utility business risk should be low"

    print("\nTest PASSED: All assertions satisfied")
    return result


def test_sp_sector_consistency():
    """
    Test that different sectors with same fundamentals produce different ratings
    based on industry risk.
    """
    # Same financials, different sectors
    financials = {
        "revenue_mn": 75.0,
        "ebit_mn": 15.0,
        "depreciation_mn": 4.0,
        "amortization_mn": 1.0,
        "interest_expense_mn": 2.0,
        "cash_interest_paid_mn": 1.8,
        "cash_taxes_paid_mn": 3.5,
        "total_debt_mn": 30.0,
        "cash_mn": 10.0,
        "avg_capital_mn": 45.0,
        "cfo_mn": 18.0,
        "capex_mn": 5.0,
        "dividends_paid_mn": 2.0,
        "share_buybacks_mn": 0.0,
    }

    # Low-risk sector
    result_low_risk = rate_company_sp(
        financials,
        sector_id="regulated_utilities",
        cyclicality=1,
        competitive_risk=2,
        quant_only=True
    )

    # High-risk sector
    result_high_risk = rate_company_sp(
        financials,
        sector_id="metals_production_and_processing",
        cyclicality=5,
        competitive_risk=4,
        quant_only=True
    )

    print("\n" + "=" * 60)
    print("TEST: Sector Consistency (Same Financials)")
    print("=" * 60)
    print(f"Low-risk sector (Utilities):        {result_low_risk['final_rating']}")
    print(f"High-risk sector (Metals Prod):     {result_high_risk['final_rating']}")

    # The utility should have equal or better rating
    utility_idx = ["CCC", "B-", "B", "B+", "BB", "BB+", "BBB", "BBB+", "A", "A+", "AA", "AA+", "AAA"].index(result_low_risk['final_rating'])
    mining_idx = ["CCC", "B-", "B", "B+", "BB", "BB+", "BBB", "BBB+", "A", "A+", "AA", "AA+", "AAA"].index(result_high_risk['final_rating'])

    assert utility_idx >= mining_idx, f"Utility should rate >= Metals Prod. Utility: {result_low_risk['final_rating']}, Metals Prod: {result_high_risk['final_rating']}"

    print("\nTest PASSED: Sector affects rating as expected")
    return (result_low_risk, result_high_risk)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("S&P RATING ENGINE TEST HARNESS")
    print("=" * 60)

    try:
        test_sp_healthy_software_company()
        test_sp_leveraged_company()
        test_sp_strong_utility()
        test_sp_sector_consistency()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
