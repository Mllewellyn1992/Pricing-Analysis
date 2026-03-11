"""
FastAPI routes for database persistence operations.
Handles companies, snapshots, analyses, and PDF uploads.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from .supabase_client import is_configured
from .repositories import SupabaseRepository

router = APIRouter(tags=["database"])


# =========================================================================
# Request/Response Models
# =========================================================================


class CompanyCreateRequest(BaseModel):
    """Create a company."""

    user_id: str
    name: str
    description: Optional[str] = None
    sp_sector: Optional[str] = None
    moodys_sector: Optional[str] = None


class SnapshotCreateRequest(BaseModel):
    """Create a financial snapshot."""

    user_id: str
    label: Optional[str] = None
    source: str = "manual"
    # Include all financial fields
    revenue_mn: Optional[float] = None
    ebit_mn: Optional[float] = None
    depreciation_mn: Optional[float] = None
    amortization_mn: Optional[float] = None
    interest_expense_mn: Optional[float] = None
    cash_interest_paid_mn: Optional[float] = None
    cash_taxes_paid_mn: Optional[float] = None
    st_debt_mn: Optional[float] = None
    cpltd_mn: Optional[float] = None
    lt_debt_net_mn: Optional[float] = None
    capital_leases_mn: Optional[float] = None
    total_debt_mn: Optional[float] = None
    cash_mn: Optional[float] = None
    cash_like_mn: Optional[float] = None
    marketable_securities_mn: Optional[float] = None
    total_equity_mn: Optional[float] = None
    minority_interest_mn: Optional[float] = None
    deferred_taxes_mn: Optional[float] = None
    nwc_current_mn: Optional[float] = None
    nwc_prior_mn: Optional[float] = None
    lt_operating_assets_current_mn: Optional[float] = None
    lt_operating_assets_prior_mn: Optional[float] = None
    assets_current_mn: Optional[float] = None
    assets_prior_mn: Optional[float] = None
    cfo_mn: Optional[float] = None
    capex_mn: Optional[float] = None
    common_dividends_mn: Optional[float] = None
    preferred_dividends_mn: Optional[float] = None
    minority_dividends_mn: Optional[float] = None
    share_buybacks_mn: Optional[float] = None
    dividends_paid_mn: Optional[float] = None
    avg_capital_mn: Optional[float] = None
    as_of_date: Optional[str] = None
    pdf_filename: Optional[str] = None
    confidence: Optional[float] = None


class AnalysisCreateRequest(BaseModel):
    """Create an analysis."""

    user_id: str
    sp_rating: Optional[str] = None
    sp_anchor: Optional[str] = None
    sp_business_risk: Optional[int] = None
    sp_financial_risk: Optional[int] = None
    moodys_rating: Optional[str] = None
    moodys_sp_equiv: Optional[str] = None
    moodys_score: Optional[float] = None
    blended_rating: Optional[str] = None
    spread_min_bps: Optional[float] = None
    spread_max_bps: Optional[float] = None
    spread_mid_bps: Optional[float] = None
    base_rate_pct: Optional[float] = None
    base_rate_type: str = "corporate"
    expected_rate_min: Optional[float] = None
    expected_rate_max: Optional[float] = None
    expected_rate_mid: Optional[float] = None
    actual_rate_pct: Optional[float] = None
    delta_bps: Optional[float] = None
    facility_tenor: int = 3
    facility_type: str = "corporate"
    computed_metrics: Optional[Dict[str, Any]] = None
    sp_workings: Optional[Dict[str, Any]] = None
    moodys_workings: Optional[Dict[str, Any]] = None


# =========================================================================
# Helper Functions
# =========================================================================


def _check_configured():
    """Check if Supabase is configured, raise 503 if not."""
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY environment variables.",
        )


# =========================================================================
# COMPANIES
# =========================================================================


@router.post("/companies")
def create_company(req: CompanyCreateRequest) -> Dict[str, Any]:
    """
    Create a new company.

    Args:
        req: Company creation request

    Returns:
        Created company dict
    """
    _check_configured()

    try:
        company = SupabaseRepository.save_company(
            user_id=req.user_id,
            name=req.name,
            description=req.description,
            sp_sector=req.sp_sector,
            moodys_sector=req.moodys_sector,
        )

        if not company:
            raise HTTPException(status_code=500, detail="Failed to create company")

        return company
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/companies")
def list_companies(user_id: str = Query(..., description="User ID")) -> List[Dict[str, Any]]:
    """
    List all companies for a user.

    Args:
        user_id: UUID of the user

    Returns:
        List of company dicts
    """
    _check_configured()

    try:
        companies = SupabaseRepository.get_companies(user_id)
        return companies
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# =========================================================================
# FINANCIAL SNAPSHOTS
# =========================================================================


@router.post("/companies/{company_id}/snapshots")
def create_snapshot(company_id: str, req: SnapshotCreateRequest) -> Dict[str, Any]:
    """
    Create a financial snapshot for a company.

    Args:
        company_id: UUID of the company
        req: Snapshot creation request

    Returns:
        Created snapshot dict
    """
    _check_configured()

    try:
        # Build financials dict from request (exclude user_id, label, source)
        financials = {
            k: v
            for k, v in req.model_dump().items()
            if k not in ["user_id", "label", "source"]
        }

        snapshot = SupabaseRepository.save_snapshot(
            user_id=req.user_id,
            company_id=company_id,
            financials_dict=financials,
            label=req.label,
            source=req.source,
        )

        if not snapshot:
            raise HTTPException(status_code=500, detail="Failed to create snapshot")

        return snapshot
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/companies/{company_id}/snapshots")
def list_snapshots(company_id: str) -> List[Dict[str, Any]]:
    """
    List all snapshots for a company.

    Args:
        company_id: UUID of the company

    Returns:
        List of snapshot dicts
    """
    _check_configured()

    try:
        snapshots = SupabaseRepository.get_snapshots(company_id)
        return snapshots
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# =========================================================================
# ANALYSES
# =========================================================================


@router.post("/companies/{company_id}/snapshots/{snapshot_id}/analyze")
def create_analysis(
    company_id: str, snapshot_id: str, req: AnalysisCreateRequest
) -> Dict[str, Any]:
    """
    Create an analysis for a financial snapshot.

    Args:
        company_id: UUID of the company
        snapshot_id: UUID of the snapshot
        req: Analysis creation request

    Returns:
        Created analysis dict
    """
    _check_configured()

    try:
        # Build analysis dict from request (exclude user_id)
        analysis = {k: v for k, v in req.model_dump().items() if k != "user_id"}

        result = SupabaseRepository.save_analysis(
            user_id=req.user_id,
            company_id=company_id,
            snapshot_id=snapshot_id,
            analysis_dict=analysis,
        )

        if not result:
            raise HTTPException(status_code=500, detail="Failed to create analysis")

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/companies/{company_id}/analyses")
def list_analyses(company_id: str) -> List[Dict[str, Any]]:
    """
    List all analyses for a company.

    Args:
        company_id: UUID of the company

    Returns:
        List of analysis dicts
    """
    _check_configured()

    try:
        analyses = SupabaseRepository.get_analyses(company_id)
        return analyses
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# =========================================================================
# BASE RATES (Public/Scraped)
# =========================================================================


@router.get("/base-rates")
def get_base_rates() -> Dict[str, Dict[str, Any]]:
    """
    Get the latest base rates for each bank.

    Returns:
        Dict mapping bank names to their latest rate records
    """
    _check_configured()

    try:
        rates = SupabaseRepository.get_latest_base_rates()
        return rates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# =========================================================================
# PDF UPLOADS
# =========================================================================


@router.post("/pdf-uploads")
def upload_pdf(
    user_id: str = Query(...),
    company_id: str = Query(...),
    filename: str = Query(...),
    file_size: int = Query(...),
    storage_path: str = Query(...),
) -> Dict[str, Any]:
    """
    Record a PDF upload.

    Args:
        user_id: UUID of the user
        company_id: UUID of the company
        filename: Original filename
        file_size: File size in bytes
        storage_path: Path in Supabase Storage

    Returns:
        Created upload record dict
    """
    _check_configured()

    try:
        upload = SupabaseRepository.save_pdf_upload(
            user_id=user_id,
            company_id=company_id,
            filename=filename,
            file_size=file_size,
            storage_path=storage_path,
        )

        if not upload:
            raise HTTPException(status_code=500, detail="Failed to create upload record")

        return upload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/pdf-uploads/{upload_id}/status")
def update_pdf_status(
    upload_id: str,
    status: str = Query(..., description="'pending', 'processing', 'completed', or 'failed'"),
    extracted_fields: Optional[Dict[str, Any]] = None,
    confidence_scores: Optional[Dict[str, float]] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update the processing status of a PDF upload.

    Args:
        upload_id: UUID of the upload
        status: New status
        extracted_fields: Extracted financial data
        confidence_scores: Per-field confidence scores
        error_message: Error message if failed

    Returns:
        Updated upload record dict
    """
    _check_configured()

    try:
        if status not in ["pending", "processing", "completed", "failed"]:
            raise HTTPException(status_code=400, detail="Invalid status")

        result = SupabaseRepository.update_pdf_upload_status(
            upload_id=upload_id,
            status=status,
            extracted_fields=extracted_fields,
            confidence_scores=confidence_scores,
            error_message=error_message,
        )

        if not result:
            raise HTTPException(status_code=500, detail="Failed to update upload status")

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/pdf-uploads")
def list_pdf_uploads(user_id: str = Query(...)) -> List[Dict[str, Any]]:
    """
    List all PDF uploads for a user.

    Args:
        user_id: UUID of the user

    Returns:
        List of upload records
    """
    _check_configured()

    try:
        uploads = SupabaseRepository.get_pdf_uploads(user_id)
        return uploads
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
