"""
S&P Industry defaults lookup.
Provides default cyclicality and competitive_risk scores by sector.
Used in quant_only mode when qualitative inputs are unavailable.

Keys match the YAML config filenames in configs/sp/sector_specific/*.yaml
"""

SP_INDUSTRY_DEFAULTS = {
    # Tech (low cyclicality)
    "technology_software_and_services": {"cyclicality": 2, "competitive_risk": 2},
    "technology_hardware_and_semiconductors": {"cyclicality": 3, "competitive_risk": 3},

    # Utilities (very low cyclicality)
    "regulated_utilities": {"cyclicality": 1, "competitive_risk": 2},
    "unregulated_power_and_gas": {"cyclicality": 3, "competitive_risk": 3},

    # Mining & Metals (high cyclicality)
    "mining": {"cyclicality": 5, "competitive_risk": 4},
    "metals_production_and_processing": {"cyclicality": 5, "competitive_risk": 4},

    # Chemicals
    "commodity_chemicals": {"cyclicality": 4, "competitive_risk": 4},
    "specialty_chemicals": {"cyclicality": 3, "competitive_risk": 3},

    # Oil & Gas (high cyclicality)
    "oil_and_gas_exploration_and_production": {"cyclicality": 5, "competitive_risk": 3},
    "refining_and_marketing": {"cyclicality": 4, "competitive_risk": 3},
    "midstream_energy": {"cyclicality": 3, "competitive_risk": 3},
    "contract_drilling": {"cyclicality": 5, "competitive_risk": 4},
    "oilfield_services_and_equipment": {"cyclicality": 5, "competitive_risk": 4},

    # Healthcare (low cyclicality)
    "pharmaceuticals": {"cyclicality": 2, "competitive_risk": 2},
    "health_care_equipment": {"cyclicality": 2, "competitive_risk": 3},
    "health_care_services": {"cyclicality": 2, "competitive_risk": 3},

    # Industrial
    "aerospace_and_defense": {"cyclicality": 3, "competitive_risk": 2},
    "capital_goods": {"cyclicality": 4, "competitive_risk": 3},
    "engineering_and_construction": {"cyclicality": 5, "competitive_risk": 4},
    "building_materials": {"cyclicality": 4, "competitive_risk": 4},
    "environmental_services": {"cyclicality": 2, "competitive_risk": 2},

    # Consumer
    "retail_and_restaurants": {"cyclicality": 3, "competitive_risk": 4},
    "consumer_durables": {"cyclicality": 4, "competitive_risk": 4},
    "consumer_staples_and_branded_nondurables": {"cyclicality": 1, "competitive_risk": 3},
    "containers_and_packaging": {"cyclicality": 3, "competitive_risk": 3},

    # Media & Telecom
    "media_and_entertainment": {"cyclicality": 3, "competitive_risk": 3},
    "telecommunications": {"cyclicality": 2, "competitive_risk": 3},

    # Transportation
    "transportation_cyclical": {"cyclicality": 4, "competitive_risk": 3},
    "transportation_infrastructure": {"cyclicality": 2, "competitive_risk": 2},
    "railroad_package_express_and_logistics": {"cyclicality": 3, "competitive_risk": 2},

    # Forestry & Paper
    "forest_and_paper_products": {"cyclicality": 4, "competitive_risk": 4},

    # Real Estate
    "homebuilders_and_real_estate_developers": {"cyclicality": 4, "competitive_risk": 3},

    # Leisure
    "leisure_and_sports": {"cyclicality": 3, "competitive_risk": 3},

    # Services
    "business_and_consumer_services": {"cyclicality": 2, "competitive_risk": 3},

    # Auto
    "auto_and_commercial_vehicle_manufacturing": {"cyclicality": 4, "competitive_risk": 3},
    "auto_suppliers": {"cyclicality": 4, "competitive_risk": 4},

    # Agriculture
    "agribusiness_commodity_foods_and_agricultural_cooperatives": {"cyclicality": 2, "competitive_risk": 3},

    # Financial
    "asset_managers": {"cyclicality": 3, "competitive_risk": 3},
    "financial_market_infrastructure": {"cyclicality": 2, "competitive_risk": 2},
    "financial_services_finance_companies": {"cyclicality": 3, "competitive_risk": 3},
}


def get_defaults(sector_id: str) -> dict:
    """
    Get industry defaults for a given sector.
    Returns {"cyclicality": int, "competitive_risk": int}.
    Falls back to neutral (3, 3) if sector not found.
    """
    return SP_INDUSTRY_DEFAULTS.get(
        sector_id,
        {"cyclicality": 3, "competitive_risk": 3}
    )
