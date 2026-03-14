"""
Extract routes
POST /api/extract/pdf - PDF financial data extraction + business description + sector classification
POST /api/classify-sector - Sector classification
"""

import os
import re
import gc
import time
import uuid
import hashlib
import asyncio
import tempfile
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from extraction.pdf_extractor import extract_text_from_pdf, extract_tables_from_pdf
from extraction.financial_mapper import map_financials_with_ai, map_financials_heuristic, validate_and_fix_extraction
from extraction.sector_classifier import classify_sector_with_ai, classify_sector_heuristic

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Thread pool for blocking operations ──────────────────────────────────────
# Single thread to avoid memory spikes from parallel OCR/pdfplumber
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="extract")

# ── Simple in-memory extraction cache (file hash → result) ───────────────────
_extraction_cache: Dict[str, dict] = {}
_CACHE_MAX_SIZE = 20  # Keep last 20 extractions

# ── Operation timeout constants ──────────────────────────────────────────────
_TEXT_EXTRACTION_TIMEOUT = 120   # 2 minutes for text extraction (incl. OCR)
_TABLE_EXTRACTION_TIMEOUT = 60   # 1 minute for table extraction
_AI_MAPPING_TIMEOUT = 60         # 1 minute for Claude financial mapping
_SECTOR_TIMEOUT = 30             # 30 seconds for sector classification
_TOTAL_REQUEST_TIMEOUT = 210     # 3.5 minutes absolute max per request


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
    warnings: List[str] = []
    timing: Optional[Dict[str, float]] = None
    request_id: Optional[str] = None


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


def _compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content for caching."""
    return hashlib.sha256(content).hexdigest()


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


async def _run_with_timeout(func, *args, timeout: float, label: str, request_id: str):
    """Run a blocking function in the thread pool with a timeout.

    Returns (result, elapsed_seconds) or raises on timeout.
    """
    loop = asyncio.get_event_loop()
    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(_executor, func, *args),
            timeout=timeout,
        )
        elapsed = time.monotonic() - t0
        logger.info(f"[{request_id}] {label}: completed in {elapsed:.1f}s")
        return result, elapsed
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        logger.error(f"[{request_id}] {label}: TIMED OUT after {elapsed:.1f}s (limit={timeout}s)")
        raise


async def _save_upload_to_temp(file: UploadFile, request_id: str) -> tuple:
    """Validate and save upload to a temp file. Returns (temp_path, file_size_mb, file_hash)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > 50:
        raise HTTPException(
            status_code=413,
            detail=f"PDF too large ({file_size_mb:.1f}MB). Maximum is 50MB."
        )

    file_hash = _compute_file_hash(content)
    logger.info(f"[{request_id}] File: {file.filename} ({file_size_mb:.1f}MB, hash={file_hash[:12]})")

    temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    os.write(temp_fd, content)
    os.close(temp_fd)
    del content
    gc.collect()
    return temp_path, file_size_mb, file_hash


def _extract_text_sync(temp_path: str) -> str:
    """Synchronous text extraction (runs in thread pool)."""
    return extract_text_from_pdf(temp_path)


def _extract_tables_sync(temp_path: str) -> list:
    """Synchronous table extraction (runs in thread pool)."""
    return extract_tables_from_pdf(temp_path)


def _map_fields_sync(raw_text: str, tables: list) -> dict:
    """Synchronous financial field mapping (runs in thread pool)."""
    try:
        result = map_financials_with_ai(raw_text, tables)
        if result.get("method") == "ai" and not result.get("fields"):
            logger.info("AI extraction returned no fields, trying heuristic")
            result = map_financials_heuristic(raw_text, tables)
    except Exception as e:
        logger.warning(f"Financial field extraction failed: {e}")
        result = map_financials_heuristic(raw_text, tables)
    return result


def _classify_sector_sync(classify_text: str) -> Optional[dict]:
    """Synchronous sector classification (runs in thread pool)."""
    result = classify_sector_with_ai(classify_text)
    if result.get("confidence", 0) < 0.4:
        result = classify_sector_heuristic(classify_text)
    return result


@router.post("/extract/pdf", response_model=ExtractionResponse)
async def extract_pdf(file: UploadFile = File(...)) -> ExtractionResponse:
    """Extract financial data from a PDF financial statement.

    Pipeline: upload → text extraction → [table extraction, AI mapping, sector] → response
    All blocking operations run in a thread pool with individual timeouts.
    """
    request_id = uuid.uuid4().hex[:8]
    request_start = time.monotonic()
    temp_path = None
    warnings: List[str] = []
    timing: Dict[str, float] = {}

    try:
        # ── Step 1: Save upload ──────────────────────────────────────────
        temp_path, file_size_mb, file_hash = await _save_upload_to_temp(file, request_id)

        # ── Step 1.5: Check cache ────────────────────────────────────────
        if file_hash in _extraction_cache:
            logger.info(f"[{request_id}] Cache HIT for {file_hash[:12]}")
            cached = _extraction_cache[file_hash]
            cached_response = ExtractionResponse(**cached)
            cached_response.request_id = request_id
            cached_response.message = f"Cached result: {cached_response.message}"
            return cached_response

        # ── Step 2: Text extraction (with timeout) ───────────────────────
        try:
            raw_text, t = await _run_with_timeout(
                _extract_text_sync, temp_path,
                timeout=_TEXT_EXTRACTION_TIMEOUT,
                label="Text extraction",
                request_id=request_id,
            )
            timing["text_extraction"] = t
            gc.collect()
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=422,
                detail="Text extraction timed out. The PDF may be too large or complex for OCR."
            )
        except Exception as e:
            logger.error(f"[{request_id}] Text extraction failed: {e}")
            raise HTTPException(status_code=422, detail=f"Failed to extract text from PDF: {str(e)}")

        if not raw_text or len(raw_text.strip()) < 50:
            raise HTTPException(
                status_code=422,
                detail="Could not extract meaningful text from this PDF. It may be encrypted or image-only."
            )

        # ── Step 3: Table extraction (with timeout, non-fatal) ───────────
        tables = []
        try:
            tables, t = await _run_with_timeout(
                _extract_tables_sync, temp_path,
                timeout=_TABLE_EXTRACTION_TIMEOUT,
                label="Table extraction",
                request_id=request_id,
            )
            timing["table_extraction"] = t
            gc.collect()
        except asyncio.TimeoutError:
            warnings.append("Table extraction timed out — using text-only extraction")
            logger.warning(f"[{request_id}] Table extraction timed out")
        except Exception as e:
            warnings.append(f"Table extraction failed: {str(e)[:80]}")
            logger.warning(f"[{request_id}] Table extraction failed: {e}")

        # ── Step 4: AI mapping + sector classification (PARALLEL) ────────
        business_description = None
        try:
            business_description = extract_business_description(raw_text)
        except Exception as e:
            warnings.append("Business description extraction failed")
            logger.warning(f"[{request_id}] Business description extraction failed: {e}")

        classify_text = business_description or raw_text[:500]

        # Run financial mapping and sector classification concurrently
        mapping_task = _run_with_timeout(
            _map_fields_sync, raw_text, tables,
            timeout=_AI_MAPPING_TIMEOUT,
            label="Financial mapping",
            request_id=request_id,
        )
        sector_task = _run_with_timeout(
            _classify_sector_sync, classify_text,
            timeout=_SECTOR_TIMEOUT,
            label="Sector classification",
            request_id=request_id,
        )

        # Gather both results concurrently, handle each independently
        results = await asyncio.gather(mapping_task, sector_task, return_exceptions=True)

        # Process financial mapping result
        extraction_result = None
        if isinstance(results[0], Exception):
            if isinstance(results[0], asyncio.TimeoutError):
                warnings.append("AI financial mapping timed out — using heuristic extraction")
                logger.warning(f"[{request_id}] AI mapping timed out, falling back to heuristic")
            else:
                warnings.append(f"AI mapping failed: {str(results[0])[:80]}")
                logger.warning(f"[{request_id}] AI mapping failed: {results[0]}")
            # Fallback to heuristic (fast, no timeout needed)
            extraction_result = map_financials_heuristic(raw_text, tables)
            timing["financial_mapping"] = 0
        else:
            extraction_result, t = results[0]
            timing["financial_mapping"] = t

        # Process sector classification result
        sector_classification = None
        if isinstance(results[1], Exception):
            if isinstance(results[1], asyncio.TimeoutError):
                warnings.append("Sector classification timed out")
            else:
                warnings.append(f"Sector classification failed: {str(results[1])[:80]}")
            logger.warning(f"[{request_id}] Sector classification failed: {results[1]}")
            timing["sector_classification"] = 0
        else:
            sector_result, t = results[1]
            timing["sector_classification"] = t
            try:
                sector_classification = SectorClassification(**sector_result)
                logger.info(f"[{request_id}] Sector: S&P={sector_classification.sp_sector}, conf={sector_classification.confidence}")
            except Exception as e:
                warnings.append(f"Invalid sector result: {str(e)[:60]}")
                logger.warning(f"[{request_id}] Invalid sector result: {e}")

        # ── Step 4.5: Validate + auto-fix extraction ─────────────────────
        try:
            t0_val = time.monotonic()
            extraction_result = validate_and_fix_extraction(
                extraction_result,
                raw_text=raw_text,
                tables=tables,
                enable_ai_fix=True,
            )
            timing["validation"] = time.monotonic() - t0_val

            validation = extraction_result.get("validation", {})
            n_errors = len(validation.get("errors", []))
            n_warnings = len(validation.get("warnings", []))
            n_corrections = len(validation.get("corrections", {}))

            if n_corrections > 0:
                corrections_detail = "; ".join(
                    f"{k}: {v['old']}→{v['new']}"
                    for k, v in validation.get("corrections", {}).items()
                )
                warnings.append(f"Auto-corrected {n_corrections} field(s): {corrections_detail}")

            post_errors = validation.get("post_fix_errors", validation.get("errors", []))
            if post_errors:
                for issue in post_errors:
                    warnings.append(
                        f"Validation {issue['severity']}: {issue['check']} "
                        f"(off by {issue.get('pct_off', '?')}%)"
                    )

            if n_errors == 0 and n_warnings == 0:
                logger.info(f"[{request_id}] All validation checks passed")
            else:
                logger.info(
                    f"[{request_id}] Validation: {n_errors} errors, {n_warnings} warnings, "
                    f"{n_corrections} auto-corrections"
                )
        except Exception as e:
            warnings.append(f"Validation step failed: {str(e)[:80]}")
            logger.warning(f"[{request_id}] Validation failed: {e}")

        # ── Step 5: Build response ───────────────────────────────────────
        extracted_fields = extraction_result.get("fields", {})
        confidence_scores = extraction_result.get("confidence", {})
        total_time = time.monotonic() - request_start
        timing["total"] = total_time

        logger.info(
            f"[{request_id}] DONE: {len(extracted_fields)} fields via {extraction_result.get('method')} "
            f"in {total_time:.1f}s (text={timing.get('text_extraction', 0):.1f}s, "
            f"tables={timing.get('table_extraction', 0):.1f}s, "
            f"mapping={timing.get('financial_mapping', 0):.1f}s, "
            f"sector={timing.get('sector_classification', 0):.1f}s)"
        )

        response_data = dict(
            status="success",
            filename=file.filename,
            extracted_fields=extracted_fields,
            confidence_scores=confidence_scores,
            raw_text_preview=raw_text[:500] if raw_text else "",
            extraction_method=extraction_result.get("method", "unknown"),
            currency=extraction_result.get("currency", "UNKNOWN"),
            fiscal_period=extraction_result.get("fiscal_period", "UNKNOWN"),
            message=f"Extracted {len(extracted_fields)} fields from {file.filename} in {total_time:.0f}s",
            business_description=business_description,
            sector_classification=sector_classification,
            warnings=warnings,
            timing=timing,
            request_id=request_id,
        )

        # ── Step 6: Cache the result ─────────────────────────────────────
        if len(_extraction_cache) >= _CACHE_MAX_SIZE:
            # Evict oldest entry
            oldest_key = next(iter(_extraction_cache))
            del _extraction_cache[oldest_key]
        # Cache a serializable copy (sector_classification needs to be a dict)
        cache_copy = {**response_data}
        if cache_copy["sector_classification"]:
            cache_copy["sector_classification"] = cache_copy["sector_classification"].model_dump()
        _extraction_cache[file_hash] = cache_copy

        return ExtractionResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        total_time = time.monotonic() - request_start
        logger.error(f"[{request_id}] FAILED after {total_time:.1f}s: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"[{request_id}] Failed to clean up temp file: {e}")


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
