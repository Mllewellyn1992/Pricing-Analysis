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
import gc
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


def _find_label_cell(row_data, year_cols):
    """Find the label cell index (first non-year, non-numeric cell). Returns index or None."""
    for ci, cell in enumerate(row_data):
        if ci in year_cols:
            continue
        if cell and str(cell).strip() and not _is_numeric_str(cell):
            return ci
    return None


def _classify_year_columns(row_data, year_cols):
    """Split year columns into empty and filled lists. Returns (empty, filled)."""
    empty = []
    filled = []
    for ci, yr in sorted(year_cols.items(), key=lambda x: x[1]):
        val = row_data[ci] if ci < len(row_data) else ""
        if not val or not str(val).strip():
            empty.append((ci, yr))
        else:
            filled.append((ci, yr))
    return empty, filled


def _extract_unmatched_numbers(label, filled_year_cols, row_data):
    """Extract real financial numbers from label that aren't already in filled columns."""
    embedded_nums = _NUMBER_PATTERN.findall(label)
    real_nums = []
    for num_str in embedded_nums:
        cleaned = re.sub(r"[$£€,\s]", "", num_str)
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = cleaned[1:-1]
        try:
            if abs(float(cleaned)) >= 100:
                real_nums.append(num_str)
        except ValueError:
            pass

    filled_vals = {str(row_data[ci]).strip() for ci, _ in filled_year_cols if ci < len(row_data)}
    return [n for n in real_nums if n.strip() not in filled_vals]


def _assign_numbers_to_row(row_data, label_ci, label, unmatched_nums, sorted_empty):
    """Assign unmatched numbers to empty year columns and clean the label. Returns (new_row, repaired)."""
    new_row = list(row_data)
    repaired = False

    can_assign = (len(unmatched_nums) == len(sorted_empty) or
                  (len(unmatched_nums) == 1 and len(sorted_empty) == 1))

    if can_assign:
        for (ci, _yr), num_str in zip(sorted_empty, unmatched_nums):
            while len(new_row) <= ci:
                new_row.append("")
            new_row[ci] = num_str
        clean_label = label
        for num_str in unmatched_nums:
            clean_label = clean_label.replace(num_str, "", 1)
        new_row[label_ci] = re.sub(r"\s+", " ", clean_label).strip()
        repaired = True

    return new_row, repaired


def repair_label_merge(columns, rows):
    """Fix the label-merge artifact: values embedded in the label cell.

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

        label_ci = _find_label_cell(row_data, year_cols)
        if label_ci is None:
            repaired_rows.append(row_data)
            continue

        label = str(row_data[label_ci])
        empty_year_cols, filled_year_cols = _classify_year_columns(row_data, year_cols)

        if not empty_year_cols:
            repaired_rows.append(row_data)
            continue

        unmatched_nums = _extract_unmatched_numbers(label, filled_year_cols, row_data)
        if not unmatched_nums or len(unmatched_nums) > len(empty_year_cols):
            repaired_rows.append(row_data)
            continue

        sorted_empty = sorted(empty_year_cols, key=lambda x: x[1])
        new_row, was_repaired = _assign_numbers_to_row(
            row_data, label_ci, label, unmatched_nums, sorted_empty)
        if was_repaired:
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

# Page-level quality thresholds
_CID_THRESHOLD = 10          # More than this many (cid: refs = garbled page
_MIN_PAGE_CHARS = 30         # Fewer chars than this = empty/image page
_MULTICOLUMN_RATIO = 0.25    # If >25% of lines are duplicated headers, likely multi-column

# Memory management constants
_DEFAULT_DPI = 150            # Reduced from 300 — still good for OCR, uses ~75% less RAM
_MAX_OCR_PAGES = 20           # Never OCR more than this many pages (prevent OOM)
_MAX_PDF_PAGES = 80           # Skip extraction entirely for very large PDFs


def _page_is_garbled(text: str) -> bool:
    """Check if page text is garbled (CID-encoded fonts or mostly non-printable)."""
    if not text or len(text.strip()) < _MIN_PAGE_CHARS:
        return True
    cid_count = text.count("(cid:")
    if cid_count > _CID_THRESHOLD:
        return True
    # Check ratio of printable alphanumeric to total chars
    alpha_chars = sum(1 for c in text if c.isalnum() or c in " .,;:$%()\n-")
    if len(text) > 0 and alpha_chars / len(text) < 0.5:
        return True
    return False


def _page_is_multicolumn(text: str) -> bool:
    """Detect multi-column layout artifacts from pdfplumber extraction.

    Common signs:
    - Header text repeated/mirrored (e.g. "BFG ANNUAL REPORT 2024/ ... BFG ANNUAL REPORT 2024/")
    - Two sets of column headers on one page (e.g. two "2024  2023" blocks)
    - Lines with interleaved data from two different statements
    """
    if not text or len(text) < 200:
        return False

    lines = text.split("\n")
    if len(lines) < 5:
        return False

    # Check for duplicated header patterns in first few lines
    # e.g. "BFG ANNUAL REPORT 2024/ CONSOLIDATED ... BFG ANNUAL REPORT 2024/ CONSOLIDATED"
    for line in lines[:5]:
        # Find if same substantial phrase appears twice in a line
        words = line.split()
        if len(words) >= 10:
            half = len(words) // 2
            first_half = " ".join(words[:half])
            second_half = " ".join(words[half:])
            # Check if they share significant overlap
            first_words = set(first_half.lower().split())
            second_words = set(second_half.lower().split())
            if len(first_words) >= 4 and len(first_words & second_words) / len(first_words) > 0.5:
                return True

    # Check for two sets of year column headers (e.g. "2024  2023" appearing twice)
    year_header_count = 0
    for line in lines[:15]:
        years = re.findall(r"\b20\d{2}\b", line)
        if len(years) >= 2:
            year_header_count += 1
    if year_header_count >= 2:
        return True

    return False


# Keywords indicating a page contains primary financial statements (not notes)
_FINANCIAL_STATEMENT_KEYWORDS = [
    "statement of comprehensive income",
    "statement of financial position",
    "statement of cash flows",
    "statement of changes in equity",
    "balance sheet",
    "profit and loss",
    "profit or loss",
]


def _page_has_financial_statements(text: str) -> bool:
    """Check if page contains a primary financial statement (not just notes).

    We only column-OCR pages with actual financial statements since those
    have critical numeric data that gets garbled by column merging. Notes
    pages are still usable from pdfplumber even with multi-column artifacts.
    """
    text_lower = text.lower()
    return any(kw in text_lower for kw in _FINANCIAL_STATEMENT_KEYWORDS)


def _ocr_single_page(pdf_path: str, page_num: int, dpi: int = _DEFAULT_DPI) -> str:
    """OCR a single page from the PDF. page_num is 1-indexed."""
    from pdf2image import convert_from_path
    import pytesseract

    try:
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            grayscale=True,
            thread_count=1,
            fmt="jpeg",
            first_page=page_num,
            last_page=page_num,
        )
        if not images:
            return ""
        try:
            text = pytesseract.image_to_string(
                images[0], lang="eng", config="--psm 6"
            )
            return text or ""
        finally:
            images[0].close()
            del images
            gc.collect()
    except Exception as e:
        logger.warning(f"OCR failed on page {page_num}: {e}")
        return ""


def _ocr_page_columns(pdf_path: str, page_num: int, dpi: int = _DEFAULT_DPI) -> str:
    """OCR a multi-column page by splitting into left and right halves.

    This handles the common NZ annual report layout where two pages of content
    are rendered side-by-side on a single landscape-oriented page.
    Each half is OCR'd independently to avoid column merging.
    """
    from pdf2image import convert_from_path
    import pytesseract
    from PIL import Image

    try:
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            grayscale=True,
            thread_count=1,
            fmt="jpeg",
            first_page=page_num,
            last_page=page_num,
        )
        if not images:
            return ""

        img = images[0]
        width, height = img.size

        try:
            # Split into left and right halves
            left_img = img.crop((0, 0, width // 2, height))
            right_img = img.crop((width // 2, 0, width, height))

            left_text = pytesseract.image_to_string(
                left_img, lang="eng", config="--psm 6"
            )
            right_text = pytesseract.image_to_string(
                right_img, lang="eng", config="--psm 6"
            )

            left_img.close()
            right_img.close()

            # Combine with clear separator
            parts = []
            if left_text and left_text.strip():
                parts.append(left_text.strip())
            if right_text and right_text.strip():
                parts.append(right_text.strip())

            return "\n".join(parts)
        finally:
            img.close()
            del images
            gc.collect()

    except Exception as e:
        logger.warning(f"Column OCR failed on page {page_num}: {e}")
        return ""


def _extract_text_with_pdfplumber(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber (simple, no per-page logic)."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    return "\n".join(text_parts)


def _extract_text_hybrid(pdf_path: str, dpi: int = _DEFAULT_DPI) -> str:
    """Smart per-page hybrid extraction: pdfplumber + targeted OCR.

    For each page:
    1. Try pdfplumber text extraction
    2. If text is garbled (CID fonts) or empty → OCR that page
    3. If text has multi-column artifacts → OCR with column splitting
    4. Otherwise keep pdfplumber text (faster, higher quality for clean PDFs)

    Memory-conscious: limits OCR pages, uses lower DPI, garbage collects.
    """
    import pdfplumber

    has_ocr = _has_library("pytesseract") and _has_library("pdf2image")

    text_parts = []
    ocr_pages = 0
    column_ocr_pages = 0
    pdfplumber_pages = 0

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        logger.info(f"Hybrid extraction: {total_pages} pages, OCR available: {has_ocr}")

        # Cap total pages to prevent OOM on massive PDFs
        pages_to_process = min(total_pages, _MAX_PDF_PAGES)
        if pages_to_process < total_pages:
            logger.warning(f"PDF has {total_pages} pages, limiting to {pages_to_process}")

        for i in range(pages_to_process):
            page = pdf.pages[i]
            page_num = i + 1  # 1-indexed for pdf2image

            try:
                text = page.extract_text() or ""
            except Exception as e:
                logger.warning(f"pdfplumber failed on page {page_num}: {e}")
                text = ""

            # Decision: is this page good enough from pdfplumber?
            if _page_is_garbled(text):
                # Page is empty or garbled — needs OCR
                if has_ocr and (ocr_pages + column_ocr_pages) < _MAX_OCR_PAGES:
                    logger.debug(f"Page {page_num}: garbled/empty, using OCR")
                    ocr_text = _ocr_single_page(pdf_path, page_num, dpi)
                    if ocr_text and ocr_text.strip():
                        text_parts.append(ocr_text)
                        ocr_pages += 1
                    else:
                        logger.debug(f"Page {page_num}: OCR also returned nothing")
                else:
                    # No OCR available or OCR budget exhausted
                    if text.strip():
                        text_parts.append(text)
            elif _page_is_multicolumn(text):
                if has_ocr and _page_has_financial_statements(text) and (ocr_pages + column_ocr_pages) < _MAX_OCR_PAGES:
                    logger.debug(f"Page {page_num}: multi-column financial statement, using column OCR")
                    col_text = _ocr_page_columns(pdf_path, page_num, dpi)
                    if col_text and col_text.strip():
                        text_parts.append(col_text)
                        column_ocr_pages += 1
                    else:
                        text_parts.append(text)
                        pdfplumber_pages += 1
                else:
                    text_parts.append(text)
                    pdfplumber_pages += 1
            else:
                # Page is clean — use pdfplumber text
                if text.strip():
                    text_parts.append(text)
                    pdfplumber_pages += 1

            # Periodic gc for long PDFs
            if page_num % 20 == 0:
                gc.collect()

    logger.info(
        f"Hybrid extraction complete: {pdfplumber_pages} pdfplumber, "
        f"{ocr_pages} OCR, {column_ocr_pages} column-OCR pages"
    )
    return "\n".join(text_parts)


def _extract_text_with_ocr(pdf_path: str, dpi: int = _DEFAULT_DPI) -> str:
    """
    Extract text from PDF using OCR, PAGE BY PAGE to limit memory.

    Converts one page at a time (not all at once) to avoid OOM on large PDFs.
    Limits to _MAX_OCR_PAGES pages max.

    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for page rendering (lower = less RAM)
    """
    import pytesseract

    logger.info(f"Running full OCR on {pdf_path} at {dpi} DPI (page-by-page, max {_MAX_OCR_PAGES} pages)")

    # Get page count first
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception:
        total_pages = _MAX_OCR_PAGES  # Guess if we can't count

    pages_to_ocr = min(total_pages, _MAX_OCR_PAGES)
    text_parts = []

    for page_num in range(1, pages_to_ocr + 1):
        try:
            page_text = _ocr_single_page(pdf_path, page_num, dpi)
            if page_text and page_text.strip():
                text_parts.append(page_text)
                logger.debug(f"OCR page {page_num}: {len(page_text)} chars")
        except Exception as e:
            logger.warning(f"OCR failed on page {page_num}: {e}")

    logger.info(f"OCR extracted {sum(len(t) for t in text_parts)} total chars from {pages_to_ocr} pages")
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
    Extract text from PDF with intelligent per-page fallback strategy.

    Priority:
    1. Hybrid extraction (pdfplumber per-page + targeted OCR for bad pages)
       - Uses pdfplumber for clean pages (fast, high quality)
       - OCRs garbled/empty pages (CID fonts, image-based pages)
       - Column-splits and OCRs multi-column layout pages
    2. Full OCR (for fully scanned/image PDFs where hybrid still fails)
    3. Plain pdfplumber (if OCR is not available)
    4. PyPDF2 (last resort)
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    best_text = None
    best_score = 0.0
    best_method = "none"

    # Try hybrid extraction first (pdfplumber + targeted OCR)
    if _has_library("pdfplumber"):
        try:
            logger.debug(f"Attempting hybrid extraction for {pdf_path}")
            text = _extract_text_hybrid(pdf_path)
            score = _text_quality_score(text)
            logger.info(f"hybrid: {len(text)} chars, quality={score:.2f}")

            if score > best_score:
                best_text = text
                best_score = score
                best_method = "hybrid"

            # If quality is high enough, we're done
            if score >= 0.6:
                logger.info(f"Hybrid quality sufficient ({score:.2f})")
                return best_text

        except Exception as e:
            logger.warning(f"Hybrid extraction failed: {e}")

    # Try full OCR if hybrid didn't produce good results
    if best_score < 0.5 and _has_library("pytesseract") and _has_library("pdf2image"):
        try:
            logger.info("Hybrid quality insufficient, attempting full OCR extraction")
            text = _extract_text_with_ocr(pdf_path)
            score = _text_quality_score(text)
            logger.info(f"Full OCR: {len(text)} chars, quality={score:.2f}")

            if score > best_score:
                best_text = text
                best_score = score
                best_method = "full_ocr"

        except Exception as e:
            logger.warning(f"Full OCR extraction failed: {e}")

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
