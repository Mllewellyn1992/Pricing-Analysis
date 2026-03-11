import streamlit as st
import pandas as pd
import yaml

from rating_engine import CONFIG_DIR, load_yaml, load_sector_methodology, score_methodology


def parse_required_float(raw: str, label: str) -> float:
    raw = raw.strip()
    if raw == "":
        raise ValueError(f"Missing value for {label}.")
    return float(raw)


def load_inputs_config() -> dict:
    path = CONFIG_DIR / "inputs_config.yaml"
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError("Invalid inputs_config.yaml")
    return cfg


def list_sectors() -> list[tuple[str, str]]:
    sector_dir = CONFIG_DIR / "sector_specific"
    sectors = []
    for path in sorted(sector_dir.glob("*.yaml")):
        cfg = load_yaml(path)
        sectors.append((cfg["id"], cfg["name"]))
    return sectors


def rating_to_index(scale: list[str], rating: str) -> int:
    if rating not in scale:
        return len(scale) - 1
    return scale.index(rating)


def apply_notches(scale: list[str], rating: str, notch_delta: int) -> str:
    idx = rating_to_index(scale, rating)
    new_idx = max(0, min(len(scale) - 1, idx - notch_delta))
    return scale[new_idx]


def categorize_ratio(value: float, bands: list[dict], direction: str) -> str:
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


def label_to_financial_score(label: str) -> int:
    mapping = {
        "Minimal": 1,
        "Modest": 2,
        "Intermediate": 3,
        "Significant": 4,
        "Aggressive": 5,
        "Highly leveraged": 6,
    }
    return mapping.get(label, 6)


def clamp_score(value: float, min_score: int = 1, max_score: int = 6) -> int:
    return max(min_score, min(max_score, int(round(value))))


st.set_page_config(page_title="S&P Rating Tool", layout="wide")
st.title("S&P Rating Tool")

sectors = list_sectors()
if not sectors:
    st.error("No sector configurations found.")
    st.stop()

sector_options = {f"{sid} – {name}": sid for sid, name in sectors}
selected_label = st.selectbox("Select sector", list(sector_options.keys()))
sector_id = sector_options[selected_label]

inputs_cfg = load_inputs_config()

st.markdown("### Inputs")
with st.form("rating_form"):
    inputs_raw = {}
    for section in inputs_cfg.get("sections", []):
        st.markdown(f"#### {section['title']}")
        for field in section.get("fields", []):
            field_id = field["id"]
            field_type = field.get("type", "number")
            if field_type == "select":
                options = field.get("options", [])
                labels = [opt.get("label", opt.get("id", "")) for opt in options]
                ids = [opt.get("id") for opt in options]
                selected_label = st.selectbox(field["label"], labels, index=0, key=field_id)
                inputs_raw[field_id] = ids[labels.index(selected_label)]
            else:
                inputs_raw[field_id] = st.text_input(field["label"], value="", key=field_id)

    submitted = st.form_submit_button("Calculate rating")

if submitted:
    try:
        corporate_cfg = load_yaml(CONFIG_DIR / "corporate_method.yaml")
        industry_cfg = load_yaml(CONFIG_DIR / "industry_risk.yaml")
        liquidity_cfg = load_yaml(CONFIG_DIR / "liquidity.yaml")
        mg_cfg = load_yaml(CONFIG_DIR / "mg_modifier.yaml")
        sector_cfg = load_sector_methodology(sector_id)

        # Parse inputs
        revenue_mn = parse_required_float(inputs_raw["revenue_mn"], "Revenue (Mn)")
        ebit_mn = parse_required_float(inputs_raw["ebit_mn"], "EBIT (Mn)")
        dep_mn = parse_required_float(inputs_raw["depreciation_mn"], "Depreciation (Mn)")
        amort_mn = parse_required_float(inputs_raw["amortization_mn"], "Amortization (Mn)")
        interest_expense_mn = parse_required_float(
            inputs_raw["interest_expense_mn"], "Interest expense (Mn)"
        )
        cash_interest_paid_mn = parse_required_float(
            inputs_raw["cash_interest_paid_mn"], "Cash interest paid (Mn)"
        )
        cash_taxes_paid_mn = parse_required_float(
            inputs_raw["cash_taxes_paid_mn"], "Cash taxes paid (Mn)"
        )
        total_debt_mn = parse_required_float(
            inputs_raw["total_debt_mn"], "Adjusted debt (Mn)"
        )
        cash_mn = parse_required_float(
            inputs_raw["cash_mn"], "Cash and liquid investments (Mn)"
        )
        avg_capital_mn = parse_required_float(
            inputs_raw["avg_capital_mn"], "Average capital (Mn)"
        )
        cfo_mn = parse_required_float(inputs_raw["cfo_mn"], "CFO (Mn)")
        capex_mn = parse_required_float(inputs_raw["capex_mn"], "Capex (Mn)")
        dividends_paid_mn = parse_required_float(
            inputs_raw["dividends_paid_mn"], "Dividends paid (Mn)"
        )
        share_buybacks_mn = parse_required_float(
            inputs_raw["share_buybacks_mn"], "Share buybacks (Mn)"
        )

        cyclicality_score = int(inputs_raw["cyclicality_score"])
        competitive_risk_score = int(inputs_raw["competitive_risk_score"])
        country_risk_score = int(inputs_raw["country_risk_score"])

        # Compute ratios
        ebitda_mn = ebit_mn + dep_mn + amort_mn
        ffo_mn = ebitda_mn - cash_interest_paid_mn - cash_taxes_paid_mn
        ffo_to_debt_pct = (ffo_mn / total_debt_mn) * 100.0 if total_debt_mn else 0.0
        debt_to_ebitda_x = (total_debt_mn / ebitda_mn) if ebitda_mn else 0.0
        ffo_to_cash_interest_x = (
            ffo_mn / cash_interest_paid_mn if cash_interest_paid_mn else 0.0
        )
        ebitda_to_interest_x = (
            ebitda_mn / interest_expense_mn if interest_expense_mn else 0.0
        )
        cfo_to_debt_pct = (cfo_mn / total_debt_mn) * 100.0 if total_debt_mn else 0.0
        focf_mn = cfo_mn - capex_mn
        focf_to_debt_pct = (focf_mn / total_debt_mn) * 100.0 if total_debt_mn else 0.0
        dcf_mn = focf_mn - dividends_paid_mn - share_buybacks_mn
        dcf_to_debt_pct = (dcf_mn / total_debt_mn) * 100.0 if total_debt_mn else 0.0
        ebit_margin_pct = (ebit_mn / revenue_mn) * 100.0 if revenue_mn else 0.0
        ebitda_margin_pct = (ebitda_mn / revenue_mn) * 100.0 if revenue_mn else 0.0
        return_on_capital_pct = (
            (ebit_mn / avg_capital_mn) * 100.0 if avg_capital_mn else 0.0
        )

        # Competitive position score from sector methodology
        cp_metrics = {
            "competitive_advantage_band": inputs_raw["competitive_advantage_band"],
            "scale_scope_diversity_band": inputs_raw["scale_scope_diversity_band"],
            "operating_efficiency_band": inputs_raw["operating_efficiency_band"],
        }
        cp_score = score_methodology(sector_cfg, cp_metrics)["composite_score"]
        competitive_position_score = clamp_score(cp_score)

        # Industry risk score from matrix
        industry_matrix = industry_cfg["matrix"]
        industry_risk_score = industry_matrix[cyclicality_score - 1][
            competitive_risk_score - 1
        ]

        # CICRA
        cicra_matrix = corporate_cfg["cicra_matrix"]
        cicra_score = cicra_matrix[industry_risk_score - 1][country_risk_score - 1]

        # Business risk profile (approximate)
        business_risk_score = clamp_score((cicra_score + competitive_position_score) / 2)

        # Financial risk profile from ratio table
        table_key = "standard"
        if cicra_score == 1:
            table_key = "low"
        elif cicra_score == 2:
            table_key = "medial"
        ratio_table = corporate_cfg["financial_risk_tables"][table_key]

        ffo_label = categorize_ratio(
            ffo_to_debt_pct, ratio_table["FFO_to_debt_pct"]["bands"], "higher_better"
        )
        debt_label = categorize_ratio(
            debt_to_ebitda_x, ratio_table["debt_to_EBITDA_x"]["bands"], "lower_better"
        )
        core_score = max(label_to_financial_score(ffo_label), label_to_financial_score(debt_label))
        financial_risk_score = clamp_score(core_score)

        # Anchor rating
        rating_scale = corporate_cfg["rating_scale"]
        anchor_by_avg = corporate_cfg["anchor_by_avg"]
        anchor_key = str(clamp_score((business_risk_score + financial_risk_score) / 2))
        anchor_rating = anchor_by_avg.get(anchor_key, "BBB")

        # Modifiers
        modifiers = corporate_cfg["modifiers"]
        fp = inputs_raw["financial_policy_assessment"]
        cs = inputs_raw["capital_structure_assessment"]
        div = inputs_raw["diversification_assessment"]
        comp = inputs_raw["comparable_assessment"]

        notch_delta = 0
        notch_delta += modifiers["financial_policy"].get(fp, 0)
        notch_delta += modifiers["capital_structure"].get(cs, 0)
        notch_delta += modifiers["diversification"].get(div, 0)
        notch_delta += modifiers["comparable_ratings"].get(comp, 0)

        # M&G modifier (simple average)
        mg_map = {"positive": 1, "neutral": 2, "negative": 3}
        mg_scores = [
            mg_map[inputs_raw["mg_ownership_structure"]],
            mg_map[inputs_raw["mg_board_structure"]],
            mg_map[inputs_raw["mg_risk_management"]],
            mg_map[inputs_raw["mg_transparency"]],
            mg_map[inputs_raw["mg_management"]],
        ]
        mg_avg = sum(mg_scores) / len(mg_scores)
        if mg_avg <= 1.5:
            mg_assessment = "positive"
            notch_delta += 0
        elif mg_avg <= 2.3:
            mg_assessment = "neutral"
        elif mg_avg <= 2.8:
            mg_assessment = "moderately_negative"
            notch_delta -= 1
        else:
            mg_assessment = "negative"
            notch_delta -= 2

        rating_after_modifiers = apply_notches(rating_scale, anchor_rating, notch_delta)

        # Liquidity caps
        liquidity_desc = inputs_raw["liquidity_descriptor"]
        cap_rating = liquidity_cfg["descriptors"][liquidity_desc].get("cap_rating")
        final_rating = rating_after_modifiers
        if cap_rating:
            cap_idx = rating_to_index(rating_scale, cap_rating)
            final_idx = rating_to_index(rating_scale, rating_after_modifiers)
            if final_idx < cap_idx:
                final_rating = cap_rating

        # Results
        st.markdown("### Results")
        st.write(f"Business risk profile score: **{business_risk_score}**")
        st.write(f"Financial risk profile score: **{financial_risk_score}**")
        st.write(f"Anchor rating: **{anchor_rating}**")
        st.write(f"Final rating: **{final_rating}**")

        st.markdown("### Computed metrics")
        computed_df = pd.DataFrame(
            [
                {"Metric": "EBITDA (Mn)", "Value": ebitda_mn},
                {"Metric": "FFO (Mn)", "Value": ffo_mn},
                {"Metric": "FFO / Debt (%)", "Value": ffo_to_debt_pct},
                {"Metric": "Debt / EBITDA (x)", "Value": debt_to_ebitda_x},
                {"Metric": "FFO / Cash interest (x)", "Value": ffo_to_cash_interest_x},
                {"Metric": "EBITDA / Interest (x)", "Value": ebitda_to_interest_x},
                {"Metric": "CFO / Debt (%)", "Value": cfo_to_debt_pct},
                {"Metric": "FOCF / Debt (%)", "Value": focf_to_debt_pct},
                {"Metric": "DCF / Debt (%)", "Value": dcf_to_debt_pct},
                {"Metric": "EBIT margin (%)", "Value": ebit_margin_pct},
                {"Metric": "EBITDA margin (%)", "Value": ebitda_margin_pct},
                {"Metric": "Return on capital (%)", "Value": return_on_capital_pct},
            ]
        )
        st.dataframe(computed_df, use_container_width=True)

        st.markdown("### Liquidity")
        liquidity_sources_mn = parse_required_float(
            inputs_raw["liquidity_sources_mn"], "Liquidity sources (Mn)"
        )
        liquidity_uses_mn = parse_required_float(
            inputs_raw["liquidity_uses_mn"], "Liquidity uses (Mn)"
        )
        liquidity_ratio = (
            liquidity_sources_mn / liquidity_uses_mn if liquidity_uses_mn else 0.0
        )
        liquidity_surplus = liquidity_sources_mn - liquidity_uses_mn
        st.write(f"Liquidity A/B: **{liquidity_ratio:.2f}**")
        st.write(f"Liquidity A-B (Mn): **{liquidity_surplus:.2f}**")
        st.write(f"Liquidity descriptor: **{liquidity_desc}**")
        st.write(f"M&G assessment: **{mg_assessment}**")
    except Exception as exc:
        st.error(str(exc))
