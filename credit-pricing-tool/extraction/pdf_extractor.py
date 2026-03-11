"""
PDF text and table extraction with multiple fallback strategies.

Supports:
- Docling (primary): Advanced document parsing with layout understanding
- PyPDF2/pdfplumber (fallback): Standard PDF libraries
- OCRmyPDF → re-extract (fallback): For scanned documents

The module intelligently selects the best available tool and falls back
gracefully when libraries are unavailable.
"""

import os
import tempfile
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def _has_library(module_name: str) -> bool:
    """Check if a library is available without raising ImportError."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def _extract_text_with_docling(pdf_path: str) -> str:
    """
    Extract text from PDF using Docling (advanced layout understanding).

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text

    Raises:
        Exception: If Docling fails or is not available
    """
    from docling.document_converter import DocumentConverter, FormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling_core.types.doc import TextItem

    pdf_options = PdfPipelineOptions(
        do_ocr=False,
        force_backend_text=True,
        do_table_structure=True,
    )
    format_options = {
        InputFormat.PDF: FormatOption(
            pipeline_cls=StandardPdfPipeline,
            pipeline_options=pdf_options,
            backend=PyPdfiumDocumentBackend,
        )
    }
    converter = DocumentConverter(format_options=format_options)
    result = converter.convert(pdf_path)
    document = getattr(result, "document", result)

    # Iterate through all text items and collect text
    text_parts = []
    if hasattr(document, "iterate_items"):
        for item, _level in document.iterate_items(with_groups=False):
            if isinstance(item, TextItem):
                text_parts.append(item.text)

    return "\n".join(text_parts)


def _extract_text_with_pdfplumber(pdf_path: str) -> str:
    """
    Extract text from PDF using pdfplumber (standard PDF library).

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text
    """
    import pdfplumber

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    return "\n".join(text_parts)


def _extract_text_with_pypdf2(pdf_path: str) -> str:
    """
    Extract text from PDF using PyPDF2 (basic PDF library).

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text
    """
    from PyPDF2 import PdfReader

    text_parts = []
    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    return "\n".join(text_parts)


def _estimate_scanned_pdf(text: str) -> bool:
    """
    Heuristic to detect if a PDF appears to be scanned (low text quality).

    Checks for:
    - Very short text relative to page count
    - Excessive whitespace/gibberish
    - Missing common financial keywords

    Args:
        text: Extracted text from PDF

    Returns:
        True if PDF appears scanned/OCR'd, False otherwise
    """
    if not text or len(text.strip()) < 100:
        return True

    # Check for gibberish patterns (lots of single letters, odd characters)
    lines = text.split("\n")
    odd_lines = sum(1 for line in lines if len(line) < 3 and line.strip())
    if odd_lines > len(lines) * 0.3:
        return True

    return False


def _apply_ocrmypdf(pdf_path: str) -> str:
    """
    Apply OCRmyPDF to a scanned PDF to add text layer.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Path to OCR'd PDF (same as input if OCRmyPDF not available or fails)
    """
    if not _has_library("ocrmypdf"):
        logger.warning("ocrmypdf not installed; cannot process scanned PDFs")
        return pdf_path

    import ocrmypdf

    # Create temporary file for OCR output
    temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(temp_fd)

    try:
        ocrmypdf.ocr(
            pdf_path,
            temp_path,
            deskew=False,
            rotate_pages=True,
            skip_text=True,  # Don't re-OCR already readable pages
            optimize=1,
            progress_bar=False,
            language=["eng"],
            invalidate_digital_signatures=True,
        )
        return temp_path
    except Exception as e:
        logger.error(f"OCRmyPDF failed: {e}")
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        return pdf_path


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF with intelligent fallback strategy.

    Try order:
    1. Docling (if available) - best for complex layouts
    2. pdfplumber (if available) - good general-purpose
    3. PyPDF2 - basic fallback
    4. If extracted text looks scanned, apply OCRmyPDF and retry

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text string

    Raises:
        FileNotFoundError: If PDF file doesn't exist
        Exception: If all extraction methods fail
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    text = None
    extraction_method = None

    # Try Docling first
    if _has_library("docling"):
        try:
            logger.debug(f"Attempting Docling extraction for {pdf_path}")
            text = _extract_text_with_docling(pdf_path)
            extraction_method = "docling"
            logger.info(f"Successfully extracted text using Docling ({len(text)} chars)")
        except Exception as e:
            logger.debug(f"Docling extraction failed: {e}")

    # Try pdfplumber
    if text is None and _has_library("pdfplumber"):
        try:
            logger.debug(f"Attempting pdfplumber extraction for {pdf_path}")
            text = _extract_text_with_pdfplumber(pdf_path)
            extraction_method = "pdfplumber"
            logger.info(f"Successfully extracted text using pdfplumber ({len(text)} chars)")
        except Exception as e:
            logger.debug(f"pdfplumber extraction failed: {e}")

    # Try PyPDF2
    if text is None and _has_library("PyPDF2"):
        try:
            logger.debug(f"Attempting PyPDF2 extraction for {pdf_path}")
            text = _extract_text_with_pypdf2(pdf_path)
            extraction_method = "pypdf2"
            logger.info(f"Successfully extracted text using PyPDF2 ({len(text)} chars)")
        except Exception as e:
            logger.debug(f"PyPDF2 extraction failed: {e}")

    # All extraction methods failed
    if text is None:
        raise Exception(
            "All PDF text extraction methods failed. "
            "Install one of: docling, pdfplumber, or PyPDF2"
        )

    # Check if text looks scanned and apply OCR if needed
    if _estimate_scanned_pdf(text):
        logger.info("PDF appears to be scanned; applying OCRmyPDF")
        ocr_pdf = _apply_ocrmypdf(pdf_path)
        if ocr_pdf != pdf_path:
            try:
                # Try extraction again on OCR'd PDF
                if _has_library("pdfplumber"):
                    ocr_text = _extract_text_with_pdfplumber(ocr_pdf)
                elif _has_library("PyPDF2"):
                    ocr_text = _extract_text_with_pypdf2(ocr_pdf)
                else:
                    ocr_text = None

                if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    extraction_method = f"{extraction_method}_+ocr"
                    logger.info(f"OCR improved text extraction ({len(text)} chars)")
            finally:
                # Clean up OCR temp file
                try:
                    os.unlink(ocr_pdf)
                except Exception:
                    pass

    logger.debug(f"Text extraction completed via {extraction_method}")
    return text


def _extract_tables_with_docling(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract tables from PDF using Docling.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of tables, each as a dict with keys: columns, rows, caption
    """
    from docling.document_converter import DocumentConverter, FormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    import pandas as pd

    pdf_options = PdfPipelineOptions(
        do_ocr=False,
        force_backend_text=True,
        do_table_structure=True,
    )
    format_options = {
        InputFormat.PDF: FormatOption(
            pipeline_cls=StandardPdfPipeline,
            pipeline_options=pdf_options,
            backend=PyPdfiumDocumentBackend,
        )
    }
    converter = DocumentConverter(format_options=format_options)
    result = converter.convert(pdf_path)
    document = getattr(result, "document", result)

    tables = []
    table_list = getattr(document, "tables", None) or []

    for table in table_list:
        try:
            df = table.export_to_dataframe()
            caption = getattr(table, "caption", None) or getattr(table, "label", None) or ""

            tables.append({
                "columns": [str(c) for c in df.columns],
                "rows": [
                    [str(v) if pd.notna(v) else "" for v in row.values]
                    for _, row in df.iterrows()
                ],
                "caption": str(caption).strip() if caption else "",
            })
        except Exception as e:
            logger.warning(f"Failed to export table: {e}")
            continue

    return tables


def _extract_tables_with_pdfplumber(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract tables from PDF using pdfplumber.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of tables, each as a dict with keys: columns, rows, caption
    """
    import pdfplumber

    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            try:
                page_tables = page.extract_tables()
                if not page_tables:
                    continue

                for table_data in page_tables:
                    if not table_data:
                        continue

                    # First row is assumed to be headers
                    if len(table_data) > 0:
                        columns = [str(c) for c in table_data[0]]
                        rows = [[str(c) for c in row] for row in table_data[1:]]
                    else:
                        columns = []
                        rows = []

                    tables.append({
                        "columns": columns,
                        "rows": rows,
                        "caption": f"Page {page_num}",
                    })
            except Exception as e:
                logger.warning(f"Failed to extract table from page {page_num}: {e}")
                continue

    return tables


def extract_tables_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract structured tables from PDF with intelligent fallback.

    Try order:
    1. Docling (if available) - better table structure understanding
    2. pdfplumber (if available) - standard table extraction

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of tables, each with structure:
        {
            "columns": ["col1", "col2", ...],
            "rows": [["val1", "val2", ...], ...],
            "caption": "table title or page reference"
        }
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    tables = []
    extraction_method = None

    # Try Docling first
    if _has_library("docling"):
        try:
            logger.debug(f"Attempting Docling table extraction for {pdf_path}")
            tables = _extract_tables_with_docling(pdf_path)
            extraction_method = "docling"
            logger.info(f"Extracted {len(tables)} tables using Docling")
        except Exception as e:
            logger.debug(f"Docling table extraction failed: {e}")

    # Try pdfplumber
    if not tables and _has_library("pdfplumber"):
        try:
            logger.debug(f"Attempting pdfplumber table extraction for {pdf_path}")
            tables = _extract_tables_with_pdfplumber(pdf_path)
            extraction_method = "pdfplumber"
            logger.info(f"Extracted {len(tables)} tables using pdfplumber")
        except Exception as e:
            logger.debug(f"pdfplumber table extraction failed: {e}")

    if not tables:
        logger.info("No tables found in PDF")

    logger.debug(f"Table extraction completed via {extraction_method}")
    return tables
