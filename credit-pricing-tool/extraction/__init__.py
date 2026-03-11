"""
Financial data extraction package.

Provides utilities for extracting financial data from PDF financial statements.
Includes PDF text/table extraction, AI-powered field mapping, and sector classification.
"""

from extraction.pdf_extractor import extract_text_from_pdf, extract_tables_from_pdf
from extraction.financial_mapper import (
    map_financials_with_ai,
    map_financials_heuristic,
)
from extraction.sector_classifier import (
    classify_sector_with_ai,
    classify_sector_heuristic,
)

__all__ = [
    "extract_text_from_pdf",
    "extract_tables_from_pdf",
    "map_financials_with_ai",
    "map_financials_heuristic",
    "classify_sector_with_ai",
    "classify_sector_heuristic",
]
