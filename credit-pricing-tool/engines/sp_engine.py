"""
S&P Rating Engine - Standalone implementation.
Combines rating_engine.py and app_S&P.py logic without Streamlit dependencies.

Exposes: rate_company_sp(financials, sector_id, cyclicality, competitive_risk, country_risk, quant_only)
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List

import yaml

# Config paths
CONFIG_DIR = Path(__file__).resolve().parent / "configs" / "sp"


class ConfigError(Exception):
    pass


class MetricError(Exception):
    pass


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load and validate YAML file."""
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ConfigError(f"Invalid YAML structure in {path}")
    return data


def load_sector_methodology(sector_id: str) -> Dict[str, Any]:
    """Load sector-specific methodology YAML."""
    path = CONFIG_DIR / "sector_specific" / f"{sector_id}.yaml"
    return load_yaml(path)


def _score_numeric_grid(
    grid: List[Dict[str, Any]], value: float, direction: str
) -> (float, str):
    """Find score and band for a numeric metric within a subfactor grid."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise MetricError("Numeric metric value is None or NaN")

    # Assume grid ordered best to worst
    for row in grid:
        band = row.get("band")
        score = row.get("score")
        lo = row.get("min")
        hi = row.get("max")

        if lo is None and hi is None:
            return float(score), str(band)
        if lo is None:
            if value < hi:
                return float(score), str(band)
        elif hi is None:
            if value >= lo:
                return float(score), str(band)
        else:
            if (value >= lo) and (value < hi):
                return float(score), str(band)

    worst = grid[-1]
    return float(worst["score"]), str(worst.get("band", "UNKNOWN"))


def _score_qualitative_grid(grid: List[Dict[str, Any]], raw_value: Any) -> (float, str):
    """Find score and band for a qualitative metric."""
    if raw_value is None:
        raise MetricError("Qualitative metric value is None")
    val_str = str(raw_value).strip()
    for row in grid:
        band = str(row.get("band")).strip()
        score = row.get("score")
        if val_str.lower() == band.lower():
            return float(score), band
    raise MetricError(f"Qualitative value '{val_str}' not found in grid")


def score_methodology(cfg: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generic methodology scorer using YAML config and metrics.
    Returns composite_score, factor_scores, subfactor_scores.
    """
    factors_cfg = cfg.get("factors", [])
    if not factors_cfg:
        raise ConfigError("No factors in methodology")

    subfactor_scores = []
    factor_scores = []

    for factor_cfg in factors_cfg:
        factor_weight = float(factor_cfg["weight_pct"])
        sf_cfgs = factor_cfg.get("subfactors", [])
        if not sf_cfgs:
            raise ConfigError(f"Factor '{factor_cfg['id']}' has no subfactors")

        sf_weight_total = 0.0
        sf_weighted_score_sum = 0.0

        for sf_cfg in sf_cfgs:
            metric_code = sf_cfg["metric"]
            direction = sf_cfg.get("direction", "higher_better")
            grid = sf_cfg.get("grid", [])
            value = metrics.get(metric_code)
            if not grid:
                raise ConfigError(
                    f"Subfactor '{sf_cfg['id']}' has no grid defined"
                )
            is_numeric = any(("min" in row or "max" in row) for row in grid)
            if direction == "qualitative" or not is_numeric:
                score, band = _score_qualitative_grid(grid, value)
            else:
                score, band = _score_numeric_grid(grid, float(value), direction)

            result = {
                "factor_id": factor_cfg["id"],
                "factor_name": factor_cfg["name"],
                "factor_weight_pct": factor_weight,
                "subfactor_id": sf_cfg["id"],
                "subfactor_name": sf_cfg["name"],
                "subfactor_weight_pct": float(sf_cfg["weight_pct"]),
                "metric_code": metric_code,
                "direction": direction,
                "input_value": value,
                "score": score,
                "band": band,
            }
            subfactor_scores.append(result)

            w = float(result["subfactor_weight_pct"])
            sf_weight_total += w
            sf_weighted_score_sum += result["score"] * w

        if sf_weight_total <= 0:
            raise ConfigError(
                f"Subfactor weights in factor '{factor_cfg['id']}' sum to zero"
            )

        factor_score = sf_weighted_score_sum / sf_weight_total
        factor_scores.append(
            {
                "factor_id": factor_cfg["id"],
                "factor_name": factor_cfg["name"],
                "factor_weight_pct": factor_weight,
                "score": factor_score,
            }
        )

    total_factor_weight = sum(f["factor_weight_pct"] for f in factor_scores)
    composite_score = (
        sum(f["score"] * f["factor_weight_pct"] for f in factor_scores)
        / total_factor_weight
    )

    return {
        "composite_score": composite_score,
        "factor_scores": factor_scores,
        "subfactor_scores": subfactor_scores,
    }


def _categorize_ratio(value: float, bands: list[dict], direction: str) -> str:
    """Categorize a numeric ratio into a band label."""
    for band in bands:
        lo = band.get("min")
        hi = band.get("max")
        label = band["label"]
        if lo is None and hi is None:
            return label
        if lo is None:
            if value < hi:
                return label
        elif hi is None:
            if value >= lo:
                return label
        else:
            if value >= lo and value < hi:
                return label
    return bands[-1]["label"]


def _label_to_financial_score(label: str) -> int:
    """Map financial risk label to score."""
    mapping = {
        "Minimal": 1,
        "Modest": 2,
        "Intermediate": 3,
        "Significant": 4,
        "Aggressive": 5,
        "Highly leveraged": 6,
    }
    return mapping.get(label, 6)


def _clamp_score(value: float, min_score: int = 1, max_score: int = 6) -> int:
    """Clamp score to valid range [1, 6]."""
    return max(min_score, min(max_score, int(round(value))))


def _rating_to_index(scale: list[str], rating: str) -> int:
    """Map rating to index in scale."""
    if rating not in scale:
        return len(scale) - 1
    return scale.index(rating)


def _apply_notches(scale: list[str], rating: str, notch_delta: int) -> str:
    """Apply notch adjustments to a rating."""
    idx = _rating_to_index(scale, rating)
    new_idx = max(0, min(len(scale) - 1, idx - notch_delta))
    return scale[new_idx]


def _extract_financial_inputs(financials: dict) -> dict:
    """Extract and compute derived financial metrics from raw inputs."""
    revenue_mn = financials.get("revenue_mn", 0.0)
    ebit_mn = financials.get("ebit_mn", 0.0)
    dep_mn = financials.get("depreciation_mn", 0.0)
    amort_mn = financials.get("amortization_mn", 0.0)
    interest_expense_mn = financials.get("interest_expense_mn", 0.0)
    cash_interest_paid_mn = financials.get("cash_interest_paid_mn", interest_expense_mn)
    cash_taxes_paid_mn = financials.get("cash_taxes_paid_mn", ebit_mn * 0.28)
    total_debt_mn = financials.get("total_debt_mn",
        financials.get("st_debt_mn", 0.0) + financials.get("cpltd_mn", 0.0) + financials.get("lt_debt_net_mn", 0.0)
    )
    cash_mn = financials.get("cash_mn", 0.0)
    avg_capital_mn = financials.get("avg_capital_mn",
        total_debt_mn + financials.get("total_equity_mn", 0.0)
    )
    cfo_mn = financials.get("cfo_mn", 0.0)
    capex_mn = financials.get("capex_mn", 0.0)
    dividends_paid_mn = financials.get("dividends_paid_mn",
        financials.get("common_dividends_mn", 0.0)
    )
    share_buybacks_mn = financials.get("share_buybacks_mn", 0.0)

    ebitda_mn = ebit_mn + dep_mn + amort_mn
    ffo_mn = ebitda_mn - cash_interest_paid_mn - cash_taxes_paid_mn
    return {
        "revenue_mn": revenue_mn, "ebit_mn": ebit_mn, "ebitda_mn": ebitda_mn,
        "ffo_mn": ffo_mn, "total_debt_mn": total_debt_mn, "cash_mn": cash_mn,
        "cfo_mn": cfo_mn, "capex_mn": capex_mn, "avg_capital_mn": avg_capital_mn,
        "cash_interest_paid_mn": cash_interest_paid_mn, "cash_taxes_paid_mn": cash_taxes_paid_mn,
        "interest_expense_mn": interest_expense_mn, "dividends_paid_mn": dividends_paid_mn,
        "share_buybacks_mn": share_buybacks_mn,
    }


def _compute_ratios(inputs: dict) -> dict:
    """Compute all derived financial ratios from extracted inputs."""
    ebitda_mn = inputs["ebitda_mn"]
    ffo_mn = inputs["ffo_mn"]
    total_debt_mn = inputs["total_debt_mn"]
    cfo_mn = inputs["cfo_mn"]
    capex_mn = inputs["capex_mn"]
    ebit_mn = inputs["ebit_mn"]
    revenue_mn = inputs["revenue_mn"]
    avg_capital_mn = inputs["avg_capital_mn"]
    cash_interest_paid_mn = inputs["cash_interest_paid_mn"]
    interest_expense_mn = inputs["interest_expense_mn"]
    dividends_paid_mn = inputs["dividends_paid_mn"]
    share_buybacks_mn = inputs["share_buybacks_mn"]

    ffo_to_debt_pct = (ffo_mn / total_debt_mn) * 100.0 if total_debt_mn else 0.0
    debt_to_ebitda_x = (total_debt_mn / ebitda_mn) if ebitda_mn else 0.0
    ffo_to_cash_interest_x = ffo_mn / cash_interest_paid_mn if cash_interest_paid_mn else 0.0
    ebitda_to_interest_x = ebitda_mn / interest_expense_mn if interest_expense_mn else 0.0
    cfo_to_debt_pct = (cfo_mn / total_debt_mn) * 100.0 if total_debt_mn else 0.0
    focf_mn = cfo_mn - capex_mn
    focf_to_debt_pct = (focf_mn / total_debt_mn) * 100.0 if total_debt_mn else 0.0
    dcf_mn = focf_mn - dividends_paid_mn - share_buybacks_mn
    dcf_to_debt_pct = (dcf_mn / total_debt_mn) * 100.0 if total_debt_mn else 0.0
    ebit_margin_pct = (ebit_mn / revenue_mn) * 100.0 if revenue_mn else 0.0
    ebitda_margin_pct = (ebitda_mn / revenue_mn) * 100.0 if revenue_mn else 0.0
    return_on_capital_pct = (ebit_mn / avg_capital_mn) * 100.0 if avg_capital_mn else 0.0

    return {
        "ebitda_mn": ebitda_mn, "ffo_mn": ffo_mn, "ffo_to_debt_pct": ffo_to_debt_pct,
        "debt_to_ebitda_x": debt_to_ebitda_x, "ffo_to_cash_interest_x": ffo_to_cash_interest_x,
        "ebitda_to_interest_x": ebitda_to_interest_x, "cfo_to_debt_pct": cfo_to_debt_pct,
        "focf_to_debt_pct": focf_to_debt_pct, "dcf_to_debt_pct": dcf_to_debt_pct,
        "ebit_margin_pct": ebit_margin_pct, "ebitda_margin_pct": ebitda_margin_pct,
        "return_on_capital_pct": return_on_capital_pct,
    }


def _compute_modifiers(corporate_cfg: dict, quant_only: bool, financial_policy: str,
                       capital_structure: str, diversification: str, comparable_ratings: str,
                       mg_ownership_structure: str, mg_board_structure: str,
                       mg_risk_management: str, mg_transparency: str, mg_management: str) -> tuple:
    """Compute notch delta and management assessment modifiers."""
    notch_delta = 0
    mg_assessment = "neutral"
    if not quant_only:
        modifiers = corporate_cfg["modifiers"]
        notch_delta += modifiers["financial_policy"].get(financial_policy, 0)
        notch_delta += modifiers["capital_structure"].get(capital_structure, 0)
        notch_delta += modifiers["diversification"].get(diversification, 0)
        notch_delta += modifiers["comparable_ratings"].get(comparable_ratings, 0)

        mg_map = {"positive": 1, "neutral": 2, "negative": 3}
        mg_scores = [
            mg_map.get(mg_ownership_structure, 2), mg_map.get(mg_board_structure, 2),
            mg_map.get(mg_risk_management, 2), mg_map.get(mg_transparency, 2),
            mg_map.get(mg_management, 2),
        ]
        mg_avg = sum(mg_scores) / len(mg_scores)
        if mg_avg <= 1.5:
            mg_assessment = "positive"
        elif mg_avg <= 2.3:
            mg_assessment = "neutral"
        elif mg_avg <= 2.8:
            mg_assessment = "moderately_negative"
            notch_delta -= 1
        else:
            mg_assessment = "negative"
            notch_delta -= 2
    return notch_delta, mg_assessment


def _get_cp_metrics(quant_only: bool, competitive_advantage: int, scale_scope: int, operating_efficiency: int) -> dict:
    """Build competitive position metrics based on quant_only flag."""
    if quant_only:
        return {
            "competitive_advantage_band": "3", "scale_scope_diversity_band": "3",
            "operating_efficiency_band": "3",
        }
    else:
        return {
            "competitive_advantage_band": str(competitive_advantage),
            "scale_scope_diversity_band": str(scale_scope),
            "operating_efficiency_band": str(operating_efficiency),
        }


def _compute_business_and_financial_risks(corporate_cfg: dict, industry_cfg: dict, sector_cfg: dict,
                                             computed_ratios: dict, quant_only: bool,
                                             competitive_advantage: int, scale_scope: int,
                                             operating_efficiency: int, cyclicality: int,
                                             competitive_risk: int, country_risk: int) -> tuple:
    """Compute business and financial risk scores with CICRA matrix."""
    cp_metrics = _get_cp_metrics(quant_only, competitive_advantage, scale_scope, operating_efficiency)
    cp_result = score_methodology(sector_cfg, cp_metrics)
    competitive_position_score = _clamp_score(cp_result["composite_score"])

    industry_matrix = industry_cfg["matrix"]
    industry_risk_score = industry_matrix[cyclicality - 1][competitive_risk - 1]
    cicra_matrix = corporate_cfg["cicra_matrix"]
    cicra_score = cicra_matrix[industry_risk_score - 1][country_risk - 1]
    business_risk_score = _clamp_score((cicra_score + competitive_position_score) / 2)

    table_key = "standard" if cicra_score > 2 else ("medial" if cicra_score == 2 else "low")
    ratio_table = corporate_cfg["financial_risk_tables"][table_key]
    ffo_label = _categorize_ratio(
        computed_ratios["ffo_to_debt_pct"], ratio_table["FFO_to_debt_pct"]["bands"], "higher_better"
    )
    debt_label = _categorize_ratio(
        computed_ratios["debt_to_ebitda_x"], ratio_table["debt_to_EBITDA_x"]["bands"], "lower_better"
    )
    core_score = max(_label_to_financial_score(ffo_label), _label_to_financial_score(debt_label))
    financial_risk_score = _clamp_score(core_score)

    return (cp_result, competitive_position_score, industry_risk_score, cicra_score,
            business_risk_score, financial_risk_score, ffo_label, debt_label, core_score)


def _apply_liquidity_cap(corporate_cfg: dict, liquidity_cfg: dict, quant_only: bool,
                         liquidity_descriptor: str, rating_after_modifiers: str) -> str:
    """Apply liquidity cap to final rating."""
    cap_rating = liquidity_cfg["descriptors"]["adequate"].get("cap_rating") if quant_only \
        else liquidity_cfg["descriptors"][liquidity_descriptor].get("cap_rating")
    final_rating = rating_after_modifiers
    if cap_rating:
        rating_scale = corporate_cfg["rating_scale"]
        cap_idx = _rating_to_index(rating_scale, cap_rating)
        final_idx = _rating_to_index(rating_scale, rating_after_modifiers)
        if final_idx < cap_idx:
            final_rating = cap_rating
    return final_rating


def _build_workings(financials: dict, sector_id: str, cyclicality: int, competitive_risk: int,
                    country_risk: int, quant_only: bool, computed_ratios: dict,
                    competitive_position_score: int, industry_risk_score: int, cicra_score: int,
                    business_risk_score: int, ffo_label: str, debt_label: str, core_score: float,
                    financial_risk_score: int, notch_delta: int, mg_assessment: str,
                    liquidity_sources_mn: float, liquidity_uses_mn: float) -> dict:
    """Build the workings audit trail."""
    liquidity_ratio = (liquidity_sources_mn / liquidity_uses_mn) if liquidity_uses_mn else 0.0
    liquidity_surplus = liquidity_sources_mn - liquidity_uses_mn

    return {
        "input_financials": financials,
        "sector_id": sector_id,
        "cyclicality": cyclicality,
        "competitive_risk": competitive_risk,
        "country_risk": country_risk,
        "quant_only": quant_only,
        "computed_ratios": computed_ratios,
        "competitive_position_score": competitive_position_score,
        "industry_risk_score": industry_risk_score,
        "cicra_score": cicra_score,
        "business_risk_score": business_risk_score,
        "financial_risk_profile": {
            "ffo_to_debt_label": ffo_label,
            "debt_to_ebitda_label": debt_label,
            "core_score": core_score,
        },
        "financial_risk_score": financial_risk_score,
        "modifiers": {
            "notch_delta": notch_delta,
            "mg_assessment": mg_assessment,
        },
        "liquidity": {
            "sources_mn": liquidity_sources_mn,
            "uses_mn": liquidity_uses_mn,
            "ratio": liquidity_ratio,
            "surplus_mn": liquidity_surplus,
        },
    }


def rate_company_sp(
    financials: dict,
    sector_id: str,
    cyclicality: int = 3,
    competitive_risk: int = 3,
    country_risk: int = 2,
    quant_only: bool = True,
    competitive_advantage: int = 3,
    scale_scope: int = 3,
    operating_efficiency: int = 3,
    financial_policy: str = "neutral",
    capital_structure: str = "neutral",
    diversification: str = "neutral",
    comparable_ratings: str = "neutral",
    mg_ownership_structure: str = "neutral",
    mg_board_structure: str = "neutral",
    mg_risk_management: str = "neutral",
    mg_transparency: str = "neutral",
    mg_management: str = "neutral",
    liquidity_descriptor: str = "adequate",
    liquidity_sources_mn: float = 0.0,
    liquidity_uses_mn: float = 0.0,
) -> dict:
    """
    Compute S&P-style rating from financial metrics and qualitative inputs.

    Args:
        financials: dict with keys:
            revenue_mn, ebit_mn, depreciation_mn, amortization_mn,
            interest_expense_mn, cash_interest_paid_mn, cash_taxes_paid_mn,
            total_debt_mn, cash_mn, avg_capital_mn, cfo_mn, capex_mn,
            dividends_paid_mn, share_buybacks_mn
        sector_id: e.g. "technology_software_services"
        cyclicality: 1-6 industry risk factor (default 3)
        competitive_risk: 1-6 industry risk factor (default 3)
        country_risk: 1-6 (default 2 for NZ)
        quant_only: when True, ignore qualitative inputs and use defaults (True default)
        competitive_advantage, scale_scope, operating_efficiency: 1-6 when quant_only=False
        financial_policy, capital_structure, diversification, comparable_ratings: when quant_only=False
        mg_*: Management & Governance when quant_only=False
        liquidity_descriptor: "adequate", "tight", "strong" when quant_only=False
        liquidity_sources_mn, liquidity_uses_mn: for liquidity analysis

    Returns:
        dict with:
            anchor_rating, final_rating, business_risk_score, financial_risk_score,
            computed_ratios, factor_scores, workings (detailed audit trail)
    """
    corporate_cfg = load_yaml(CONFIG_DIR / "corporate_method.yaml")
    industry_cfg = load_yaml(CONFIG_DIR / "industry_risk.yaml")
    liquidity_cfg = load_yaml(CONFIG_DIR / "liquidity.yaml")
    sector_cfg = load_sector_methodology(sector_id)

    inputs = _extract_financial_inputs(financials)
    computed_ratios = _compute_ratios(inputs)

    (cp_result, competitive_position_score, industry_risk_score, cicra_score,
     business_risk_score, financial_risk_score, ffo_label, debt_label,
     core_score) = _compute_business_and_financial_risks(
        corporate_cfg, industry_cfg, sector_cfg, computed_ratios, quant_only,
        competitive_advantage, scale_scope, operating_efficiency, cyclicality,
        competitive_risk, country_risk
    )

    notch_delta, mg_assessment = _compute_modifiers(
        corporate_cfg, quant_only, financial_policy, capital_structure, diversification,
        comparable_ratings, mg_ownership_structure, mg_board_structure, mg_risk_management,
        mg_transparency, mg_management
    )

    rating_scale = corporate_cfg["rating_scale"]
    anchor_by_avg = corporate_cfg["anchor_by_avg"]
    anchor_key = _clamp_score((business_risk_score + financial_risk_score) / 2)
    anchor_rating = anchor_by_avg.get(anchor_key) or anchor_by_avg.get(str(anchor_key), "BBB")
    rating_after_modifiers = _apply_notches(rating_scale, anchor_rating, notch_delta)

    final_rating = _apply_liquidity_cap(
        corporate_cfg, liquidity_cfg, quant_only, liquidity_descriptor, rating_after_modifiers
    )

    workings = _build_workings(
        financials, sector_id, cyclicality, competitive_risk, country_risk,
        quant_only, computed_ratios, competitive_position_score, industry_risk_score,
        cicra_score, business_risk_score, ffo_label, debt_label, core_score,
        financial_risk_score, notch_delta, mg_assessment, liquidity_sources_mn,
        liquidity_uses_mn
    )

    return {
        "anchor_rating": anchor_rating,
        "final_rating": final_rating,
        "business_risk_score": business_risk_score,
        "financial_risk_score": financial_risk_score,
        "computed_ratios": computed_ratios,
        "factor_scores": cp_result.get("factor_scores", []),
        "workings": workings,
    }
