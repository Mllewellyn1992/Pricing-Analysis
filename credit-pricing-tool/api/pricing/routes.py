"""
Pricing routes
- POST /api/pricing/lookup: Spread lookup from pricing matrix
- POST /api/pricing/full-analysis: Complete pricing analysis including ratings
"""

from typing import Dict, Optional, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.pricing.engine import (
    load_pricing_matrix,
    lookup_spread,
    compute_expected_rate_range,
    get_base_rate,
)
from api.rate.routes import rate_company, RatingRequest, RatingResponse

router = APIRouter()


class SpreadLookupRequest(BaseModel):
    """Request model for /api/pricing/lookup endpoint."""
    rating: str = Field(..., description="S&P rating (e.g., 'BBB', 'A+')")
    tenor: int = Field(..., ge=1, le=5, description="Tenor in years (1-5)")
    facility_type: Optional[str] = Field(
        default="corporate",
        description="'corporate' or 'working_capital' (for future facility type filtering)"
    )


class SpreadLookupResponse(BaseModel):
    """Response model for /api/pricing/lookup endpoint."""
    rating: str
    tenor: int
    min_spread_bps: float
    max_spread_bps: float
    mid_spread_bps: float


class FullAnalysisRequest(BaseModel):
    """Request model for /api/pricing/full-analysis endpoint."""
    financials: Dict[str, Any] = Field(..., description="Financial metrics dict")
    sector_id: Optional[str] = Field(
        default="technology_software_and_services",
        description="S&P sector ID"
    )
    actual_rate_pct: float = Field(..., description="Actual rate offered (%)")
    facility_tenor: int = Field(..., ge=1, le=5, description="Facility tenor (years)")
    facility_type: str = Field(
        default="corporate",
        description="'corporate' or 'working_capital'"
    )
    base_rate_type: Optional[str] = Field(
        default="corporate",
        description="Base rate type for lookup"
    )


class FullAnalysisResponse(BaseModel):
    """Response model for /api/pricing/full-analysis endpoint."""
    ratings: Dict[str, Any]
    spread_min_bps: float
    spread_max_bps: float
    spread_mid_bps: float
    base_rate_pct: float
    expected_rate_min: float
    expected_rate_max: float
    expected_rate_mid: float
    actual_rate_pct: float
    delta_bps: float
    interpretation: str


@router.post("/pricing/lookup", response_model=SpreadLookupResponse)
def lookup_pricing(request: SpreadLookupRequest) -> SpreadLookupResponse:
    """
    Look up spread for a given rating and tenor.

    Returns the min, mid, and max spread in basis points from the pricing matrix.
    """
    try:
        matrix = load_pricing_matrix()
        spread = lookup_spread(request.rating, request.tenor, matrix)

        return SpreadLookupResponse(
            rating=request.rating,
            tenor=request.tenor,
            min_spread_bps=spread["min_bps"],
            max_spread_bps=spread["max_bps"],
            mid_spread_bps=spread["mid_bps"],
        )

    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Pricing lookup error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pricing lookup error: {str(e)}"
        )


@router.post("/pricing/full-analysis", response_model=FullAnalysisResponse)
def full_analysis(request: FullAnalysisRequest) -> FullAnalysisResponse:
    """
    Complete pricing analysis: rate the company, look up spreads, compare to actual rate.

    Returns:
        - ratings: Full rating output from both engines
        - spread: Spread lookup (min, mid, max bps)
        - base_rate_pct: Current NZ base rate for facility type
        - expected_rate_range: Expected rate range (min, mid, max %)
        - actual_rate_pct: Actual rate offered (from request)
        - delta_bps: Difference between actual and expected mid-point (in bps)
        - interpretation: Brief interpretation of the pricing
    """
    try:
        # Step 1: Rate the company
        rating_request = RatingRequest(
            financials=request.financials,
            sector_id=request.sector_id,
            business_description=None,
        )
        rating_response = rate_company(rating_request)

        # Step 2: Look up spread for the blended rating
        matrix = load_pricing_matrix()
        spread = lookup_spread(
            rating_response.blended_rating,
            request.facility_tenor,
            matrix
        )

        # Step 3: Get base rate
        base_rate_type = request.base_rate_type or "corporate"
        base_rate_pct = get_base_rate(base_rate_type)

        # Step 4: Compute expected rate range
        expected_rate_range = compute_expected_rate_range(
            spread["min_bps"],
            spread["max_bps"],
            base_rate_pct
        )

        # Step 5: Compare actual vs expected
        delta_pct = request.actual_rate_pct - expected_rate_range["mid_rate"]
        delta_bps = delta_pct * 100.0

        # Step 6: Generate interpretation
        interpretation = _generate_interpretation(
            delta_bps,
            expected_rate_range["min_rate"],
            expected_rate_range["max_rate"],
            request.actual_rate_pct
        )

        return FullAnalysisResponse(
            ratings={
                "sp_rating": rating_response.sp_rating,
                "moodys_rating": rating_response.moodys_rating,
                "moodys_sp_equivalent": rating_response.moodys_sp_equivalent,
                "blended_rating": rating_response.blended_rating,
            },
            spread_min_bps=spread["min_bps"],
            spread_max_bps=spread["max_bps"],
            spread_mid_bps=spread["mid_bps"],
            base_rate_pct=base_rate_pct,
            expected_rate_min=expected_rate_range["min_rate"],
            expected_rate_max=expected_rate_range["max_rate"],
            expected_rate_mid=expected_rate_range["mid_rate"],
            actual_rate_pct=request.actual_rate_pct,
            delta_bps=delta_bps,
            interpretation=interpretation,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Full analysis error: {str(e)}"
        )


def _generate_interpretation(
    delta_bps: float,
    min_rate: float,
    max_rate: float,
    actual_rate: float
) -> str:
    """Generate a brief text interpretation of the pricing delta."""
    if abs(delta_bps) < 10:
        status = "inline with expected range"
    elif delta_bps >= 10 and delta_bps <= 50:
        status = "slightly tight (below market expectations)"
    elif delta_bps > 50:
        status = "significantly tight (attractive pricing)"
    elif delta_bps >= -50 and delta_bps < -10:
        status = "slightly loose (above market expectations)"
    else:
        status = "significantly loose (poor pricing)"

    return (
        f"Actual rate {actual_rate:.2f}% is {status}. "
        f"Expected range: {min_rate:.2f}% - {max_rate:.2f}%."
    )
