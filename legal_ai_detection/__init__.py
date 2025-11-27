"""
Legal AI Detection Engine

A comprehensive tool for detecting AI-targeted manipulation
in legal settlement websites.
"""

__version__ = "1.0.0"
__author__ = "Research Project"

from .hidden_detector import (
    HiddenContentDetector,
    AnalysisResult,
    DetectionResult,
    HiddenBlock,
    analyze_html_file,
    analyze_html_string
)

from .legal_scraper import (
    LegalSiteScraper,
    ScrapedPage
)

from .main_pipeline import (
    LegalAIDetectionPipeline
)

__all__ = [
    'HiddenContentDetector',
    'AnalysisResult',
    'DetectionResult',
    'HiddenBlock',
    'analyze_html_file',
    'analyze_html_string',
    'LegalSiteScraper',
    'ScrapedPage',
    'LegalAIDetectionPipeline'
]
