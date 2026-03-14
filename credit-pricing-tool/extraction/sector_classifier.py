"""
Sector classification for S&P and Moody's rating frameworks.

Provides two approaches:
1. AI-powered classification using Claude API
2. Heuristic keyword-based fallback

Both classify companies into S&P and Moody's sector taxonomies
used for credit rating analysis.
"""

import logging
import json
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# S&P sector taxonomy (commonly used in credit analysis)
SP_SECTORS = {
    "technology_software_and_services",
    "mining",
    "regulated_utilities",
    "retail_and_restaurants",
    "engineering_and_construction",
    "pharmaceuticals",
    "aerospace_and_defense",
    "building_materials",
    "chemicals",
    "consumer_durables",
    "consumer_packaged_goods",
    "environmental_services",
    "capital_goods",
    "health_care_services",
    "telecommunications",
    "media_and_entertainment",
    "midstream_energy",
    "oil_and_gas_exploration_and_production",
    "forest_and_paper_products",
    "homebuilders_and_real_estate_developers",
    "auto_and_commercial_vehicle_manufacturing",
    "business_and_consumer_services",
    "diversified_manufacturing",
    "food_and_beverage",
    "integrated_oil_and_gas",
    "plastics_and_rubber",
    "steel_and_metal_products",
    "supraregional_telecom",
    "wireless_telecom",
    "entertainment",
    "automotive_components",
    "containers_and_packaging",
    "electric_utilities",
    "gas_utilities",
    "diversified_telecommunications",
    "publishing_and_broadcasting",
    "insurance_brokerage",
    "asset_management",
    "specialty_retail",
    "department_stores",
    "apparel",
    "footwear",
    "lodging_and_casinos",
    "restaurants",
    "unregulated_power_and_gas",
    # Additional sectors from frontend/S&P defaults
    "agribusiness_commodity_foods_and_agricultural_cooperatives",
    "asset_managers",
    "auto_suppliers",
    "commodity_chemicals",
    "specialty_chemicals",
    "consumer_staples_and_branded_nondurables",
    "contract_drilling",
    "financial_market_infrastructure",
    "financial_services_finance_companies",
    "health_care_equipment",
    "leisure_and_sports",
    "metals_production_and_processing",
    "oilfield_services_and_equipment",
    "railroad_package_express_and_logistics",
    "refining_and_marketing",
    "technology_hardware_and_semiconductors",
    "transportation_cyclical",
    "transportation_infrastructure",
}

# Moody's sector taxonomy
MOODYS_SECTORS = {
    "software",
    "steel",
    "telecommunications",
    "retail_and_apparel",
    "construction",
    "pharmaceuticals",
    "aerospace_defense",
    "building_materials",
    "chemicals",
    "consumer_durables",
    "consumer_packaged_goods",
    "diversified_manufacturing",
    "environmental_services",
    "food_processing",
    "gaming",
    "homebuilding",
    "integrated_oil_gas",
    "media",
    "metals_mining",
    "oil_gas_e_and_p",
    "paper_and_forest_products",
    "oil_refining",
    "diversified_services",
    "technology",
    "transportation",
    "utilities",
    "utilities_regulated",
    "waste_management",
    "automotive",
    "automotive_parts",
    "beverage",
    "broadcasting",
    "business_services",
    "container",
    "department_stores",
    "electric_utilities",
    "gas_utilities",
    "healthcare_services",
    "machinery",
    "packaging",
    "publishing",
    "railroads",
    "real_estate",
    "restaurants",
    "retail",
    "specialty_retail",
    "telecommunications_services",
    "wireline",
    "wireless",
}

# Keyword to sector mappings for heuristic classification
KEYWORD_MAPPINGS = {
    # Technology
    "software": {"sp": "technology_software_and_services", "moodys": "software"},
    "technology": {"sp": "technology_software_and_services", "moodys": "technology"},
    "hardware": {"sp": "technology_software_and_services", "moodys": "technology"},
    "cloud": {"sp": "technology_software_and_services", "moodys": "software"},
    "saas": {"sp": "technology_software_and_services", "moodys": "software"},

    # Energy and Utilities
    "oil": {"sp": "integrated_oil_and_gas", "moodys": "integrated_oil_gas"},
    "gas": {"sp": "midstream_energy", "moodys": "oil_gas_e_and_p"},
    "energy": {"sp": "midstream_energy", "moodys": "integrated_oil_gas"},
    "utility": {"sp": "regulated_utilities", "moodys": "utilities"},
    "utilities": {"sp": "regulated_utilities", "moodys": "utilities"},
    "electric": {"sp": "regulated_utilities", "moodys": "electric_utilities"},
    "petroleum": {"sp": "oil_and_gas_exploration_and_production", "moodys": "oil_gas_e_and_p"},

    # Healthcare
    "pharmaceutical": {"sp": "pharmaceuticals", "moodys": "pharmaceuticals"},
    "pharma": {"sp": "pharmaceuticals", "moodys": "pharmaceuticals"},
    "biotech": {"sp": "pharmaceuticals", "moodys": "pharmaceuticals"},
    "healthcare": {"sp": "health_care_services", "moodys": "healthcare_services"},
    "medical": {"sp": "health_care_services", "moodys": "healthcare_services"},

    # Materials and Mining
    "mining": {"sp": "mining", "moodys": "metals_mining"},
    "metal": {"sp": "mining", "moodys": "metals_mining"},
    "steel": {"sp": "steel_and_metal_products", "moodys": "steel"},
    "aluminum": {"sp": "mining", "moodys": "metals_mining"},
    "chemical": {"sp": "chemicals", "moodys": "chemicals"},
    "paper": {"sp": "forest_and_paper_products", "moodys": "paper_and_forest_products"},

    # Retail and Consumer
    "retail": {"sp": "retail_and_restaurants", "moodys": "retail"},
    "restaurant": {"sp": "retail_and_restaurants", "moodys": "restaurants"},
    "apparel": {"sp": "retail_and_restaurants", "moodys": "retail_and_apparel"},
    "clothing": {"sp": "retail_and_restaurants", "moodys": "retail_and_apparel"},
    "consumer": {"sp": "consumer_packaged_goods", "moodys": "consumer_packaged_goods"},
    "grocery": {"sp": "retail_and_restaurants", "moodys": "retail"},
    "food": {"sp": "consumer_packaged_goods", "moodys": "food_processing"},
    "beverage": {"sp": "consumer_packaged_goods", "moodys": "beverage"},

    # Telecommunications
    "telecom": {"sp": "telecommunications", "moodys": "telecommunications"},
    "wireless": {"sp": "telecommunications", "moodys": "wireless"},
    "broadband": {"sp": "telecommunications", "moodys": "telecommunications_services"},
    "internet": {"sp": "telecommunications", "moodys": "telecommunications"},

    # Industrials
    "aerospace": {"sp": "aerospace_and_defense", "moodys": "aerospace_defense"},
    "defense": {"sp": "aerospace_and_defense", "moodys": "aerospace_defense"},
    "manufacturing": {"sp": "capital_goods", "moodys": "diversified_manufacturing"},
    "industrial": {"sp": "capital_goods", "moodys": "machinery"},
    "equipment": {"sp": "capital_goods", "moodys": "machinery"},
    "construction": {"sp": "engineering_and_construction", "moodys": "construction"},
    "engineering": {"sp": "engineering_and_construction", "moodys": "construction"},
    "automotive": {"sp": "auto_and_commercial_vehicle_manufacturing", "moodys": "automotive"},
    "auto": {"sp": "auto_and_commercial_vehicle_manufacturing", "moodys": "automotive"},

    # Real Estate and Building
    "real estate": {"sp": "homebuilders_and_real_estate_developers", "moodys": "real_estate"},
    "homebuilder": {"sp": "homebuilders_and_real_estate_developers", "moodys": "homebuilding"},
    "building": {"sp": "building_materials", "moodys": "building_materials"},
    "construction material": {"sp": "building_materials", "moodys": "building_materials"},

    # Media and Entertainment
    "media": {"sp": "media_and_entertainment", "moodys": "media"},
    "entertainment": {"sp": "media_and_entertainment", "moodys": "entertainment"},
    "broadcast": {"sp": "media_and_entertainment", "moodys": "broadcasting"},
    "publishing": {"sp": "media_and_entertainment", "moodys": "publishing"},

    # Business Services
    "business service": {"sp": "business_and_consumer_services", "moodys": "business_services"},
    "consulting": {"sp": "business_and_consumer_services", "moodys": "business_services"},
    "logistics": {"sp": "business_and_consumer_services", "moodys": "business_services"},
}


def _build_sector_prompt(business_description: str) -> str:
    """Build the Claude API prompt for sector classification."""
    sp_sectors_str = ", ".join(sorted(SP_SECTORS))
    moodys_sectors_str = ", ".join(sorted(MOODYS_SECTORS))

    return f"""You are a financial sector classification expert with deep knowledge of S&P and Moody's rating frameworks.

Given the following company business description, classify the company into appropriate sectors for both S&P and Moody's.

BUSINESS DESCRIPTION:
{business_description}

S&P SECTORS (choose one):
{sp_sectors_str}

MOODY'S SECTORS (choose one):
{moodys_sectors_str}

RESPONSE:
Return ONLY a valid JSON object with this exact structure (no other text):
{{
  "sp_sector": "exact_sector_name_from_list",
  "moodys_sector": "exact_sector_name_from_list",
  "confidence": 0.0_to_1.0,
  "reasoning": "Brief explanation of why you chose these sectors"
}}

CONFIDENCE SCORING:
- 0.95+: Clear classification, unambiguous business model
- 0.80-0.94: Strong signal but some diversification
- 0.60-0.79: Reasonable classification with some ambiguity
- 0.40-0.59: Low confidence, diversified/unclear
- Below 0.40: Not confident, return null instead

RULES:
1. Must choose from provided sector lists exactly
2. Use exact sector names from lists
3. Must be valid JSON
4. Confidence must be between 0 and 1
"""


def _validate_sector_result(result: dict, business_description: str) -> Optional[dict]:
    """Validate sectors and confidence from API result."""
    sp = result.get("sp_sector", "").strip()
    moodys = result.get("moodys_sector", "").strip()

    if sp not in SP_SECTORS:
        logger.warning(f"Invalid S&P sector from API: {sp}")
        sp = None
    if moodys not in MOODYS_SECTORS:
        logger.warning(f"Invalid Moody's sector from API: {moodys}")
        moodys = None

    if not sp or not moodys:
        logger.warning("API returned invalid sectors, falling back to heuristic")
        return None

    confidence = float(result.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))

    return {
        "sp_sector": sp,
        "moodys_sector": moodys,
        "confidence": confidence,
        "reasoning": result.get("reasoning", ""),
        "method": "ai",
    }


def classify_sector_with_ai(
    business_description: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classify company sector using Claude API.

    Analyzes business description and returns both S&P and Moody's
    sector classifications with confidence and reasoning.

    Args:
        business_description: Company business description/overview
        api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)

    Returns:
        Dictionary with structure:
        {
            "sp_sector": "sector_name",
            "moodys_sector": "sector_name",
            "confidence": 0.0_to_1.0,
            "reasoning": "explanation of classification",
            "method": "ai"
        }
    """
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic library not installed; falling back to heuristic")
        return classify_sector_heuristic(business_description)

    import os
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; falling back to heuristic")
        return classify_sector_heuristic(business_description)

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_sector_prompt(business_description)

    try:
        logger.debug("Calling Claude API for sector classification")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        json_str = response_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        result = json.loads(json_str.strip())
        validated = _validate_sector_result(result, business_description)
        if validated:
            return validated
        return classify_sector_heuristic(business_description)

    except Exception as e:
        logger.error(f"Sector classification API call failed: {e}")
        return classify_sector_heuristic(business_description)


def classify_sector_heuristic(business_description: str) -> Dict[str, Any]:
    """
    Classify company sector using keyword matching (no AI needed).

    Fallback heuristic method that scans description for industry keywords
    and maps to appropriate sector classifications.

    Args:
        business_description: Company business description

    Returns:
        Dictionary with same structure as classify_sector_with_ai
    """
    desc_lower = business_description.lower()

    # Score each keyword match
    sp_scores = {}
    moodys_scores = {}
    matched_keywords = []

    for keyword, sector_map in KEYWORD_MAPPINGS.items():
        if keyword in desc_lower:
            matched_keywords.append(keyword)
            sp = sector_map.get("sp")
            moodys = sector_map.get("moodys")

            if sp:
                sp_scores[sp] = sp_scores.get(sp, 0) + 1
            if moodys:
                moodys_scores[moodys] = moodys_scores.get(moodys, 0) + 1

    # Select highest scoring sectors
    sp_sector = None
    moodys_sector = None
    confidence = 0.5

    if sp_scores:
        sp_sector = max(sp_scores, key=sp_scores.get)
        if moodys_scores:
            moodys_sector = max(moodys_scores, key=moodys_scores.get)

            # Confidence based on score distribution
            max_score = max(sp_scores.get(sp_sector, 0), moodys_scores.get(moodys_sector, 0))
            if max_score >= 3:
                confidence = 0.85
            elif max_score == 2:
                confidence = 0.70
            else:
                confidence = 0.55

    # Fallback defaults
    if not sp_sector:
        sp_sector = "capital_goods"
        confidence = 0.30

    if not moodys_sector:
        moodys_sector = "diversified_manufacturing"
        confidence = 0.30

    return {
        "sp_sector": sp_sector,
        "moodys_sector": moodys_sector,
        "confidence": confidence,
        "reasoning": f"Matched keywords: {', '.join(matched_keywords) if matched_keywords else 'generic/default classification'}",
        "method": "heuristic",
    }
