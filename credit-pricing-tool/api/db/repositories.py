"""
CRUD operations for all Supabase tables.
Handles companies, financial snapshots, analyses, base rates, and PDF uploads.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from .supabase_client import get_client


class SupabaseRepository:
    """Repository for all database operations."""

    @staticmethod
    def _handle_error(error: Exception, operation: str) -> None:
        """Log database errors for debugging."""
        print(f"Database error in {operation}: {str(error)}")

    # =========================================================================
    # COMPANIES
    # =========================================================================

    @staticmethod
    def save_company(
        user_id: str,
        name: str,
        description: Optional[str] = None,
        sp_sector: Optional[str] = None,
        moodys_sector: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new company record.

        Args:
            user_id: UUID of the user
            name: Company name
            description: Business description for sector mapping
            sp_sector: S&P sector ID
            moodys_sector: Moody's sector ID

        Returns:
            Created company dict with id, or None if failed
        """
        client = get_client()
        if not client:
            return None

        try:
            data = {
                "user_id": user_id,
                "name": name,
                "description": description,
                "sp_sector": sp_sector,
                "moodys_sector": moodys_sector,
            }
            response = client.table("companies").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "save_company")
            return None

    @staticmethod
    def get_companies(user_id: str) -> List[Dict[str, Any]]:
        """
        Get all companies for a user.

        Args:
            user_id: UUID of the user

        Returns:
            List of company dicts, or empty list if failed
        """
        client = get_client()
        if not client:
            return []

        try:
            response = client.table("companies").select("*").eq("user_id", user_id).execute()
            return response.data or []
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_companies")
            return []

    @staticmethod
    def get_company(company_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single company by ID.

        Args:
            company_id: UUID of the company

        Returns:
            Company dict, or None if not found or error
        """
        client = get_client()
        if not client:
            return None

        try:
            response = client.table("companies").select("*").eq("id", company_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_company")
            return None

    # =========================================================================
    # FINANCIAL SNAPSHOTS
    # =========================================================================

    @staticmethod
    def save_snapshot(
        user_id: str,
        company_id: str,
        financials_dict: Dict[str, Any],
        label: Optional[str] = None,
        source: str = "manual",
    ) -> Optional[Dict[str, Any]]:
        """
        Save a financial snapshot for a company.

        Args:
            user_id: UUID of the user
            company_id: UUID of the company
            financials_dict: Dictionary with all financial fields
            label: Label like "FY2025" or "H1 2025"
            source: 'manual', 'pdf_upload', or 'api'

        Returns:
            Created snapshot dict with id, or None if failed
        """
        client = get_client()
        if not client:
            return None

        try:
            data = {
                "user_id": user_id,
                "company_id": company_id,
                "label": label,
                "source": source,
                **financials_dict,
            }
            response = client.table("financial_snapshots").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "save_snapshot")
            return None

    @staticmethod
    def get_snapshots(company_id: str) -> List[Dict[str, Any]]:
        """
        Get all snapshots for a company.

        Args:
            company_id: UUID of the company

        Returns:
            List of snapshot dicts, or empty list if failed
        """
        client = get_client()
        if not client:
            return []

        try:
            response = (
                client.table("financial_snapshots")
                .select("*")
                .eq("company_id", company_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_snapshots")
            return []

    @staticmethod
    def get_snapshot(snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single snapshot by ID.

        Args:
            snapshot_id: UUID of the snapshot

        Returns:
            Snapshot dict, or None if not found or error
        """
        client = get_client()
        if not client:
            return None

        try:
            response = (
                client.table("financial_snapshots")
                .select("*")
                .eq("id", snapshot_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_snapshot")
            return None

    # =========================================================================
    # ANALYSES
    # =========================================================================

    @staticmethod
    def save_analysis(
        user_id: str,
        company_id: str,
        snapshot_id: str,
        analysis_dict: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Save an analysis result for a snapshot.

        Args:
            user_id: UUID of the user
            company_id: UUID of the company
            snapshot_id: UUID of the financial snapshot
            analysis_dict: Dictionary with rating and pricing results

        Returns:
            Created analysis dict with id, or None if failed
        """
        client = get_client()
        if not client:
            return None

        try:
            data = {
                "user_id": user_id,
                "company_id": company_id,
                "snapshot_id": snapshot_id,
                **analysis_dict,
            }
            response = client.table("analyses").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "save_analysis")
            return None

    @staticmethod
    def get_analyses(company_id: str) -> List[Dict[str, Any]]:
        """
        Get all analyses for a company.

        Args:
            company_id: UUID of the company

        Returns:
            List of analysis dicts, or empty list if failed
        """
        client = get_client()
        if not client:
            return []

        try:
            response = (
                client.table("analyses")
                .select("*")
                .eq("company_id", company_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_analyses")
            return []

    @staticmethod
    def get_analysis(analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single analysis by ID.

        Args:
            analysis_id: UUID of the analysis

        Returns:
            Analysis dict, or None if not found or error
        """
        client = get_client()
        if not client:
            return None

        try:
            response = client.table("analyses").select("*").eq("id", analysis_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_analysis")
            return None

    # =========================================================================
    # BASE RATES
    # =========================================================================

    @staticmethod
    def save_base_rates(rates_list: List[Dict[str, Any]]) -> bool:
        """
        Save scraped base rates (service role operation).

        Args:
            rates_list: List of rate dicts with bank, corporate_rate, working_capital_rate, etc.

        Returns:
            True if successful, False otherwise
        """
        client = get_client()
        if not client:
            return False

        try:
            for rate in rates_list:
                rate["scraped_at"] = datetime.utcnow().isoformat()
            response = client.table("base_rates").insert(rates_list).execute()
            return bool(response.data)
        except Exception as e:
            SupabaseRepository._handle_error(e, "save_base_rates")
            return False

    @staticmethod
    def get_latest_base_rates() -> Dict[str, Dict[str, Any]]:
        """
        Get the latest base rates for each bank.

        Returns:
            Dict mapping bank names to their latest rate records
        """
        client = get_client()
        if not client:
            return {}

        try:
            response = (
                client.table("base_rates")
                .select("*")
                .order("bank")
                .order("scraped_at", desc=True)
                .execute()
            )

            rates_by_bank = {}
            for rate in response.data or []:
                bank = rate.get("bank")
                if bank and bank not in rates_by_bank:
                    rates_by_bank[bank] = rate

            return rates_by_bank
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_latest_base_rates")
            return {}

    # =========================================================================
    # PDF UPLOADS
    # =========================================================================

    @staticmethod
    def save_pdf_upload(
        user_id: str,
        company_id: str,
        filename: str,
        file_size: int,
        storage_path: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Record a PDF upload.

        Args:
            user_id: UUID of the user
            company_id: UUID of the company
            filename: Original filename
            file_size: File size in bytes
            storage_path: Path in Supabase Storage

        Returns:
            Created upload record dict, or None if failed
        """
        client = get_client()
        if not client:
            return None

        try:
            data = {
                "user_id": user_id,
                "company_id": company_id,
                "filename": filename,
                "file_size_bytes": file_size,
                "storage_path": storage_path,
                "extraction_status": "pending",
            }
            response = client.table("pdf_uploads").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "save_pdf_upload")
            return None

    @staticmethod
    def update_pdf_upload_status(
        upload_id: str,
        status: str,
        extracted_fields: Optional[Dict[str, Any]] = None,
        confidence_scores: Optional[Dict[str, float]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update the processing status of a PDF upload.

        Args:
            upload_id: UUID of the upload record
            status: 'pending', 'processing', 'completed', or 'failed'
            extracted_fields: Extracted financial data (JSONB)
            confidence_scores: Per-field confidence scores (JSONB)
            error_message: Error message if failed

        Returns:
            Updated record dict, or None if failed
        """
        client = get_client()
        if not client:
            return None

        try:
            data = {
                "extraction_status": status,
                "processed_at": datetime.utcnow().isoformat() if status in ["completed", "failed"] else None,
            }

            if extracted_fields is not None:
                data["extracted_fields"] = extracted_fields

            if confidence_scores is not None:
                data["confidence_scores"] = confidence_scores

            if error_message is not None:
                data["error_message"] = error_message

            response = (
                client.table("pdf_uploads")
                .update(data)
                .eq("id", upload_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "update_pdf_upload_status")
            return None

    @staticmethod
    def get_pdf_upload(upload_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a PDF upload record by ID.

        Args:
            upload_id: UUID of the upload

        Returns:
            Upload record dict, or None if not found or error
        """
        client = get_client()
        if not client:
            return None

        try:
            response = (
                client.table("pdf_uploads")
                .select("*")
                .eq("id", upload_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_pdf_upload")
            return None

    # =========================================================================
    # SAVED EXTRACTIONS
    # =========================================================================

    @staticmethod
    def save_extraction(
        name: str,
        filename: Optional[str],
        extracted_fields: Dict[str, Any],
        confidence_scores: Optional[Dict[str, Any]] = None,
        extraction_method: str = "ai",
        sector_classification: Optional[Dict[str, Any]] = None,
        business_description: Optional[str] = None,
        warnings: Optional[list] = None,
        fiscal_period: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Save an extraction result for later review."""
        client = get_client()
        if not client:
            return None

        try:
            data = {
                "name": name,
                "filename": filename,
                "extracted_fields": extracted_fields,
                "confidence_scores": confidence_scores or {},
                "extraction_method": extraction_method,
                "sector_classification": sector_classification,
                "business_description": business_description,
                "warnings": warnings or [],
                "fiscal_period": fiscal_period,
            }
            response = client.table("saved_extractions").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "save_extraction")
            return None

    @staticmethod
    def list_extractions(limit: int = 50) -> List[Dict[str, Any]]:
        """List saved extractions, newest first."""
        client = get_client()
        if not client:
            return []

        try:
            response = (
                client.table("saved_extractions")
                .select("id, name, filename, extraction_method, fiscal_period, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            SupabaseRepository._handle_error(e, "list_extractions")
            return []

    @staticmethod
    def get_extraction(extraction_id: str) -> Optional[Dict[str, Any]]:
        """Get a single saved extraction by ID (full data)."""
        client = get_client()
        if not client:
            return None

        try:
            response = (
                client.table("saved_extractions")
                .select("*")
                .eq("id", extraction_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_extraction")
            return None

    @staticmethod
    def delete_extraction(extraction_id: str) -> bool:
        """Delete a saved extraction."""
        client = get_client()
        if not client:
            return False

        try:
            client.table("saved_extractions").delete().eq("id", extraction_id).execute()
            return True
        except Exception as e:
            SupabaseRepository._handle_error(e, "delete_extraction")
            return False

    @staticmethod
    def get_pdf_uploads(user_id: str) -> List[Dict[str, Any]]:
        """
        Get all PDF uploads for a user.

        Args:
            user_id: UUID of the user

        Returns:
            List of upload records, or empty list if failed
        """
        client = get_client()
        if not client:
            return []

        try:
            response = (
                client.table("pdf_uploads")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            SupabaseRepository._handle_error(e, "get_pdf_uploads")
            return []
