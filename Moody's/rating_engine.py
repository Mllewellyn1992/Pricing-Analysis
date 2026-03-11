"""
Generic engine to compute an indicative Moody's-style rating
from a YAML methodology config and a dict of input metrics.

Folder structure:
    rating_tool/
      rating_engine.py
      configs/
        building_materials.yaml
        <other_methodologies>.yaml
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Default folder for YAML configs (relative to this file)
CONFIG_DIR = Path(__file__).resolve().parent / "configs"

# Default score → rating mapping when not provided in YAML.
DEFAULT_SCORE_TO_RATING = [
    {"min_score": 1.0, "max_score": 1.5, "rating": "Aaa"},
    {"min_score": 1.5, "max_score": 2.5, "rating": "Aa1"},
    {"min_score": 2.5, "max_score": 3.5, "rating": "Aa2"},
    {"min_score": 3.5, "max_score": 4.5, "rating": "Aa3"},
    {"min_score": 4.5, "max_score": 5.5, "rating": "A1"},
    {"min_score": 5.5, "max_score": 6.5, "rating": "A2"},
    {"min_score": 6.5, "max_score": 7.5, "rating": "A3"},
    {"min_score": 7.5, "max_score": 8.5, "rating": "Baa1"},
    {"min_score": 8.5, "max_score": 9.5, "rating": "Baa2"},
    {"min_score": 9.5, "max_score": 10.5, "rating": "Baa3"},
    {"min_score": 10.5, "max_score": 11.5, "rating": "Ba1"},
    {"min_score": 11.5, "max_score": 12.5, "rating": "Ba2"},
    {"min_score": 12.5, "max_score": 13.5, "rating": "Ba3"},
    {"min_score": 13.5, "max_score": 14.5, "rating": "B1"},
    {"min_score": 14.5, "max_score": 15.5, "rating": "B2"},
    {"min_score": 15.5, "max_score": 16.5, "rating": "B3"},
    {"min_score": 16.5, "max_score": 17.5, "rating": "Caa1"},
    {"min_score": 17.5, "max_score": 18.5, "rating": "Caa2"},
    {"min_score": 18.5, "max_score": 19.5, "rating": "Caa3"},
    {"min_score": 19.5, "max_score": 99.9, "rating": "Ca"},
]


class ConfigError(Exception):
    """Raised when the methodology config is invalid or missing."""


class MetricError(Exception):
    """Raised when required metric values are missing or invalid."""


def load_methodology(
    methodology_id: str,
    config_dir: Path = CONFIG_DIR,
) -> Dict[str, Any]:
    """
    Load a methodology YAML config by id.
    Expects a file named <methodology_id>.yaml in config_dir.
    """

    path = config_dir / f"{methodology_id}.yaml"
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        raise ConfigError(f"Invalid YAML structure in {path}")

    # Basic sanity checks
    for key in ("id", "name", "factors"):
        if key not in cfg:
            raise ConfigError(f"Missing '{key}' in {path}")

    if "score_to_rating" not in cfg:
        cfg["score_to_rating"] = DEFAULT_SCORE_TO_RATING

    if cfg["id"] != methodology_id:
        # Not fatal, but worth warning
        print(
            f"WARNING: methodology id in YAML ({cfg['id']}) "
            f"does not match file id ({methodology_id})"
        )

    return cfg


def _score_numeric_grid(
    grid: List[Dict[str, Any]],
    value: float,
    direction: str,
) -> (float, str):
    """
    Find score and band for a numeric metric within a subfactor grid.
    grid: list of dicts with at least {band, score, min?, max?}
    direction: "higher_better" or "lower_better" (for now this only matters
               for how you define your min/max in YAML; logic is generic).
    """

    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise MetricError("Numeric metric value is None or NaN")

    # Assume YAML grids are ordered from best to worst band.
    for row in grid:
        band = row.get("band")
        score = row.get("score")
        lo = row.get("min")
        hi = row.get("max")

        # Treat None as open-ended side
        if lo is None and hi is None:
            # degenerate, but just return
            return float(score), str(band)

        if lo is None:
            if value < hi:
                return float(score), str(band)
        elif hi is None:
            if value >= lo:
                return float(score), str(band)
        else:
            # inclusive lower, exclusive upper
            if (value >= lo) and (value < hi):
                return float(score), str(band)

    # If nothing matched, fall back to worst row (last)
    worst = grid[-1]
    return float(worst["score"]), str(worst.get("band", "UNKNOWN"))


def _score_qualitative_grid(
    grid: List[Dict[str, Any]],
    raw_value: Any,
) -> (float, str):
    """
    For qualitative subfactors, we expect 'raw_value' to be a band string
    like 'Aaa', 'Baa' etc. We map it directly to the corresponding score.
    """

    if raw_value is None:
        raise MetricError("Qualitative metric value is None")

    val_str = str(raw_value).strip()
    for row in grid:
        band = str(row.get("band")).strip()
        score = row.get("score")

        if val_str.lower() == band.lower():
            return float(score), band

    raise MetricError(f"Qualitative value '{val_str}' not found in grid")


def _score_subfactor(
    methodology_cfg: Dict[str, Any],
    factor_cfg: Dict[str, Any],
    subfactor_cfg: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute the score for a single subfactor given metrics.
    """

    metric_code = subfactor_cfg["metric"]
    direction = subfactor_cfg.get("direction", "higher_better")
    grid = subfactor_cfg.get("grid", [])
    value = metrics.get(metric_code)

    if not grid:
        raise ConfigError(
            f"Subfactor '{subfactor_cfg['id']}' has no grid defined"
        )

    # Check special cases (override grid)
    special_cases = subfactor_cfg.get("special_cases", [])
    for case in special_cases:
        when = case.get("when", {})
        match = True
        for key, expected in when.items():
            if key == "total_debt":
                match = match and metrics.get("total_debt") == expected
            elif key == "total_debt_gt_0":
                match = match and (metrics.get("total_debt", 0) > 0) == bool(expected)
            elif key == "ebitda_lt_0":
                match = match and (metrics.get("ebitda", 0) < 0) == bool(expected)
            elif key == "ebitda_lte_0":
                match = match and (metrics.get("ebitda", 0) <= 0) == bool(expected)
            elif key == "ebit_lt_0":
                match = match and (metrics.get("ebit", 0) < 0) == bool(expected)
            elif key == "ebit_lte_0":
                match = match and (metrics.get("ebit", 0) <= 0) == bool(expected)
            elif key == "debt_ebitda_lt_0":
                match = (
                    match
                    and (metrics.get("debt_ebitda_x", 0) < 0) == bool(expected)
                )
            elif key == "debt_lt_0":
                match = match and (metrics.get("total_debt", 0) < 0) == bool(expected)
            elif key == "net_debt_lt_0":
                match = match and (metrics.get("net_debt", 0) < 0) == bool(expected)
            elif key == "rcf_gt_0":
                match = match and (metrics.get("rcf", 0) > 0) == bool(expected)
            elif key == "rcf_lt_0":
                match = match and (metrics.get("rcf", 0) < 0) == bool(expected)
            elif key == "rcf_lte_0":
                match = match and (metrics.get("rcf", 0) <= 0) == bool(expected)
            elif key == "debt_book_cap_lt_0":
                match = (
                    match
                    and (metrics.get("debt_book_cap_pct", 0) < 0)
                    == bool(expected)
                )
            elif key == "interest_expense_lte_0":
                match = match and (metrics.get("interest_expense", 0) <= 0) == bool(expected)
            elif key == "interest_expense_gt_0":
                match = match and (metrics.get("interest_expense", 0) > 0) == bool(expected)
            else:
                match = False
            if not match:
                break

        if match:
            if "numeric_score" in case:
                score = float(case["numeric_score"])
                band = str(case.get("band", "SPECIAL"))
            else:
                score = float(case["score"])
                band = str(case["band"])
            return {
                "methodology_id": methodology_cfg["id"],
                "factor_id": factor_cfg["id"],
                "factor_name": factor_cfg["name"],
                "factor_weight_pct": float(factor_cfg["weight_pct"]),
                "subfactor_id": subfactor_cfg["id"],
                "subfactor_name": subfactor_cfg["name"],
                "subfactor_weight_pct": float(subfactor_cfg["weight_pct"]),
                "metric_code": metric_code,
                "direction": direction,
                "input_value": value,
                "score": score,
                "band": band,
            }

    # Decide numeric vs qualitative by presence of min/max in rows
    is_numeric = any(("min" in row or "max" in row) for row in grid)

    if direction == "qualitative" or not is_numeric:
        score, band = _score_qualitative_grid(grid, value)
    else:
        if value is None:
            raise MetricError(
                f"Missing numeric metric '{metric_code}' "
                f"for subfactor '{subfactor_cfg['id']}'"
            )

        score, band = _score_numeric_grid(grid, float(value), direction)

    return {
        "methodology_id": methodology_cfg["id"],
        "factor_id": factor_cfg["id"],
        "factor_name": factor_cfg["name"],
        "factor_weight_pct": float(factor_cfg["weight_pct"]),
        "subfactor_id": subfactor_cfg["id"],
        "subfactor_name": subfactor_cfg["name"],
        "subfactor_weight_pct": float(subfactor_cfg["weight_pct"]),
        "metric_code": metric_code,
        "direction": direction,
        "input_value": value,
        "score": score,
        "band": band,
    }


def score_company(
    methodology_id: str,
    metrics: Dict[str, Any],
    config_dir: Path = CONFIG_DIR,
    normalize_quantitative: bool = False,
    skip_metrics: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """
    Main entry point.
    methodology_id: e.g. "building_materials"
    metrics: dict of metric_code -> value (numbers or band strings)
    Returns dict with:
      - methodology_id
      - methodology_name
      - composite_score
      - anchor_rating
      - factor_scores: list of dicts
      - subfactor_scores: list of dicts
    """

    cfg = load_methodology(methodology_id, config_dir=config_dir)
    factors_cfg = cfg["factors"]
    score_to_rating = cfg["score_to_rating"]

    subfactor_scores: List[Dict[str, Any]] = []
    factor_scores: List[Dict[str, Any]] = []

    # 1) Score each subfactor
    skip_metrics = skip_metrics or set()
    for factor_cfg in factors_cfg:
        factor_id = factor_cfg["id"]
        factor_name = factor_cfg["name"]
        factor_weight = float(factor_cfg["weight_pct"])
        sub_cfgs = factor_cfg.get("subfactors", [])

        if not sub_cfgs:
            raise ConfigError(f"Factor '{factor_id}' has no subfactors")

        if normalize_quantitative:
            is_qualitative_factor = all(
                sf.get("direction") == "qualitative"
                or not any(("min" in row or "max" in row) for row in sf.get("grid", []))
                for sf in sub_cfgs
            )
            if is_qualitative_factor:
                # Skip qualitative-only factors and reweight remaining factors to 100%
                continue

        sf_weight_total = 0.0
        sf_weighted_score_sum = 0.0

        for sf_cfg in sub_cfgs:
            if sf_cfg.get("metric") in skip_metrics:
                continue
            sf_result = _score_subfactor(cfg, factor_cfg, sf_cfg, metrics)
            subfactor_scores.append(sf_result)

            w = float(sf_result["subfactor_weight_pct"])
            sf_weight_total += w
            sf_weighted_score_sum += sf_result["score"] * w

        if sf_weight_total <= 0:
            raise ConfigError(
                f"Subfactor weights in factor '{factor_id}' sum to zero"
            )

        factor_score = sf_weighted_score_sum / sf_weight_total
        factor_scores.append(
            {
                "factor_id": factor_id,
                "factor_name": factor_name,
                "factor_weight_pct": factor_weight,
                "score": factor_score,
            }
        )

    # 2) Composite score (weighted by factor weight_pct)
    total_factor_weight = sum(f["factor_weight_pct"] for f in factor_scores)
    if total_factor_weight <= 0:
        raise ConfigError("Total factor weight <= 0; check config")

    if normalize_quantitative:
        for f in factor_scores:
            f["weight_pct_adjusted"] = (
                f["factor_weight_pct"] / total_factor_weight * 100.0
            )

    composite_score = (
        sum(f["score"] * f["factor_weight_pct"] for f in factor_scores)
        / total_factor_weight
    )

    # 3) Map composite score to rating
    anchor_rating: Optional[str] = None
    for row in score_to_rating:
        min_s = float(row["min_score"])
        max_s = float(row["max_score"])
        if composite_score >= min_s and composite_score < max_s:
            anchor_rating = str(row["rating"])
            break

    result = {
        "methodology_id": cfg["id"],
        "methodology_name": cfg["name"],
        "composite_score": composite_score,
        "anchor_rating": anchor_rating,
        "factor_scores": factor_scores,
        "subfactor_scores": subfactor_scores,
    }
    return result


# ---------------------------------------------------------------------
# Basic CLI / smoke test
# ---------------------------------------------------------------------
if __name__ == "__main__":
    """
    Example usage for building_materials.yaml
    Adjust the metric values to something sensible and run:
        python rating_engine.py
    from inside the rating_tool folder.
    """

    example_metrics = {
        # Scale
        "revenue_usd_billion": 3.5,
        # Profitability & efficiency
        "operating_margin_pct": 15.0,
        "operating_margin_volatility_pct": 8.0,
        "ebit_avg_assets_pct": 9.0,
        # Leverage & coverage
        "debt_book_cap_pct": 45.0,
        "debt_ebitda_x": 3.0,
        "ebit_interest_x": 5.0,
        "rcf_net_debt_pct": 25.0,
        # Qualitative
        "business_profile_band": "Baa",
        "financial_policy_band": "Baa",
    }

    res = score_company("building_materials", example_metrics)

    print("Methodology:", res["methodology_name"])
    print("Composite score:", round(res["composite_score"], 2))
    print("Anchor rating:", res["anchor_rating"])
    print("\nFactor scores:")
    for f in res["factor_scores"]:
        print(
            "  - {name}: score={score:.2f}, weight={w:.1f}%".format(
                name=f["factor_name"],
                score=f["score"],
                w=f["factor_weight_pct"],
            )
        )

