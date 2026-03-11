"""
Generic scoring engine for S&P-style YAML methodologies.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List

import yaml

CONFIG_DIR = Path(__file__).resolve().parent / "configs"


class ConfigError(Exception):
    pass


class MetricError(Exception):
    pass


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ConfigError(f"Invalid YAML structure in {path}")
    return data


def load_sector_methodology(sector_id: str) -> Dict[str, Any]:
    path = CONFIG_DIR / "sector_specific" / f"{sector_id}.yaml"
    return load_yaml(path)


def _score_numeric_grid(
    grid: List[Dict[str, Any]], value: float, direction: str
) -> (float, str):
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
