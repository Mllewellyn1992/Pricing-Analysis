import streamlit as st
import pandas as pd
import statistics
from pathlib import Path
import yaml

from rating_engine import score_company, load_methodology, CONFIG_DIR


# ---------- Helpers ----------


def list_methodologies():
    """Return list of (id, name) from YAML files in CONFIG_DIR."""

    methods = []
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        try:
            cfg = load_methodology(path.stem)
            methods.append((cfg["id"], cfg["name"]))
        except Exception as exc:  # pragma: no cover - UI feedback only
            # Skip any broken configs but log in console
            print(f"Error loading {path}: {exc}")
    return methods


def is_numeric_grid(grid):
    """Detect if a grid is numeric (has min/max) vs pure qualitative."""

    return any(("min" in row or "max" in row) for row in grid)


def parse_required_float(raw: str, label: str) -> float:
    raw = raw.strip()
    if raw == "":
        raise ValueError(f"Missing value for {label}.")
    return float(raw)


def load_pricing_matrix(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Pricing matrix file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict) or "tenors" not in cfg:
        raise ValueError("Invalid pricing matrix config")
    return cfg


def load_inputs_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Inputs config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict) or "common" not in cfg:
        raise ValueError("Invalid inputs config")
    return cfg


def moody_to_sp_rating(moody_rating: str | None) -> str | None:
    if not moody_rating:
        return None
    mapping = {
        "Aaa": "AAA",
        "Aa1": "AA+",
        "Aa2": "AA",
        "Aa3": "AA-",
        "Aa": "AA",
        "A1": "A+",
        "A2": "A",
        "A3": "A-",
        "A": "A",
        "Baa1": "BBB+",
        "Baa2": "BBB",
        "Baa3": "BBB-",
        "Baa": "BBB",
        "Ba1": "BB+",
        "Ba2": "BB",
        "Ba3": "BB-",
        "Ba": "BB",
        "B1": "B+",
        "B2": "B",
        "B3": "B-",
        "B": "B",
        "Caa1": "CCC+",
        "Caa2": "CCC",
        "Caa3": "CCC-",
        "Caa": "CCC",
        "Ca": "CCC-",
    }
    return mapping.get(moody_rating)


def get_pricing_range(pricing_cfg: dict, tenor_years: int, sp_rating: str) -> tuple[float, float] | None:
    tenor_key = str(tenor_years)
    tenor_cfg = pricing_cfg.get("tenors", {}).get(tenor_key)
    if not tenor_cfg:
        return None
    rating_cfg = tenor_cfg.get(sp_rating)
    if not rating_cfg:
        return None
    return float(rating_cfg["min_bps"]), float(rating_cfg["max_bps"])


def compute_building_materials_metrics(inputs: dict) -> dict:
    revenue_mn = inputs["revenue_mn"]
    ebit = inputs["ebit"]
    gross_interest = inputs["gross_interest"]
    dep = inputs["depreciation"]
    amort = inputs["amortization"]

    revenue_usd_billion = revenue_mn / 1000.0
    operating_margin_pct = (ebit / revenue_mn) * 100.0 if revenue_mn else 0.0

    margins = []
    for rev, ebit_hist in zip(inputs["revenues_hist"], inputs["ebit_hist"]):
        if rev:
            margins.append((ebit_hist / rev) * 100.0)
    if len(margins) > 0:
        avg_margin = sum(margins) / len(margins)
        if avg_margin:
            operating_margin_volatility_pct = (
                statistics.pstdev(margins) / avg_margin
            ) * 100.0
        else:
            operating_margin_volatility_pct = 0.0
    else:
        operating_margin_volatility_pct = 0.0

    avg_assets = (inputs["assets_y0"] + inputs["assets_y1"]) / 2.0
    ebit_avg_assets_pct = (ebit / avg_assets) * 100.0 if avg_assets else 0.0

    debt_book = (
        inputs["short_term_debt"]
        + inputs["current_portion_lt_debt"]
        + inputs["long_term_debt_net"]
        + inputs["capital_leases"]
    )
    equity_book = (
        inputs["total_equity"]
        + inputs["minority_interest"]
        + inputs["non_current_deferred_taxes"]
    )
    debt_book_cap_pct = (
        (debt_book / (debt_book + equity_book)) * 100.0
        if (debt_book + equity_book)
        else 0.0
    )

    ebitda = ebit + dep + amort
    total_debt = debt_book
    debt_ebitda_x = (total_debt / ebitda) if ebitda else 0.0
    ebit_interest_x = (ebit / gross_interest) if gross_interest else 0.0

    net_debt = total_debt - inputs["cash"] - inputs["cash_like_assets"]
    change_nwc = inputs["nwc_y0"] - inputs["nwc_y1"]
    change_long_term = inputs["lt_operating_assets_y0"] - inputs["lt_operating_assets_y1"]
    ffo = inputs["cfo"] - change_nwc - change_long_term
    rcf = (
        ffo
        - inputs["common_dividends"]
        - inputs["preferred_dividends"]
        - inputs["minority_dividends"]
    )
    rcf_net_debt_pct = (rcf / net_debt) * 100.0 if net_debt else 0.0

    return {
        "metrics": {
            "revenue_usd_billion": revenue_usd_billion,
            "operating_margin_pct": operating_margin_pct,
            "operating_margin_volatility_pct": operating_margin_volatility_pct,
            "ebit_avg_assets_pct": ebit_avg_assets_pct,
            "debt_book_cap_pct": debt_book_cap_pct,
            "debt_ebitda_x": debt_ebitda_x,
            "ebit_interest_x": ebit_interest_x,
            "rcf_net_debt_pct": rcf_net_debt_pct,
        },
        "computed": {
            "revenue_usd_billion": revenue_usd_billion,
            "operating_margin_pct": operating_margin_pct,
            "operating_margin_volatility_pct": operating_margin_volatility_pct,
            "ebit_avg_assets_pct": ebit_avg_assets_pct,
            "debt_book_cap_pct": debt_book_cap_pct,
            "debt_ebitda_x": debt_ebitda_x,
            "ebit_interest_x": ebit_interest_x,
            "total_debt": total_debt,
            "net_debt": net_debt,
            "ffo": ffo,
            "rcf": rcf,
            "rcf_net_debt_pct": rcf_net_debt_pct,
            "ebitda": ebitda,
        },
    }


def compute_business_consumer_service_metrics(inputs: dict) -> dict:
    revenue_mn = inputs["revenue_mn"]
    ebit_mn = inputs["ebit_mn"]
    dep_mn = inputs["depreciation_mn"]
    amort_mn = inputs["amortization_mn"]
    interest_mn = inputs["interest_expense_mn"]
    total_debt_mn = inputs["total_debt_mn"]
    cash_mn = inputs["cash_mn"]
    cash_like_mn = inputs["cash_like_assets_mn"]

    ebitda = ebit_mn + dep_mn + amort_mn
    # EBITA is EBIT before amortization
    ebita = ebit_mn + amort_mn
    ebita_margin_pct = (ebita / revenue_mn) * 100.0 if revenue_mn else 0.0
    ebitda_margin_pct = (ebitda / revenue_mn) * 100.0 if revenue_mn else 0.0
    debt_ebitda_x = (total_debt_mn / ebitda) if ebitda else 0.0
    ebita_interest_x = (ebita / interest_mn) if interest_mn else 0.0

    net_debt = total_debt_mn - cash_mn - cash_like_mn
    change_nwc = inputs["nwc_y0_mn"] - inputs["nwc_y1_mn"]
    change_long_term = (
        inputs["lt_operating_assets_y0_mn"]
        - inputs["lt_operating_assets_y1_mn"]
    )
    ffo = inputs["cfo_mn"] - change_nwc - change_long_term
    rcf = (
        ffo
        - inputs["common_dividends_mn"]
        - inputs["preferred_dividends_mn"]
        - inputs["minority_dividends_mn"]
    )
    rcf_net_debt_pct = (rcf / net_debt) * 100.0 if net_debt else 0.0

    return {
        "metrics": {
            "revenue_usd_billion": revenue_mn / 1000.0,
            "ebita_margin_pct": ebita_margin_pct,
            "debt_ebitda_x": debt_ebitda_x,
            "ebita_interest_x": ebita_interest_x,
            "rcf_net_debt_pct": rcf_net_debt_pct,
            "total_debt": total_debt_mn,
            "ebitda": ebitda,
            "net_debt": net_debt,
            "rcf": rcf,
        },
        "computed": {
            "ebita_margin_pct": ebita_margin_pct,
            "ebitda_margin_pct": ebitda_margin_pct,
            "debt_ebitda_x": debt_ebitda_x,
            "ebita_interest_x": ebita_interest_x,
            "ebita": ebita,
            "ebitda": ebitda,
            "total_debt": total_debt_mn,
            "net_debt": net_debt,
            "ffo": ffo,
            "rcf": rcf,
            "rcf_net_debt_pct": rcf_net_debt_pct,
        },
    }


def compute_consumer_durables_metrics(inputs: dict) -> dict:
    total_sales_mn = inputs["total_sales_mn"]
    ebit_mn = inputs["ebit_mn"]
    dep_mn = inputs["depreciation_mn"]
    amort_mn = inputs["amortization_mn"]
    interest_mn = inputs["interest_expense_mn"]

    total_debt_mn = inputs["total_debt_mn"]
    cash_mn = inputs["cash_mn"]
    cash_like_mn = inputs["cash_like_assets_mn"]

    ebitda = ebit_mn + dep_mn + amort_mn
    ebit_margin_pct = (ebit_mn / total_sales_mn) * 100.0 if total_sales_mn else 0.0
    debt_ebitda_x = (total_debt_mn / ebitda) if ebitda else 0.0
    ebit_interest_x = (ebit_mn / interest_mn) if interest_mn else 0.0

    net_debt = total_debt_mn - cash_mn - cash_like_mn
    change_nwc = inputs["nwc_y0_mn"] - inputs["nwc_y1_mn"]
    change_long_term = (
        inputs["lt_operating_assets_y0_mn"]
        - inputs["lt_operating_assets_y1_mn"]
    )
    ffo = inputs["cfo_mn"] - change_nwc - change_long_term
    rcf = (
        ffo
        - inputs["common_dividends_mn"]
        - inputs["preferred_dividends_mn"]
        - inputs["minority_dividends_mn"]
    )
    rcf_net_debt_pct = (rcf / net_debt) * 100.0 if net_debt else 0.0

    return {
        "metrics": {
            "total_sales_usd_billion": total_sales_mn / 1000.0,
            "ebit_margin_pct": ebit_margin_pct,
            "debt_ebitda_x": debt_ebitda_x,
            "rcf_net_debt_pct": rcf_net_debt_pct,
            "ebit_interest_x": ebit_interest_x,
            "total_debt": total_debt_mn,
            "ebitda": ebitda,
            "net_debt": net_debt,
            "rcf": rcf,
        },
        "computed": {
            "total_sales_usd_billion": total_sales_mn / 1000.0,
            "ebit_margin_pct": ebit_margin_pct,
            "debt_ebitda_x": debt_ebitda_x,
            "ebit_interest_x": ebit_interest_x,
            "total_debt": total_debt_mn,
            "net_debt": net_debt,
            "ffo": ffo,
            "rcf": rcf,
            "rcf_net_debt_pct": rcf_net_debt_pct,
        },
    }


# ---------- Streamlit UI ----------


st.set_page_config(page_title="Indicative Credit Rating Tool", layout="wide")

st.title("Indicative Credit Rating Tool")

# 1. Methodology selection
methods = list_methodologies()
if not methods:
    st.error(f"No YAML configs found in {CONFIG_DIR}.")
    st.stop()

method_options = {f"{m_id} – {name}": m_id for (m_id, name) in methods}
selected_label = st.selectbox("Select methodology", list(method_options.keys()))
methodology_id = method_options[selected_label]

cfg = load_methodology(methodology_id)
st.caption(f"Loaded methodology: **{cfg['name']}**")

# 2. Build input form
result = None
inputs_cfg = None
try:
    inputs_cfg = load_inputs_config(CONFIG_DIR / "inputs_config.yaml")
except Exception:
    inputs_cfg = None

use_inputs_cfg = bool(inputs_cfg and inputs_cfg.get("methodologies", {}).get(methodology_id))

if use_inputs_cfg:
    st.markdown("### Input base financials")
    with st.form("rating_form"):
        inputs_raw = {}

        inputs_cfg = load_inputs_config(CONFIG_DIR / "inputs_config.yaml")
        method_cfg = inputs_cfg.get("methodologies", {}).get(methodology_id, {})
        common_sections = inputs_cfg.get("common", {}).get("sections", [])
        method_sections = method_cfg.get("sections", [])

        # Render common sections
        for section in common_sections:
            st.markdown(f"#### {section['title']}")
            for field in section.get("fields", []):
                key = field["id"]
                inputs_raw[key] = st.text_input(field["label"], value="", key=key)

        base_year_value = inputs_raw.get("base_year", "").strip()
        base_year_int = None
        if base_year_value:
            try:
                base_year_int = int(float(base_year_value))
            except ValueError:
                base_year_int = None
        year_labels = []

        use_quant_only = False
        business_profile_band = None
        financial_policy_band = None

        # Render methodology-specific sections
        for section in method_sections:
            st.markdown(f"#### {section['title']}")
            if section.get("type") == "history_5yr":
                st.session_state["ebit_y0_display"] = inputs_raw.get("ebit", "")
                st.session_state["rev_y0_display"] = inputs_raw.get("revenue_mn", "")
                if base_year_int is None:
                    year_labels = ["Y-4", "Y-3", "Y-2", "Y-1", "Y0"]
                else:
                    year_labels = [
                        str(base_year_int - 4),
                        str(base_year_int - 3),
                        str(base_year_int - 2),
                        str(base_year_int - 1),
                        str(base_year_int),
                    ]
                ebit_hist = []
                revenue_hist = []
                cols = st.columns(5)
                for i, year in enumerate(year_labels):
                    with cols[i]:
                        if year == (str(base_year_int) if base_year_int is not None else "Y0"):
                            ebit_hist.append(inputs_raw.get("ebit", ""))
                            st.text_input(
                                f"{year} EBIT",
                                value=st.session_state.get("ebit_y0_display", ""),
                                key="ebit_y0_display",
                                disabled=True,
                            )
                            revenue_hist.append(inputs_raw.get("revenue_mn", ""))
                            st.text_input(
                                f"{year} Revenue (Mn)",
                                value=st.session_state.get("rev_y0_display", ""),
                                key="rev_y0_display",
                                disabled=True,
                            )
                        else:
                            ebit_hist.append(
                                st.text_input(
                                    f"{year} EBIT", value="", key=f"ebit_{year}"
                                )
                            )
                            revenue_hist.append(
                                st.text_input(
                                    f"{year} Revenue (Mn)", value="", key=f"rev_{year}"
                                )
                            )
                inputs_raw["ebit_hist"] = ebit_hist
                inputs_raw["revenues_hist"] = revenue_hist
                continue

            if section.get("type") == "qualitative":
                use_quant_only = st.checkbox(
                    "Skip qualitative inputs (reweight quantitative to 100%)",
                    value=False,
                )
                if not use_quant_only:
                    for factor in cfg["factors"]:
                        for sf in factor.get("subfactors", []):
                            direction = sf.get("direction", "higher_better")
                            grid = sf.get("grid", [])
                            is_numeric = any(
                                ("min" in row or "max" in row) for row in grid
                            )
                            if direction == "qualitative" or not is_numeric:
                                options = [row["band"] for row in grid]
                                default_idx = (
                                    options.index("Baa") if "Baa" in options else 0
                                )
                                inputs_raw[sf["metric"]] = st.selectbox(
                                    f"{sf['name']}  (`{sf['metric']}`)",
                                    options,
                                    index=default_idx,
                                    key=f"qual_{sf['metric']}",
                                )
                continue

            for field in section.get("fields", []):
                field_id = field["id"]
                if field_id == "base_year":
                    base_year_value = st.text_input(
                        field["label"], value="", key="base_year"
                    )
                    inputs_raw["base_year"] = base_year_value
                    if base_year_value.strip():
                        try:
                            base_year_int = int(float(base_year_value))
                        except ValueError:
                            base_year_int = None
                    else:
                        base_year_int = None
                    continue
                if field.get("type") == "computed":
                    total_debt_value = ""
                    if (
                        inputs_raw.get("short_term_debt", "").strip()
                        and inputs_raw.get("current_portion_lt_debt", "").strip()
                        and inputs_raw.get("long_term_debt_net", "").strip()
                        and inputs_raw.get("capital_leases", "").strip()
                    ):
                        try:
                            total_debt_value = (
                                float(inputs_raw["short_term_debt"])
                                + float(inputs_raw["current_portion_lt_debt"])
                                + float(inputs_raw["long_term_debt_net"])
                                + float(inputs_raw["capital_leases"])
                            )
                        except ValueError:
                            total_debt_value = ""
                    if (
                        inputs_raw.get("short_term_debt_usd_billion", "").strip()
                        and inputs_raw.get("current_portion_lt_debt_usd_billion", "").strip()
                        and inputs_raw.get("long_term_debt_net_usd_billion", "").strip()
                        and inputs_raw.get("capital_leases_usd_billion", "").strip()
                    ):
                        try:
                            total_debt_value = (
                                float(inputs_raw["short_term_debt_usd_billion"])
                                + float(inputs_raw["current_portion_lt_debt_usd_billion"])
                                + float(inputs_raw["long_term_debt_net_usd_billion"])
                                + float(inputs_raw["capital_leases_usd_billion"])
                            )
                        except ValueError:
                            total_debt_value = ""
                    label = (
                        f"{field['label']} ({base_year_int})"
                        if base_year_int is not None
                        else field["label"]
                    )
                    st.text_input(
                        label,
                        value="" if total_debt_value == "" else str(total_debt_value),
                        key=f"computed_{field_id}",
                        disabled=True,
                    )
                    continue

                label = field["label"]
                year_tag = field.get("year")
                if year_tag == "current" and base_year_int is not None:
                    label = f"{label} ({base_year_int})"
                elif year_tag == "prior" and base_year_int is not None:
                    label = f"{label} ({base_year_int - 1})"

                inputs_raw[field_id] = st.text_input(
                    label,
                    value=str(field.get("default", "")),
                    key=field_id,
                )

        submitted = st.form_submit_button("Calculate rating")

    if submitted:
        try:
            if methodology_id == "building_materials":
                inputs = {
                    "revenue_mn": parse_required_float(
                        inputs_raw["revenue_mn"], "Revenue (Mn)"
                    ),
                    "ebit": parse_required_float(inputs_raw["ebit"], "EBIT"),
                    "gross_interest": parse_required_float(
                        inputs_raw["gross_interest"], "Gross interest expense"
                    ),
                    "depreciation": parse_required_float(
                        inputs_raw["depreciation"], "Depreciation"
                    ),
                    "amortization": parse_required_float(
                        inputs_raw["amortization"], "Amortization of intangibles"
                    ),
                    "ebit_hist": [
                        parse_required_float(v, f"{label} EBIT")
                        for v, label in zip(inputs_raw["ebit_hist"], year_labels)
                    ],
                    "revenues_hist": [
                        parse_required_float(v, f"{label} Revenue (Mn)")
                        for v, label in zip(inputs_raw["revenues_hist"], year_labels)
                    ],
                    "assets_y0": parse_required_float(inputs_raw["assets_y0"], "Assets Y0"),
                    "assets_y1": parse_required_float(inputs_raw["assets_y1"], "Assets Y-1"),
                    "short_term_debt": parse_required_float(
                        inputs_raw["short_term_debt"], "Short-term debt"
                    ),
                    "current_portion_lt_debt": parse_required_float(
                        inputs_raw["current_portion_lt_debt"],
                        "Current portion of long-term debt",
                    ),
                    "long_term_debt_net": parse_required_float(
                        inputs_raw["long_term_debt_net"],
                        "Long-term debt, net of current portion",
                    ),
                    "capital_leases": parse_required_float(
                        inputs_raw["capital_leases"], "Liability for capital leases"
                    ),
                    "total_equity": parse_required_float(
                        inputs_raw["total_equity"], "Total equity"
                    ),
                    "minority_interest": parse_required_float(
                        inputs_raw["minority_interest"], "Minority interest"
                    ),
                    "non_current_deferred_taxes": parse_required_float(
                        inputs_raw["non_current_deferred_taxes"],
                        "Non-current deferred income taxes",
                    ),
                    "cash": parse_required_float(
                        inputs_raw["cash"], "Cash and cash equivalents"
                    ),
                    "cash_like_assets": parse_required_float(
                        inputs_raw["cash_like_assets"],
                        "Cash-like current financial assets",
                    ),
                    "cfo": parse_required_float(
                        inputs_raw["cfo"], "Cash flow from operations (CFO)"
                    ),
                    "nwc_y0": parse_required_float(
                        inputs_raw["nwc_y0"], "Net working capital Y0"
                    ),
                    "nwc_y1": parse_required_float(
                        inputs_raw["nwc_y1"], "Net working capital Y-1"
                    ),
                    "lt_operating_assets_y0": parse_required_float(
                        inputs_raw["lt_operating_assets_y0"],
                        "Net long-term operating assets/liabilities Y0",
                    ),
                    "lt_operating_assets_y1": parse_required_float(
                        inputs_raw["lt_operating_assets_y1"],
                        "Net long-term operating assets/liabilities Y-1",
                    ),
                    "common_dividends": parse_required_float(
                        inputs_raw["common_dividends"], "Common dividends"
                    ),
                    "preferred_dividends": parse_required_float(
                        inputs_raw["preferred_dividends"], "Preferred dividends"
                    ),
                    "minority_dividends": parse_required_float(
                        inputs_raw["minority_dividends"], "Minority dividends"
                    ),
                }
                calc = compute_building_materials_metrics(inputs)
                metrics_for_engine = {**calc["metrics"]}
                if not use_quant_only:
                    metrics_for_engine["business_profile_band"] = inputs_raw.get(
                        "business_profile_band"
                    )
                    metrics_for_engine["financial_policy_band"] = inputs_raw.get(
                        "financial_policy_band"
                    )

                st.markdown("### Computed metrics")
                computed_df = pd.DataFrame(
                    [
                        {"Metric": "Revenue (USD bn)", "Value": calc["computed"]["revenue_usd_billion"]},
                        {"Metric": "Operating margin (%)", "Value": calc["computed"]["operating_margin_pct"]},
                        {
                            "Metric": "Operating margin volatility (%)",
                            "Value": calc["computed"]["operating_margin_volatility_pct"],
                        },
                        {"Metric": "EBIT / Avg assets (%)", "Value": calc["computed"]["ebit_avg_assets_pct"]},
                        {"Metric": "Debt / Book cap (%)", "Value": calc["computed"]["debt_book_cap_pct"]},
                        {"Metric": "Debt / EBITDA (x)", "Value": calc["computed"]["debt_ebitda_x"]},
                        {"Metric": "EBIT / Interest (x)", "Value": calc["computed"]["ebit_interest_x"]},
                        {"Metric": "Total debt (gross)", "Value": calc["computed"]["total_debt"]},
                        {"Metric": "Net debt", "Value": calc["computed"]["net_debt"]},
                        {"Metric": "FFO", "Value": calc["computed"]["ffo"]},
                        {"Metric": "RCF", "Value": calc["computed"]["rcf"]},
                        {"Metric": "RCF / Net debt (%)", "Value": calc["computed"]["rcf_net_debt_pct"]},
                    ]
                )
                st.dataframe(computed_df, use_container_width=True)
            elif methodology_id == "business_consumer_service":
                inputs = {
                    "revenue_mn": parse_required_float(
                        inputs_raw["revenue_mn"], "Revenue (Mn)"
                    ),
                    "ebit_mn": parse_required_float(
                        inputs_raw["ebit_mn"], "EBIT (Mn)"
                    ),
                    "depreciation_mn": parse_required_float(
                        inputs_raw["depreciation_mn"],
                        "Depreciation (Mn)",
                    ),
                    "amortization_mn": parse_required_float(
                        inputs_raw["amortization_mn"],
                        "Amortization (Mn)",
                    ),
                    "interest_expense_mn": parse_required_float(
                        inputs_raw["interest_expense_mn"],
                        "Interest expense (Mn)",
                    ),
                    "total_debt_mn": parse_required_float(
                        inputs_raw["short_term_debt_mn"],
                        "Short-term debt (Mn)",
                    )
                    + parse_required_float(
                        inputs_raw["current_portion_lt_debt_mn"],
                        "Current portion of long-term debt (Mn)",
                    )
                    + parse_required_float(
                        inputs_raw["long_term_debt_net_mn"],
                        "Long-term debt, net of current portion (Mn)",
                    )
                    + parse_required_float(
                        inputs_raw["capital_leases_mn"],
                        "Liability for capital leases (Mn)",
                    ),
                    "cash_mn": parse_required_float(
                        inputs_raw["cash_mn"],
                        "Cash and cash equivalents (Mn)",
                    ),
                    "cash_like_assets_mn": parse_required_float(
                        inputs_raw["cash_like_assets_mn"],
                        "Cash-like current financial assets (Mn)",
                    ),
                    "cfo_mn": parse_required_float(
                        inputs_raw["cfo_mn"],
                        "Cash flow from operations (CFO, Mn)",
                    ),
                    "nwc_y0_mn": parse_required_float(
                        inputs_raw["nwc_y0_mn"],
                        "Net working capital (Mn) Y0",
                    ),
                    "nwc_y1_mn": parse_required_float(
                        inputs_raw["nwc_y1_mn"],
                        "Net working capital (Mn) Y-1",
                    ),
                    "lt_operating_assets_y0_mn": parse_required_float(
                        inputs_raw["lt_operating_assets_y0_mn"],
                        "Net long-term operating assets/liabilities (Mn) Y0",
                    ),
                    "lt_operating_assets_y1_mn": parse_required_float(
                        inputs_raw["lt_operating_assets_y1_mn"],
                        "Net long-term operating assets/liabilities (Mn) Y-1",
                    ),
                    "common_dividends_mn": parse_required_float(
                        inputs_raw["common_dividends_mn"],
                        "Common dividends (Mn)",
                    ),
                    "preferred_dividends_mn": parse_required_float(
                        inputs_raw["preferred_dividends_mn"],
                        "Preferred dividends (Mn)",
                    ),
                    "minority_dividends_mn": parse_required_float(
                        inputs_raw["minority_dividends_mn"],
                        "Minority dividends (Mn)",
                    ),
                }
                calc = compute_business_consumer_service_metrics(inputs)
                metrics_for_engine = {**calc["metrics"]}

                if not use_quant_only:
                    metrics_for_engine["demand_characteristics_band"] = inputs_raw.get(
                        "demand_characteristics_band"
                    )
                    metrics_for_engine["competitive_profile_band"] = inputs_raw.get(
                        "competitive_profile_band"
                    )
                    metrics_for_engine["financial_policy_band"] = inputs_raw.get(
                        "financial_policy_band"
                    )

                st.markdown("### Computed metrics")
                computed_df = pd.DataFrame(
                    [
                        {"Metric": "EBITA", "Value": calc["computed"]["ebita"]},
                        {"Metric": "EBITDA", "Value": calc["computed"]["ebitda"]},
                        {"Metric": "EBITA margin (%)", "Value": calc["computed"]["ebita_margin_pct"]},
                        {"Metric": "Debt / EBITDA (x)", "Value": calc["computed"]["debt_ebitda_x"]},
                        {"Metric": "EBITA / Interest (x)", "Value": calc["computed"]["ebita_interest_x"]},
                        {"Metric": "Total debt (gross)", "Value": calc["computed"]["total_debt"]},
                        {"Metric": "Net debt", "Value": calc["computed"]["net_debt"]},
                        {"Metric": "FFO", "Value": calc["computed"]["ffo"]},
                        {"Metric": "RCF", "Value": calc["computed"]["rcf"]},
                        {"Metric": "RCF / Net debt (%)", "Value": calc["computed"]["rcf_net_debt_pct"]},
                    ]
                )
                st.dataframe(computed_df, use_container_width=True)
            elif methodology_id == "consumer_durables":
                inputs = {
                    "total_sales_mn": parse_required_float(
                        inputs_raw["total_sales_mn"], "Total sales (Mn)"
                    ),
                    "ebit_mn": parse_required_float(
                        inputs_raw["ebit_mn"], "EBIT (Mn)"
                    ),
                    "depreciation_mn": parse_required_float(
                        inputs_raw["depreciation_mn"],
                        "Depreciation (Mn)",
                    ),
                    "amortization_mn": parse_required_float(
                        inputs_raw["amortization_mn"],
                        "Amortization (Mn)",
                    ),
                    "interest_expense_mn": parse_required_float(
                        inputs_raw["interest_expense_mn"],
                        "Interest expense (Mn)",
                    ),
                    "total_debt_mn": parse_required_float(
                        inputs_raw["short_term_debt_mn"],
                        "Short-term debt (Mn)",
                    )
                    + parse_required_float(
                        inputs_raw["current_portion_lt_debt_mn"],
                        "Current portion of long-term debt (Mn)",
                    )
                    + parse_required_float(
                        inputs_raw["long_term_debt_net_mn"],
                        "Long-term debt, net of current portion (Mn)",
                    )
                    + parse_required_float(
                        inputs_raw["capital_leases_mn"],
                        "Liability for capital leases (Mn)",
                    ),
                    "cash_mn": parse_required_float(
                        inputs_raw["cash_mn"],
                        "Cash and cash equivalents (Mn)",
                    ),
                    "cash_like_assets_mn": parse_required_float(
                        inputs_raw["cash_like_assets_mn"],
                        "Cash-like current financial assets (Mn)",
                    ),
                    "cfo_mn": parse_required_float(
                        inputs_raw["cfo_mn"],
                        "Cash flow from operations (CFO, Mn)",
                    ),
                    "nwc_y0_mn": parse_required_float(
                        inputs_raw["nwc_y0_mn"],
                        "Net working capital (Mn) Y0",
                    ),
                    "nwc_y1_mn": parse_required_float(
                        inputs_raw["nwc_y1_mn"],
                        "Net working capital (Mn) Y-1",
                    ),
                    "lt_operating_assets_y0_mn": parse_required_float(
                        inputs_raw["lt_operating_assets_y0_mn"],
                        "Net long-term operating assets/liabilities (Mn) Y0",
                    ),
                    "lt_operating_assets_y1_mn": parse_required_float(
                        inputs_raw["lt_operating_assets_y1_mn"],
                        "Net long-term operating assets/liabilities (Mn) Y-1",
                    ),
                    "common_dividends_mn": parse_required_float(
                        inputs_raw["common_dividends_mn"],
                        "Common dividends (Mn)",
                    ),
                    "preferred_dividends_mn": parse_required_float(
                        inputs_raw["preferred_dividends_mn"],
                        "Preferred dividends (Mn)",
                    ),
                    "minority_dividends_mn": parse_required_float(
                        inputs_raw["minority_dividends_mn"],
                        "Minority dividends (Mn)",
                    ),
                }
                calc = compute_consumer_durables_metrics(inputs)
                metrics_for_engine = {**calc["metrics"]}
                if not use_quant_only:
                    metrics_for_engine["competitive_position_band"] = inputs_raw.get(
                        "competitive_position_band"
                    )
                    metrics_for_engine["brand_strength_band"] = inputs_raw.get(
                        "brand_strength_band"
                    )
                    metrics_for_engine["financial_policy_band"] = inputs_raw.get(
                        "financial_policy_band"
                    )

                st.markdown("### Computed metrics")
                computed_df = pd.DataFrame(
                    [
                        {"Metric": "Total sales (USD bn)", "Value": calc["computed"]["total_sales_usd_billion"]},
                        {"Metric": "EBIT margin (%)", "Value": calc["computed"]["ebit_margin_pct"]},
                        {"Metric": "Debt / EBITDA (x)", "Value": calc["computed"]["debt_ebitda_x"]},
                        {"Metric": "EBIT / Interest (x)", "Value": calc["computed"]["ebit_interest_x"]},
                        {"Metric": "Total debt (gross)", "Value": calc["computed"]["total_debt"]},
                        {"Metric": "Net debt", "Value": calc["computed"]["net_debt"]},
                        {"Metric": "FFO", "Value": calc["computed"]["ffo"]},
                        {"Metric": "RCF", "Value": calc["computed"]["rcf"]},
                        {"Metric": "RCF / Net debt (%)", "Value": calc["computed"]["rcf_net_debt_pct"]},
                    ]
                )
                st.dataframe(computed_df, use_container_width=True)
            else:
                metrics_for_engine = {}
                for factor in cfg["factors"]:
                    for sf in factor.get("subfactors", []):
                        metric_code = sf["metric"]
                        direction = sf.get("direction", "higher_better")
                        grid = sf.get("grid", [])
                        is_numeric = any(("min" in row or "max" in row) for row in grid)
                        if direction == "qualitative" or not is_numeric:
                            if use_quant_only:
                                continue
                            val = inputs_raw.get(metric_code)
                            if not val:
                                st.error(f"Missing qualitative value for `{metric_code}`.")
                                st.stop()
                            metrics_for_engine[metric_code] = val
                        else:
                            metrics_for_engine[metric_code] = parse_required_float(
                                inputs_raw.get(metric_code, ""),
                                sf["name"],
                            )
        except ValueError as exc:
            st.error(str(exc))
            st.stop()

        try:
            result = score_company(
                methodology_id,
                metrics_for_engine,
                normalize_quantitative=use_quant_only,
            )
        except Exception as exc:
            st.error(f"Error scoring company: {exc}")
            st.stop()
else:
    st.markdown("### Input metrics")
    with st.form("rating_form"):
        metrics_input = {}

        # Loop factors and subfactors to build inputs
        for factor in cfg["factors"]:
            st.markdown(
                f"#### {factor['name']} "
                f"(_weight {factor['weight_pct']}%_)"
            )

            subfactors = factor.get("subfactors", [])
            if not subfactors:
                st.warning(f"Factor '{factor['name']}' has no subfactors in config.")
                continue

            for sf in subfactors:
                metric_code = sf["metric"]
                label = sf["name"]
                direction = sf.get("direction", "higher_better")
                grid = sf.get("grid", [])
                units = sf.get("units", "").strip()

                # Avoid creating duplicate widgets when the same metric_code appears multiple times
                if metric_code in metrics_input:
                    continue

                # Widget key must be unique per methodology+metric
                key = f"{methodology_id}_{metric_code}"

                # Decide numeric vs qualitative
                numeric = is_numeric_grid(grid) and direction != "qualitative"

                if numeric:
                    # Numeric input
                    cols = st.columns([3, 1])
                    with cols[0]:
                        val_str = st.text_input(
                            f"{label}  (`{metric_code}`)",
                            value="",
                            key=key,
                            help=f"Units: {units}" if units else f"Metric code: {metric_code}",
                        )
                    with cols[1]:
                        st.caption(units or "numeric")

                    metrics_input[metric_code] = {
                        "type": "numeric",
                        "raw": val_str,
                        "sf": sf,
                    }

                else:
                    # Qualitative: choose band from grid
                    options = [row["band"] for row in grid]
                    default_idx = options.index("Baa") if "Baa" in options else 0
                    band = st.selectbox(
                        f"{label}  (`{metric_code}`)",
                        options,
                        index=default_idx,
                        key=key,
                        help="Select the appropriate qualitative band",
                    )
                    metrics_input[metric_code] = {
                        "type": "qualitative",
                        "value": band,
                        "sf": sf,
                    }

        submitted = st.form_submit_button("Calculate rating")

    # 3. Run the engine
    if submitted:
        # Convert user input to the dict expected by score_company
        metrics_for_engine = {}

        # Parse numeric fields
        for metric_code, meta in metrics_input.items():
            if meta["type"] == "qualitative":
                metrics_for_engine[metric_code] = meta["value"]
            else:
                raw = meta["raw"].strip()
                if raw == "":
                    st.error(f"Missing value for `{metric_code}` ({meta['sf']['name']}).")
                    st.stop()
                try:
                    val = float(raw)
                except ValueError:
                    st.error(
                        f"Invalid number for `{metric_code}` "
                        f"({meta['sf']['name']}): '{raw}'"
                    )
                    st.stop()
                metrics_for_engine[metric_code] = val

        # Call the engine
        try:
            result = score_company(methodology_id, metrics_for_engine)
        except Exception as exc:
            st.error(f"Error scoring company: {exc}")
            st.stop()

if result is not None:
    # 4. Display results
    st.markdown("---")
    st.markdown("### Results")

    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Anchor rating", value=result["anchor_rating"] or "N/A")
    with col2:
        st.metric(
            label="Composite score",
            value=f"{result['composite_score']:.2f}",
        )

    # Factor scores table
    st.markdown("#### Factor scores")
    factor_df_raw = pd.DataFrame(result["factor_scores"])
    weight_col = (
        "weight_pct_adjusted" if "weight_pct_adjusted" in factor_df_raw.columns
        else "factor_weight_pct"
    )
    factor_df = factor_df_raw.rename(
        columns={
            "factor_name": "Factor",
            "score": "Score",
            weight_col: "Weight (%)",
        }
    )[
        [
            "Factor",
            "Score",
            "Weight (%)",
        ]
    ]
    st.dataframe(factor_df, use_container_width=True)

    # Sub-factor detail
    st.markdown("#### Sub-factor details")
    sf_df = pd.DataFrame(result["subfactor_scores"]).rename(
        columns={
            "factor_name": "Factor",
            "subfactor_name": "Sub-factor",
            "metric_code": "Metric code",
            "input_value": "Input",
            "score": "Score",
            "band": "Band",
            "subfactor_weight_pct": "Weight (%)",
        }
    )
    if "Direction" not in sf_df.columns:
        sf_df["Direction"] = [
            row.get("direction", "") for row in result["subfactor_scores"]
        ]

    sf_df = sf_df[
        [
            "Factor",
            "Sub-factor",
            "Metric code",
            "Direction",
            "Input",
            "Band",
            "Score",
            "Weight (%)",
        ]
    ]
    st.dataframe(sf_df, use_container_width=True)

    st.caption(
        "Tip: copy these tables into Excel/Word for credit papers or pitch decks."
    )

    # Pricing output
    pricing_cfg = None
    try:
        pricing_cfg = load_pricing_matrix(CONFIG_DIR / "pricing_matrix.yaml")
    except Exception as exc:  # pragma: no cover - UI feedback only
        st.error(f"Pricing matrix error: {exc}")

    if pricing_cfg:
        st.markdown("### Indicative pricing")
        sp_rating = moody_to_sp_rating(result.get("anchor_rating"))
        tenor_val = None
        try:
            tenor_val = int(float(st.session_state.get("tenor_years", "")))
        except Exception:
            tenor_val = None

        if not sp_rating:
            st.warning("Pricing not available: rating could not be mapped.")
        elif tenor_val is None:
            st.warning("Pricing not available: enter a valid tenor in years.")
        else:
            pricing_range = get_pricing_range(pricing_cfg, tenor_val, sp_rating)
            if not pricing_range:
                st.warning("Pricing not available for that tenor/rating.")
            else:
                min_bps, max_bps = pricing_range
                st.write(
                    f"Indicative pricing range: {min_bps:.0f} - {max_bps:.0f} bps"
                )
                customer_bps = None
                try:
                    customer_bps = float(
                        st.session_state.get("customer_pricing_bps", "")
                    )
                except Exception:
                    customer_bps = None
                if customer_bps is not None:
                    if customer_bps < min_bps:
                        delta = customer_bps - min_bps
                    elif customer_bps > max_bps:
                        delta = customer_bps - max_bps
                    else:
                        delta = 0.0
                    st.write(f"Customer pricing: {customer_bps:.0f} bps")
                    st.write(f"Delta vs range: {delta:.0f} bps")

