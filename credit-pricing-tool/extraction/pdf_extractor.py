"""
PDF text and table extraction with multiple fallback strategies.

Supports:
- pdfplumber (primary): Lightweight, reliable PDF library
- Docling (optional): Advanced document parsing with layout understanding
- PyPDF2 (fallback): Basic PDF library
- OCRmyPDF → re-extract (fallback): For scanned documents

Includes v2 table post-processing from 02_docling_to_parquet_v2:
- Label-merge repair (fixes Docling artifact where values merge into labels)
- Multi-level header detection and merging
- Quality scoring and flagging per table
"""

import os
import re
import tempfile
import logging
import signal
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Table post-processing patterns (from v2) ────────────────────────────────
_YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
_NUMBER_PATTERN = re.compile(r"\([\d,]{3,}\.?\d*\)|[\d,]{3,}\.?\d*")
_EMBEDDED_NUMBER = re.compile(r"[\s\r\n]+\(?[\d,]{3,}\.?\d*\)?")


def _has_library(module_name: str) -> bool:
    """Check if a library is available without raising ImportError."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# TABLE POST-PROCESSING (from v2 extraction code)
# ══════════════════════════════════════════════════════════════════════════════


def _is_numeric_str(s):
    """Check if string looks like a financial number (with commas, parens, $)."""
    s = str(s).strip()
    s = re.sub(r"[$£€,\s]", "", s)
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    try:
        float(s)
        return True
    except ValueError:
        return False


def _detect_year_columns(columns):
    """Return dict {col_index: year_int} for columns that look like year headers."""
    year_cols = {}
    for ci, col in enumerate(columns):
        m = _YEAR_PATTERN.search(str(col))
        if m:
            year_cols[ci] = int(m.group(1))
    return year_cols


def repair_label_merge(columns, rows):
    """Fix the Docling label-merge artifact: values embedded in the label cell.

    When Docling merges a label cell with adjacent value cells, the first cell
    looks like "Revenue 1,371,343 1,726,686" while the year columns are empty.

    Returns (columns, repaired_rows, repair_count).
    """
    year_cols = _detect_year_columns(columns)
    if not year_cols:
        return columns, rows, 0

    repair_count = 0
    repaired_rows = []

    for row_data in rows:
        if not row_data:
            repaired_rows.append(row_data)
            continue

        # Find the label cell (first non-year, non-numeric cell)
        label_ci = None
        for ci, cell in enumerate(row_data):
            if ci in year_cols:
                continue
            if cell and str(cell).strip() and not _is_numeric_str(cell):
                label_ci = ci
                break

        if label_ci is None:
            repaired_rows.append(row_data)
            continue

        label = str(row_data[label_ci])

        # Check if year columns are empty for this row
        empty_year_cols = []
        filled_year_cols = []
        for ci, yr in sorted(year_cols.items(), key=lambda x: x[1]):
            val = row_data[ci] if ci < len(row_data) else ""
            if not val or not str(val).strip():
                empty_year_cols.append((ci, yr))
            else:
                filled_year_cols.append((ci, yr))

        if not empty_year_cols:
            repaired_rows.append(row_data)
            continue

        # Extract embedded numbers from label
        embedded_nums = _NUMBER_PATTERN.findall(label)
        # Filter out small numbers that are likely note references (< 100)
        real_nums = []
        for num_str in embedded_nums:
            cleaned = re.sub(r"[$£€,\s]", "", num_str)
            if cleaned.startswith("(") and cleaned.endswith(")"):
                cleaned = cleaned[1:-1]
            try:
                val = float(cleaned)
                if abs(val) >= 100:
                    real_nums.append(num_str)
            except ValueError:
                pass

        # Filter out numbers already present in filled columns
        filled_vals = set()
        for ci, yr in filled_year_cols:
            v = str(row_data[ci]).strip()
            if v:
                filled_vals.add(v)

        unmatched_nums = [n for n in real_nums if n.strip() not in filled_vals]

        if not unmatched_nums or len(unmatched_nums) > len(empty_year_cols):
            repaired_rows.append(row_data)
            continue

        # Assign: numbers to empty year columns (sorted by year)
        new_row = list(row_data)
        sorted_empty = sorted(empty_year_cols, key=lambda x: x[1])
        if len(unmatched_nums) == len(sorted_empty):
            for (ci, yr), num_str in zip(sorted_empty, unmatched_nums):
                if ci < len(new_row):
                    new_row[ci] = num_str
                else:
                    while len(new_row) <= ci:
                        new_row.append("")
                    new_row[ci] = num_str
            # Clean the label
            clean_label = label
            for num_str in unmatched_nums:
                clean_label = clean_label.replace(num_str, "", 1)
            clean_label = re.sub(r"\s+", " ", clean_label).strip()
            new_row[label_ci] = clean_label
            repair_count += 1
        elif len(unmatched_nums) == 1 and len(sorted_empty) == 1:
            ci, yr = sorted_empty[0]
            if ci < len(new_row):
                new_row[ci] = unmatched_nums[0]
            clean_label = label.replace(unmatched_nums[0], "", 1)
            clean_label = re.sub(r"\s+", " ", clean_label).strip()
            new_row[label_ci] = clean_label
            repair_count += 1

        repaired_rows.append(new_row)

    return columns, repaired_rows, repair_count


def merge_multi_level_headers(columns, rows):
    """Detect and merge multi-level column headers.

    NZ financial statements often have two-row headers like:
        Row 0: | Group      | Group      | Parent     | Parent     |
        Row 1: | 2024 $000  | 2023 $000  | 2024 $000  | 2023 $000  |

    Returns (new_columns, remaining_rows, was_merged).
    """
    if not rows or not rows[0]:
        return columns, rows, False

    first_row = rows[0]
    year_count = 0
    text_count = 0
    number_count = 0
    consolidation_words = {
        "group", "consolidated", "parent", "company", "standalone", "economic entity"
    }

    for cell in first_row:
        s = str(cell).strip().lower()
        if not s:
            continue
        if _YEAR_PATTERN.search(s):
            year_count += 1
        elif _is_numeric_str(cell):
            number_count += 1
        elif any(w in s for w in consolidation_words):
            text_count += 1
        elif "$" in s or "000" in s or "million" in s:
            text_count += 1

    is_subheader = (year_count >= 1 or text_count >= 1) and number_count == 0

    if not is_subheader:
        return columns, rows, False

    # Merge column header + first row
    new_columns = []
    for ci, col in enumerate(columns):
        col_str = str(col).strip() if col else ""
        sub_str = str(first_row[ci]).strip() if ci < len(first_row) and first_row[ci] else ""
        if col_str and sub_str and col_str.lower() != sub_str.lower():
            new_columns.append(f"{col_str} {sub_str}")
        elif sub_str:
            new_columns.append(sub_str)
        else:
            new_columns.append(col_str)

    return new_columns, rows[1:], True


def assess_table_quality(columns, rows):
    """Score a table's extraction quality. Returns (score 0-100, list of flag strings)."""
    flags = []
    score = 100

    # Merged years in single column
    for col in columns:
        years = re.findall(r"\b(?:19|20)\d{2}\b", str(col))
        if len(years) >= 2:
            flags.append("merged_years")
            score -= 40
            break

    # Year columns present
    year_cols = _detect_year_columns(columns)
    if not year_cols:
        flags.append("no_year_cols")
        score -= 20

    # Column count
    if len(columns) <= 2:
        flags.append("few_columns")
        score -= 15

    # Row count
    if len(rows) <= 2:
        flags.append("few_rows")
        score -= 10

    # All-numeric headers (Docling fallback)
    if all(str(c).strip().isdigit() or not str(c).strip() for c in columns):
        flags.append("all_numeric_headers")
        score -= 25

    # Financial keywords check
    all_text = " ".join(str(c) for c in columns)
    for row in rows:
        all_text += " " + " ".join(str(v) for v in row)
    fin_keywords = ["revenue", "profit", "loss", "asset", "liability", "equity",
                    "income", "expense", "cash", "debt", "capital", "operating"]
    if not any(kw in all_text.lower() for kw in fin_keywords):
        flags.append("no_financial_keywords")
        score -= 15

    return max(0, score), flags


def _postprocess_table(columns, rows):
    """Apply v2 post-processing to a table: header merge, label repair, quality scoring."""
    # Step 1: Multi-level header merge
    columns, rows, header_merged = merge_multi_level_headers(columns, rows)

    # Step 2: Label-merge repair
    columns, rows, repair_count = repair_label_merge(columns, rows)

    # Step 3: Quality assessment
    quality_score, quality_flags = assess_table_quality(columns, rows)

    return columns, rows, {
        "header_merged": header_merged,
        "repairs": repair_count,
        "quality_score": quality_score,
        "quality_flags": quality_flags,
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEXT EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════


def _extract_text_with_pdfplumber(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    return "\n".join(text_parts)


def _extract_text_with_docling(pdf_path: str) -> str:
    """Extract text from PDF using Docling (advanced layout understanding).

    NOTE: Docling loads PyTorch models and requires significant memory.
    This may fail on free-tier hosting with limited RAM.
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

    text_parts = []
    if hasattr(document, "iterate_items"):
        for item, _level in document.iterate_items(with_groups=False):
            if isinstance(item, TextItem):
                text_parts.append(item.text)

    return "\n".join(text_parts)


def _extract_text_with_pypdf2(pdf_path: str) -> str:
    """Extract text from PDF using PyPDF2 (basic fallback)."""
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
    """Heuristic to detect if a PDF appears to be scanned (low text quality)."""
    if not text or len(text.strip()) < 100:
        return True

    lines = text.split("\n")
    odd_lines = sum(1 for line in lines if len(line) < 3 and line.strip())
    if odd_lines > len(lines) * 0.3:
        return True

    return False


def _apply_ocrmypdf(pdf_path: str) -> str:
    """Apply OCRmyPDF to a scanned PDF to add text layer."""
    if not _has_library("ocrmypdf"):
        logger.warning("ocrmypdf not installed; cannot process scanned PDFs")
        return pdf_path

    import ocrmypdf

    temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(temp_fd)

    try:
        ocrmypdf.ocr(
            pdf_path,
            temp_path,
            deskew=False,
            rotate_pages=True,
            skip_text=True,
            optimize=1,
            progress_bar=False,
            language=["eng"],
            invalidate_digital_signatures=True,
        )
        return temp_path
    except Exception as e:
        logger.error(f"OCRmyPDF failed: {e}")
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        return pdf_path


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF with intelligent fallback strategy.

    Priority order (changed from v1 to prioritize lightweight libraries):
    1. pdfplumber (if available) - lightweight, reliable
    2. Docling (if available) - better for complex layouts but heavy
    3. PyPDF2 - basic fallback
    4. If text looks scanned, apply OCRmyPDF and retry
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    text = None
    extraction_method = None

    # Try pdfplumber first (lightweight, reliable)
    if _has_library("pdfplumber"):
        try:
            logger.debug(f"Attempting pdfplumber extraction for {pdf_path}")
            text = _extract_text_with_pdfplumber(pdf_path)
            extraction_method = "pdfplumber"
            logger.info(f"Successfully extracted text using pdfplumber ({len(text)} chars)")
        except Exception as e:
            logger.debug(f"pdfplumber extraction failed: {e}")

    # Try Docling if pdfplumber didn't work or text is very short
    if (text is None or len(text.strip()) < 200) and _has_library("docling"):
        try:
            logger.debug(f"Attempting Docling extraction for {pdf_path}")
            docling_text = _extract_text_with_docling(pdf_path)
            if docling_text and (text is None or len(docling_text.strip()) > len(text.strip())):
                text = docling_text
                extraction_method = "docling"
                logger.info(f"Successfully extracted text using Docling ({len(text)} chars)")
        except MemoryError:
            logger.warning("Docling failed: out of memory (likely free-tier hosting)")
        except Exception as e:
            logger.debug(f"Docling extraction failed: {e}")

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
            "Install one of: pdfplumber, docling, or PyPDF2"
        )

    # Check if text looks scanned and apply OCR if needed
    if _estimate_scanned_pdf(text):
        logger.info("PDF appears to be scanned; applying OCRmyPDF")
        ocr_pdf = _apply_ocrmypdf(pdf_path)
        if ocr_pdf != pdf_path:
            try:
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
                try:
                    os.unlink(ocr_pdf)
                except Exception:
                    pass

    logger.debug(f"Text extraction completed via {extraction_method}")
    return text


# ══════════════════════════════════════════════════════════════════════════════
# TABLE EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════


def _extract_tables_with_pdfplumber(pdf_path: str) -> List[Dict[str, Any]]:
    """Extract tables from PDF using pdfplumber."""
    import pdfplumber

    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            try:
                page_tables = page.extract_tables()
                if not page_tables:
                    continue

                for table_data in page_tables:
                    if not table_data or len(table_data) < 2:
                        continue

                    # First row is headers
                    columns = [str(c or "") for c in table_data[0]]
                    rows = [[str(c or "") for c in row] for row in table_data[1:]]

                    # Apply v2 post-processing
                    columns, rows, meta = _postprocess_table(columns, rows)

                    tables.append({
                        "columns": columns,
                        "rows": rows,
                        "caption": f"Page {page_num}",
                        "quality_score": meta["quality_score"],
                        "quality_flags": meta["quality_flags"],
                        "repairs": meta["repairs"],
                    })
            except Exception as e:
                logger.warning(f"Failed to extract table from page {page_num}: {e}")
                continue

    return tables


def _extract_tables_with_docling(pdf_path: str) -> List[Dict[str, Any]]:
    """Extract tables from PDF using Docling."""
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

            columns = [str(c) for c in df.columns]
            rows = [
                [str(v) if pd.notna(v) else "" for v in row.values]
                for _, row in df.iterrows()
            ]

            # Apply v2 post-processing
            columns, rows, meta = _postprocess_table(columns, rows)

            tables.append({
                "columns": columns,
                "rows": rows,
                "caption": str(caption).strip() if caption else "",
                "quality_score": meta["quality_score"],
                "quality_flags": meta["quality_flags"],
                "repairs": meta["repairs"],
            })
        except Exception as e:
            logger.warning(f"Failed to export table: {e}")
            continue

    return tables


def extract_tables_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract structured tables from PDF with intelligent fallback.

    Priority (changed from v1):
    1. pdfplumber (if available) - lightweight, reliable
    2. Docling (if available) - better table structure but heavy

    All tables receive v2 post-processing:
    - Multi-level header merging
    - Label-merge repair
    - Quality scoring
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    tables = []

    # Try pdfplumber first (lightweight)
    if _has_library("pdfplumber"):
        try:
            logger.debug(f"Attempting pdfplumber table extraction for {pdf_path}")
            tables = _extract_tables_with_pdfplumber(pdf_path)
            logger.info(f"Extracted {len(tables)} tables using pdfplumber")
        except Exception as e:
            logger.debug(f"pdfplumber table extraction failed: {e}")

    # Try Docling if pdfplumber found no tables
    if not tables and _has_library("docling"):
        try:
            logger.debug(f"Attempting Docling table extraction for {pdf_path}")
            tables = _extract_tables_with_docling(pdf_path)
            logger.info(f"Extracted {len(tables)} tables using Docling")
        except MemoryError:
            logger.warning("Docling table extraction failed: out of memory")
        except Exception as e:
            logger.debug(f"Docling table extraction failed: {e}")

    if not tables:
        logger.info("No tables found in PDF")

    return tables
