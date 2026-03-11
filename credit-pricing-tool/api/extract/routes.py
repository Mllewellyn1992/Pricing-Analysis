"""
Extract routes
POST /api/extract/pdf - PDF financial data extraction
POST /api/classify-sector - Sector classification
"""

import os
import tempfile
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from extraction.pdf_extractor import extract_text_from_pdf, extract_tables_from_pdf
from extraction.financial_mapper import map_financials_with_ai, map_financials_heuristic
from extraction.sector_classifier import classify_sector_with_ai, classify_sector_heuristic

router = APIRouter()
logger = logging.getLogger(__name__)


class ExtractionResponse(BaseModel):
    """Response model for PDF extraction."""
    status: str
    filename: str
    extracted_fields: Dict[str, Any]
    confidence_scores: Dict[str, float]
    raw_text_preview: str
    extraction_method: str
    currency: str
    fiscal_period: str
    message: str


class SectorClassificationRequest(BaseModel):
    """Request model for sector classification."""
    business_description: str


class SectorClassificationResponse(BaseModel):
    """Response model for sector classification."""
    sp_sector: str
    moodys_sector: str
    confidence: float
    reasoning: str
    method: str


@router.post("/extract/pdf", response_model=ExtractionResponse)
async def extract_pdf(file: UploadFile = File(...)) -> ExtractionResponse:
    """
    Extract financial data from a PDF financial statement.

    Process:
    1. Accepts multipart PDF file upload
    2. Extracts text (Docling → pdfplumber → PyPDF2, with OCR fallback)
    3. Extracts tables from document
    4. Uses Claude API to intelligently identify financial fields (or heuristic fallback)
    5. Returns structured financial data with confidence scores

    Args:
        file: Uploaded PDF file

    Returns:
        Extraction status, extracted fields, confidence scores, and preview text

    Raises:
        HTTPException: If file is not PDF or extraction fails
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="File must have a filename"
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="File must be a PDF"
        )

    temp_path = None
    try:
        # Save uploaded file to temp location
        content = await file.read()
        temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.write(temp_fd, content)
        os.close(temp_fd)

        logger.info(f"Extracting financial data from: {file.filename}")

        # Extract text from PDF
        try:
            raw_text = extract_text_from_pdf(temp_path)
            logger.debug(f"Extracted {len(raw_text)} characters of text")
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"Failed to extract text from PDF: {str(e)}"
            )

        # Extract tables from PDF
        try:
            tables = extract_tables_from_pdf(temp_path)
            logger.debug(f"Extracted {len(tables)} tables")
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")
            tables = []

        # Map financial fields
        try:
            # Try AI-powered extraction first
            extraction_result = map_financials_with_ai(raw_text, tables)

            # Fall back to heuristic if AI didn't work well
            if extraction_result.get("method") == "ai" and not extraction_result.get("fields"):
                logger.info("AI extraction returned no fields, trying heuristic")
                extraction_result = map_financials_heuristic(raw_text, tables)

        except Exception as e:
            logger.warning(f"Financial field extraction failed: {e}")
            # Fall back to heuristic
            extraction_result = map_financials_heuristic(raw_text, tables)

        extracted_fields = extraction_result.get("fields", {})
        confidence_scores = extraction_result.get("confidence", {})
        extraction_method = extraction_result.get("method", "unknown")
        currency = extraction_result.get("currency", "UNKNOWN")
        fiscal_period = extraction_result.get("fiscal_period", "UNKNOWN")

        logger.info(
            f"Extraction complete: {len(extracted_fields)} fields extracted "
            f"using {extraction_method} method"
        )

        # Create preview of raw text
        raw_text_preview = raw_text[:500] if raw_text else ""

        return ExtractionResponse(
            status="success",
            filename=file.filename,
            extracted_fields=extracted_fields,
            confidence_scores=confidence_scores,
            raw_text_preview=raw_text_preview,
            extraction_method=extraction_method,
            currency=currency,
            fiscal_period=fiscal_period,
            message=f"Successfully extracted {len(extracted_fields)} financial fields from {file.filename}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during extraction: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}"
        )
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")


@router.post("/classify-sector", response_model=SectorClassificationResponse)
async def classify_sector(request: SectorClassificationRequest) -> SectorClassificationResponse:
    """
    Classify company into S&P and Moody's sectors.

    Uses Claude API for intelligent classification based on business description,
    with keyword-based heuristic fallback.

    Args:
        request: Request containing business_description

    Returns:
        Sector classification with confidence and reasoning

    Raises:
        HTTPException: If classification fails
    """
    if not request.business_description or not request.business_description.strip():
        raise HTTPException(
            status_code=400,
            detail="business_description cannot be empty"
        )

    try:
        logger.info("Classifying company sector")

        # Try AI-powered classification
        result = classify_sector_with_ai(request.business_description)

        # Fall back to heuristic if confidence is too low
        if result.get("confidence", 0) < 0.4:
            logger.info("AI confidence too low, trying heuristic")
            result = classify_sector_heuristic(request.business_description)

        logger.info(
            f"Sector classification: S&P={result['sp_sector']}, "
            f"Moody's={result['moodys_sector']}, "
            f"confidence={result['confidence']}"
        )

        return SectorClassificationResponse(**result)

    except Exception as e:
        logger.error(f"Sector classification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )
