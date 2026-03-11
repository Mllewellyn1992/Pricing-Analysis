"""
Rating routes - POST /api/rate endpoint
Runs both S&P and Moody's engines and returns blended rating
"""

from typing import Dict, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from engines.sp_engine import rate_company_sp
from engines.sp_defaults import get_defaults as get_sp_defaults
from engines.moodys_wrapper import rate_company_moodys, moody_to_sp_rating

router = APIRouter()


class RatingRequest(BaseModel):
    """Request model for /api/rate endpoint."""
    financials: Dict[str, Any] = Field(..., description="Financial metrics dict")
    sector_id: Optional[str] = Field(
        default="technology_software_and_services",
        description="S&P sector ID"
    )
    business_description: Optional[str] = Field(
        default=None,
        description="Optional business description"
    )


class RatingResponse(BaseModel):
    """Response model for /api/rate endpoint."""
    sp_rating: str
    moodys_rating: str
    moodys_sp_equivalent: Optional[str]
    blended_rating: str
    computed_metrics: Dict[str, Any]
    sp_details: Dict[str, Any]
    moodys_details: Dict[str, Any]


# Sector mapping: S&P sector_id -> Moody's methodology_id
SP_TO_MOODYS_METHODOLOGY = {
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
    "capital_goods": "consumer_durables",
    "consumer_staples_and_branded_nondurables": "consumer_packaged_goods",
    "consumer_packaged_goods": "consumer_packaged_goods",
    "food_and_beverage": "consumer_packaged_goods",
    "diversified_manufacturing": "consumer_durables",
    "business_and_consumer_services": "business_consumer_service",
    "media_and_entertainment": "media",
    "oil_and_gas_exploration_and_production": "independent_exploration_production",
    "integrated_oil_and_gas": "integrated_oil_and_gas",
    "midstream_energy": "integrated_oil_and_gas",
    "steel_and_metal_products": "steel",
    "forest_and_paper_products": "consumer_packaged_goods",
    "homebuilders_and_real_estate_developers": "homebuilding_property_development",
    "auto_and_commercial_vehicle_manufacturing": "automobile_manufacturers",
    "automotive_components": "automotive_suppliers",
    "telecommunications": "telecommunications_service_providers",
    "environmental_services": "environmental_services_waste_management",
    "health_care_services": "consumer_durables",
    "plastics_and_rubber": "chemicals",
}


# Sector aliases: maps common/friendly sector names to the canonical S&P config filenames
SP_SECTOR_ALIASES = {
    "chemicals": "commodity_chemicals",
    "specialty_chemicals": "specialty_chemicals",
    "consumer_packaged_goods": "consumer_staples_and_branded_nondurables",
    "food_and_beverage": "agribusiness_commodity_foods_and_agricultural_cooperatives",
    "food_processing": "agribusiness_commodity_foods_and_agricultural_cooperatives",
    "media": "media_and_entertainment",
    "steel": "metals_production_and_processing",
    "steel_and_metal_products": "metals_production_and_processing",
    "plastics_and_rubber": "commodity_chemicals",
    "diversified_manufacturing": "capital_goods",
    "integrated_oil_and_gas": "oil_and_gas_exploration_and_production",
    "forest_and_paper_products": "forest_and_paper_products",
    "automotive_components": "auto_suppliers",
    "auto_and_commercial_vehicle_manufacturing": "auto_and_commercial_vehicle_manufacturing",
}


def resolve_sp_sector(sector_id: str) -> str:
    """
    Resolve a sector_id to its canonical S&P config filename.
    Checks aliases first, then returns the original if it already matches a config.
    """
    return SP_SECTOR_ALIASES.get(sector_id, sector_id)


def get_moodys_methodology(sector_id: str) -> str:
    """
    Map S&P sector_id to Moody's methodology_id.
    Falls back to 'consumer_durables' if not found.
    """
    return SP_TO_MOODYS_METHODOLOGY.get(sector_id, "consumer_durables")


def rating_to_numeric_position(rating: str) -> int:
    """
    Convert rating string to numeric position for averaging.
    Higher position = worse rating. Used for blending.
    """
    scale = [
        "AAA", "AA+", "AA", "AA-",
        "A+", "A", "A-",
        "BBB+", "BBB", "BBB-",
        "BB+", "BB", "BB-",
        "B+", "B", "B-",
        "CCC+", "CCC", "CCC-", "CC", "C", "D"
    ]
    return scale.index(rating) if rating in scale else len(scale) - 1


def numeric_position_to_rating(position: int) -> str:
    """Convert numeric position back to rating string."""
    scale = [
        "AAA", "AA+", "AA", "AA-",
        "A+", "A", "A-",
        "BBB+", "BBB", "BBB-",
        "BB+", "BB", "BB-",
        "B+", "B", "B-",
        "CCC+", "CCC", "CCC-", "CC", "C", "D"
    ]
    position = max(0, min(len(scale) - 1, int(round(position))))
    return scale[position]


@router.post("/rate", response_model=RatingResponse)
def rate_company(request: RatingRequest) -> RatingResponse:
    """
    Rate a company using both S&P and Moody's engines.

    Returns:
        - sp_rating: S&P final rating
        - moodys_rating: Moody's final rating
        - moodys_sp_equivalent: Moody's rating converted to S&P scale
        - blended_rating: Simple average of both engines
        - computed_metrics: All computed financial metrics
        - sp_details: Full S&P engine output
        - moodys_details: Full Moody's engine output
    """
    try:
        # Resolve sector aliases to canonical S&P config names
        sp_sector_id = resolve_sp_sector(request.sector_id)

        # Get S&P defaults for the sector
        sp_defaults = get_sp_defaults(sp_sector_id)

        # Run S&P engine with country_risk=2 (NZ)
        sp_result = rate_company_sp(
            financials=request.financials,
            sector_id=sp_sector_id,
            cyclicality=sp_defaults["cyclicality"],
            competitive_risk=sp_defaults["competitive_risk"],
            country_risk=2,  # New Zealand
            quant_only=True,
        )

        sp_rating = sp_result.get("final_rating", "BBB")

        # Get Moody's methodology for this sector
        methodology_id = get_moodys_methodology(request.sector_id)

        # Run Moody's engine
        moodys_result = rate_company_moodys(
            financials=request.financials,
            methodology_id=methodology_id,
            quant_only=True,
        )

        moodys_rating = moodys_result.get("moody_rating", "Baa2")
        moodys_sp_equivalent = moodys_result.get("sp_equivalent")

        # Compute blended rating (simple average of numeric positions)
        sp_pos = rating_to_numeric_position(sp_rating)
        moodys_equiv_pos = (
            rating_to_numeric_position(moodys_sp_equivalent)
            if moodys_sp_equivalent
            else sp_pos
        )
        avg_pos = (sp_pos + moodys_equiv_pos) / 2.0
        blended_rating = numeric_position_to_rating(avg_pos)

        # Merge computed metrics
        computed_metrics = {
            "sp_computed_ratios": sp_result.get("computed_ratios", {}),
            "moodys_computed_metrics": moodys_result.get("computed_metrics", {}),
        }

        return RatingResponse(
            sp_rating=sp_rating,
            moodys_rating=moodys_rating,
            moodys_sp_equivalent=moodys_sp_equivalent,
            blended_rating=blended_rating,
            computed_metrics=computed_metrics,
            sp_details=sp_result,
            moodys_details=moodys_result,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Rating engine error: {str(e)}"
        )
