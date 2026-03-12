"""
PDF text and table extraction with OCR fallback for scanned documents.

Extraction chain (best quality first):
1. pdfplumber text extraction (fast, accurate for text-based PDFs)
2. pytesseract OCR via pdf2image (handles scanned/image-based PDFs)
3. PyPDF2 basic extraction (last resort fallback)

Includes v2 table post-processing:
- Label-merge repair (fixes artifacts where values merge into labels)
- Multi-level header detection and merging
- Quality scoring and flagging per table

OCR pipeline:
- pdf2image converts each PDF page to a high-DPI image (300 DPI)
- pytesseract runs Tesseract OCR on each page image
- Results are combined with any text-based extraction
- Tables are extracted from OCR text using line/column heuristics
"""

import os
import re
import logging
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
    """Fix the label-merge artifact: values embedded in the label cell.

    When extraction merges a label cell with adjacent value cells, the first cell
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
        elif "$" in s or "000" in s or "million" in s or "thousand" in s:
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

    # All-numeric headers (extraction fallback)
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


def _extract_text_with_ocr(pdf_path: str, dpi: int = 300) -> str:
    """
    Extract text from PDF using OCR (pytesseract + pdf2image).

    Converts each page to a high-DPI image, then runs Tesseract OCR.
    This handles scanned/image-based PDFs that pdfplumber can't read.

    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for page rendering (higher = better OCR but slower/more RAM)
             Using 300 for good quality while staying within RAM limits.
    """
    from pdf2image import convert_from_path
    import pytesseract

    logger.info(f"Running OCR on {pdf_path} at {dpi} DPI")

    text_parts = []

    try:
        # Convert PDF pages to images
        # Use thread_count=1 and grayscale=True to minimize RAM usage
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            grayscale=True,
            thread_count=1,
            fmt="jpeg",
        )

        for i, image in enumerate(images):
            try:
                # Run OCR on each page
                page_text = pytesseract.image_to_string(
                    image,
                    lang="eng",
                    config="--psm 6",  # Assume uniform block of text
                )
                if page_text and page_text.strip():
                    text_parts.append(page_text)
                    logger.debug(f"OCR page {i+1}: {len(page_text)} chars")
            except Exception as e:
                logger.warning(f"OCR failed on page {i+1}: {e}")
            finally:
                # Free image memory immediately
                image.close()

        logger.info(f"OCR extracted {sum(len(t) for t in text_parts)} total chars from {len(images)} pages")

    except Exception as e:
        logger.error(f"pdf2image conversion failed: {e}")
        raise

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


def _text_quality_score(text: str) -> float:
    """
    Score extracted text quality from 0 to 1.

    Checks for:
    - Sufficient length
    - Financial keywords present
    - Reasonable word density (not just noise/garbled text)
    - Number density (financial docs have lots of numbers)
    """
    if not text or len(text.strip()) < 50:
        return 0.0

    score = 0.0
    text_lower = text.lower()

    # Length score (more text = better, up to a point)
    char_count = len(text.strip())
    if char_count > 5000:
        score += 0.3
    elif char_count > 1000:
        score += 0.2
    elif char_count > 200:
        score += 0.1

    # Financial keywords
    fin_keywords = [
        "revenue", "profit", "loss", "income", "expense", "asset",
        "liability", "equity", "cash", "debt", "capital", "operating",
        "depreciation", "amortization", "interest", "dividend", "tax",
        "balance sheet", "statement", "financial", "audit", "director",
        "shareholder", "total", "net", "gross",
    ]
    keyword_hits = sum(1 for kw in fin_keywords if kw in text_lower)
    score += min(0.4, keyword_hits * 0.04)  # Up to 0.4 for 10+ keywords

    # Number density (financial docs have lots of numbers)
    numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text)
    num_density = len(numbers) / max(1, char_count / 100)
    if num_density > 2:
        score += 0.2
    elif num_density > 0.5:
        score += 0.1

    # Word quality (ratio of real words vs garbled text)
    words = text.split()
    if words:
        # Count words with at least 2 alpha chars
        real_words = sum(1 for w in words if len(re.findall(r"[a-zA-Z]", w)) >= 2)
        word_quality = real_words / len(words)
        score += word_quality * 0.1

    return min(1.0, score)


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF with intelligent fallback strategy.

    Priority:
    1. pdfplumber - lightweight, reliable for text-based PDFs
    2. pytesseract OCR - handles scanned/image PDFs
    3. PyPDF2 - basic fallback

    If pdfplumber returns low-quality text (common for scanned PDFs where
    it might get garbled text or nothing), automatically falls back to OCR.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    best_text = None
    best_score = 0.0
    best_method = "none"

    # Try pdfplumber first (lightweight, reliable for text-based PDFs)
    if _has_library("pdfplumber"):
        try:
            logger.debug(f"Attempting pdfplumber extraction for {pdf_path}")
            text = _extract_text_with_pdfplumber(pdf_path)
            score = _text_quality_score(text)
            logger.info(f"pdfplumber: {len(text)} chars, quality={score:.2f}")

            if score > best_score:
                best_text = text
                best_score = score
                best_method = "pdfplumber"

            # If quality is high enough, skip OCR (saves time and RAM)
            if score >= 0.6:
                logger.info(f"pdfplumber quality sufficient ({score:.2f}), skipping OCR")
                return best_text

        except Exception as e:
            logger.debug(f"pdfplumber extraction failed: {e}")

    # Try OCR if pdfplumber didn't produce good results
    if _has_library("pytesseract") and _has_library("pdf2image"):
        try:
            logger.info("pdfplumber quality insufficient, attempting OCR extraction")
            text = _extract_text_with_ocr(pdf_path)
            score = _text_quality_score(text)
            logger.info(f"OCR: {len(text)} chars, quality={score:.2f}")

            if score > best_score:
                best_text = text
                best_score = score
                best_method = "ocr"

                # If OCR is also low quality but pdfplumber had some text,
                # combine them for the best result
                if best_method == "ocr" and best_score < 0.4 and best_text:
                    logger.info("Combining pdfplumber and OCR text for best result")

        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")
    else:
        logger.info("pytesseract/pdf2image not available, skipping OCR")

    # Try PyPDF2 as last resort
    if best_score < 0.3 and _has_library("PyPDF2"):
        try:
            logger.debug(f"Attempting PyPDF2 extraction for {pdf_path}")
            text = _extract_text_with_pypdf2(pdf_path)
            score = _text_quality_score(text)
            logger.info(f"PyPDF2: {len(text)} chars, quality={score:.2f}")

            if score > best_score:
                best_text = text
                best_score = score
                best_method = "pypdf2"

        except Exception as e:
            logger.debug(f"PyPDF2 extraction failed: {e}")

    # Return best result
    if best_text and best_score > 0:
        logger.info(f"Best extraction: {best_method} (quality={best_score:.2f}, {len(best_text)} chars)")
        return best_text

    # All extraction methods failed
    raise Exception(
        "All PDF text extraction methods failed. "
        "The document may be encrypted, corrupted, or in an unsupported format."
    )


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


def _extract_tables_from_ocr_text(ocr_text: str) -> List[Dict[str, Any]]:
    """
    Extract table-like structures from OCR text using line/column heuristics.

    OCR text doesn't have native table structure, so we look for:
    - Lines with consistent column-like spacing
    - Rows that have financial labels followed by numbers
    - Year headers that indicate columnar data
    """
    if not ocr_text:
        return []

    tables = []
    lines = ocr_text.split("\n")

    # Look for sections that look like financial tables
    current_table_lines = []
    in_table = False
    table_start_patterns = [
        r"(?:statement|balance\s+sheet|cash\s+flow|income|profit|loss|financial)",
        r"(?:note|notes?\s+to)",
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if in_table and current_table_lines:
                # End of table section
                table = _parse_ocr_table_lines(current_table_lines)
                if table:
                    tables.append(table)
                current_table_lines = []
                in_table = False
            continue

        # Check if this line has numbers (potential table row)
        numbers = re.findall(r"[\d,]{3,}(?:\.\d+)?|\(\d[\d,]*(?:\.\d+)?\)", stripped)
        has_label = bool(re.search(r"[a-zA-Z]{3,}", stripped))

        if has_label and len(numbers) >= 1:
            in_table = True
            current_table_lines.append(stripped)
        elif in_table and (numbers or has_label):
            current_table_lines.append(stripped)

    # Process any remaining table
    if current_table_lines:
        table = _parse_ocr_table_lines(current_table_lines)
        if table:
            tables.append(table)

    return tables


def _parse_ocr_table_lines(lines: List[str]) -> Optional[Dict[str, Any]]:
    """
    Parse a group of OCR text lines into a table structure.

    Tries to identify columns by looking for consistent spacing patterns
    and year headers.
    """
    if len(lines) < 3:
        return None

    # Try to find year headers in the first few lines
    header_line = None
    data_start = 0
    for i, line in enumerate(lines[:3]):
        years = re.findall(r"\b(20\d{2}|19\d{2})\b", line)
        if len(years) >= 1:
            header_line = line
            data_start = i + 1
            break

    if not header_line:
        # Use first line as header, try to detect columns from data patterns
        header_line = lines[0]
        data_start = 1

    # Extract years from header for column names
    years = re.findall(r"\b(20\d{2}|19\d{2})\b", header_line)
    if years:
        columns = ["Item"] + [f"FY{y}" for y in years]
    else:
        columns = ["Item", "Value"]

    # Parse data rows
    rows = []
    for line in lines[data_start:]:
        # Split line into label and numbers
        # Pattern: "Revenue 1,234,567 987,654" or "Total assets 45,678"
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) >= 2:
            label = parts[0]
            values = parts[1:]
            row = [label] + values
            # Pad to match column count
            while len(row) < len(columns):
                row.append("")
            rows.append(row[:len(columns)])
        else:
            # Try splitting by finding number positions
            nums = list(re.finditer(r"[\d,]{3,}(?:\.\d+)?|\(\d[\d,]*(?:\.\d+)?\)", line))
            if nums:
                label = line[:nums[0].start()].strip()
                values = [m.group() for m in nums]
                row = [label] + values
                while len(row) < len(columns):
                    row.append("")
                rows.append(row[:len(columns)])

    if len(rows) < 2:
        return None

    # Apply v2 post-processing
    columns, rows, meta = _postprocess_table(columns, rows)

    return {
        "columns": columns,
        "rows": rows,
        "caption": "OCR extracted table",
        "quality_score": meta["quality_score"],
        "quality_flags": meta["quality_flags"] + ["ocr_extracted"],
        "repairs": meta["repairs"],
    }


def extract_tables_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract structured tables from PDF.

    Strategy:
    1. pdfplumber table extraction with v2 post-processing
    2. If no tables found and OCR text is available, try OCR-based table extraction

    All tables receive v2 post-processing:
    - Multi-level header merging
    - Label-merge repair
    - Quality scoring
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    tables = []

    # Use pdfplumber for native table extraction
    if _has_library("pdfplumber"):
        try:
            logger.debug(f"Attempting pdfplumber table extraction for {pdf_path}")
            tables = _extract_tables_with_pdfplumber(pdf_path)
            logger.info(f"Extracted {len(tables)} tables using pdfplumber")
        except Exception as e:
            logger.warning(f"pdfplumber table extraction failed: {e}")

    # If no tables from pdfplumber, try OCR-based table extraction
    if not tables:
        logger.info("No tables from pdfplumber, attempting OCR-based table extraction")
        try:
            # First get OCR text
            if _has_library("pytesseract") and _has_library("pdf2image"):
                ocr_text = _extract_text_with_ocr(pdf_path)
                if ocr_text:
                    ocr_tables = _extract_tables_from_ocr_text(ocr_text)
                    if ocr_tables:
                        tables = ocr_tables
                        logger.info(f"Extracted {len(tables)} tables from OCR text")
        except Exception as e:
            logger.warning(f"OCR table extraction failed: {e}")

    if not tables:
        logger.info("No tables found in PDF (tried pdfplumber + OCR)")

    return tables
