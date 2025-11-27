"""
S&P 500 Earnings Hidden Text Scanner

A Python-based system for detecting hidden or AI-targeted text in:
- SEC EDGAR 8-K earnings filings
- Company investor relations websites

Modules:
- config: Configuration settings
- edgar_scraper: SEC EDGAR 8-K scraper
- ir_crawler: Investor relations website crawler
- hidden_detector: Hidden text and prompt detection
- main_pipeline: Pipeline orchestrator
"""

__version__ = "1.0.0"
__author__ = "Research Team"

from .config import (
    SP500_FIRMS_CSV,
    EDGAR_OUTPUT_CSV,
    IR_OUTPUT_CSV,
    FILING_START_DATE,
    FILING_END_DATE,
)
from .hidden_detector import analyze_page, analyze_text_only
from .edgar_scraper import EdgarScraper, scrape_firm
from .ir_crawler import IRCrawler, crawl_firm_ir
from .main_pipeline import Pipeline, run_pipeline

__all__ = [
    "analyze_page",
    "analyze_text_only",
    "EdgarScraper",
    "scrape_firm",
    "IRCrawler",
    "crawl_firm_ir",
    "Pipeline",
    "run_pipeline",
    "SP500_FIRMS_CSV",
    "EDGAR_OUTPUT_CSV",
    "IR_OUTPUT_CSV",
    "FILING_START_DATE",
    "FILING_END_DATE",
]
