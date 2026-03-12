"""
Extract routes
POST /api/extract/pdf - PDF financial data extraction + business description + sector classification
POST /api/classify-sector - Sector classification
"""

import os
import re
import tempfile
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from extraction.pdf_extractor import extract_text_from_pdf, extract_tables_from_pdf
from extraction.financial_mapper import map_financials_with_ai, map_financials_heuristic
from extraction.sector_classifier import classify_sector_with_ai, classify_sector_heuristic

router = APIRouter()
logger = logging.getLogger(__name__)


class SectorClassification(BaseModel):
    sp_sector: str
    moodys_sector: str
    confidence: float
    reasoning: str
    method: str


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
    business_description: Optional[str] = None
    sector_classification: Optional[SectorClassification] = None


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


def extract_business_description(raw_text: str) -> Optional[str]:
    """
    Extract a business description from the first few pages of a financial statement.

    NZ financial statements typically have a section describing the nature
    of business, principal activities, or company overview near the top.
    """
    if not raw_text:
        return None

    # Take the first ~3000 chars where the business description usually lives
    text_head = raw_text[:3000].lower()

    # Patterns that often precede business descriptions in NZ financials
    description_markers = [
        r"(?:nature\s+of\s+(?:the\s+)?business|principal\s+activit|company\s+overview|"
        r"about\s+(?:the\s+)?(?:company|group)|business\s+description|"
        r"(?:the\s+)?(?:company|group)\s+(?:is\s+|operates\s+|provides\s+|engages\s+in))",
    ]

    # Try to find a description paragraph after one of these markers
    for pattern in description_markers:
        match = re.search(pattern, text_head, re.IGNORECASE)
        if match:
            start = match.start()
            # Take up to 500 chars from the match point
            snippet = raw_text[start:start + 500]
            # Clean up to first double-newline or 2+ sentences
            lines = snippet.split('\n')
            desc_lines = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if desc_lines:
                        break
                    continue
                desc_lines.append(stripped)
                # Stop after collecting enough
                if len(' '.join(desc_lines)) > 200:
                    break
            if desc_lines:
                return ' '.join(desc_lines)[:500]

    # Fallback: just use the first meaningful paragraph from the document
    paragraphs = raw_text[:2000].split('\n\n')
    for para in paragraphs:
        cleaned = para.strip()
        # Skip short lines (headers, page numbers) and tables
        if len(cleaned) > 80 and not cleaned.startswith('|') and not re.match(r'^[\d,.\s$%]+$', cleaned):
            return cleaned[:500]

    # Last resort: first 300 chars
    return raw_text[:300].strip() if raw_text else None


@router.post("/extract/pdf", response_model=ExtractionResponse)
async def extract_pdf(file: UploadFile = File(...)) -> ExtractionResponse:
    """
    Extract financial data from a PDF financial statement.

    Process:
    1. Accepts multipart PDF file upload
    2. Extracts text using pdfplumber
    3. Extracts tables from document
    4. Uses Claude API to identify financial fields (or heuristic fallback)
    5. Extracts business description from document text
    6. Classifies sector using AI based on business description
    7. Returns structured data with confidence scores + sector classification
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

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
            extraction_result = map_financials_with_ai(raw_text, tables)
            if extraction_result.get("method") == "ai" and not extraction_result.get("fields"):
                logger.info("AI extraction returned no fields, trying heuristic")
                extraction_result = map_financials_heuristic(raw_text, tables)
        except Exception as e:
            logger.warning(f"Financial field extraction failed: {e}")
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

        # Extract business description from PDF text
        business_description = None
        try:
            business_description = extract_business_description(raw_text)
            if business_description:
                logger.info(f"Extracted business description ({len(business_description)} chars)")
        except Exception as e:
            logger.warning(f"Business description extraction failed: {e}")

        # Classify sector based on business description + raw text context
        sector_classification = None
        try:
            # Use business description if found, otherwise use first 500 chars of raw text
            classify_text = business_description or raw_text[:500]
            if classify_text:
                result = classify_sector_with_ai(classify_text)
                if result.get("confidence", 0) < 0.4:
                    result = classify_sector_heuristic(classify_text)
                sector_classification = SectorClassification(**result)
                logger.info(
                    f"Sector classified: S&P={sector_classification.sp_sector}, "
                    f"confidence={sector_classification.confidence}"
                )
        except Exception as e:
            logger.warning(f"Sector classification failed: {e}")

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
            business_description=business_description,
            sector_classification=sector_classification,
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
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")


@router.post("/classify-sector", response_model=SectorClassificationResponse)
async def classify_sector(request: SectorClassificationRequest) -> SectorClassificationResponse:
    """Classify company into S&P and Moody's sectors."""
    if not request.business_description or not request.business_description.strip():
        raise HTTPException(status_code=400, detail="business_description cannot be empty")

    try:
        result = classify_sector_with_ai(request.business_description)
        if result.get("confidence", 0) < 0.4:
            result = classify_sector_heuristic(request.business_description)

        return SectorClassificationResponse(**result)

    except Exception as e:
        logger.error(f"Sector classification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")
