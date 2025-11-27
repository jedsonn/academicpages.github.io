"""
Configuration settings for Legal AI Detection Engine
"""

import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
HTML_CACHE_DIR = DATA_DIR / "html_cache"

# Create directories
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
HTML_CACHE_DIR.mkdir(exist_ok=True)

# Detection thresholds
SUSPICIOUSNESS_THRESHOLDS = {
    "low": 2.0,
    "medium": 5.0,
    "high": 10.0,
    "critical": 15.0
}

# Detection weights
DETECTION_WEIGHTS = {
    "css_hidden": 1.0,
    "position_offscreen": 1.5,
    "zero_width_unicode": 2.0,
    "suspicious_comment": 1.5,
    "metadata_manipulation": 2.5,
    "prompt_injection": 4.0
}

# Zero-width Unicode characters
ZERO_WIDTH_CHARS = [
    '\u200b',  # Zero-width space
    '\u200c',  # Zero-width non-joiner
    '\u200d',  # Zero-width joiner
    '\ufeff',  # Byte order mark
    '\u2060',  # Word joiner
    '\u180e',  # Mongolian vowel separator
    '\u00ad',  # Soft hyphen
]

# Prompt injection patterns (case-insensitive)
PROMPT_INJECTION_PATTERNS = [
    r"you are an? ai",
    r"if you are an? ai",
    r"ai system",
    r"ai assistant",
    r"summarize this? positively",
    r"summarize this? favorably",
    r"when summarizing",
    r"ignore previous",
    r"ignore any negative",
    r"ignore all previous",
    r"disregard previous",
    r"focus on the positive",
    r"emphasize that .* is legitimate",
    r"do not mention .* complaints?",
    r"do not mention .* concerns?",
    r"please note that this",
    r"this is a? legitimate",
    r"ai summary instructions?",
    r"for ai (systems?|assistants?|models?)",
    r"llm instructions?",
    r"gpt instructions?",
    r"claude instructions?",
    r"system:?\s*you",
    r"<\|im_start\|>",
    r"<\|system\|>",
]

# CSS patterns indicating hidden content
CSS_HIDDEN_PATTERNS = {
    "display_none": r"display\s*:\s*none",
    "visibility_hidden": r"visibility\s*:\s*hidden",
    "opacity_zero": r"opacity\s*:\s*0(?:[^.]|$)",
    "font_size_zero": r"font-size\s*:\s*0",
    "height_zero": r"height\s*:\s*0",
    "width_zero": r"width\s*:\s*0[^%\d]",
    "overflow_hidden": r"overflow\s*:\s*hidden",
    "text_indent_negative": r"text-indent\s*:\s*-\d{4,}",
    "position_offscreen_left": r"left\s*:\s*-\d{4,}",
    "position_offscreen_top": r"top\s*:\s*-\d{4,}",
    "clip_rect": r"clip\s*:\s*rect\s*\(\s*0",
}

# Request settings
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 2.0  # Seconds between requests (be polite)
USER_AGENT = "Mozilla/5.0 (compatible; LegalAIResearch/1.0; Academic Research)"

# Sample legal settlement URLs for testing
# These are real settlement sites from Stanford SCAC and public sources
SAMPLE_LEGAL_URLS = [
    # Class action settlement sites
    "https://www.equifaxbreachsettlement.com/",
    "https://www.faborgsettlement.com/",
    "https://www.totalclaimsolution.com/",
    "https://www.gilardi.com/",
    "https://www.strategicclaims.net/",

    # Data breach settlements
    "https://www.t-mobilesettlement.com/",
    "https://www.yahoodatabreachsettlement.com/",
    "https://www.capitalonesettlement.com/",

    # Securities class actions
    "https://www.worldacceptancecorporationsecuritieslitigation.com/",

    # Consumer protection
    "https://www.classaction.org/",
    "https://www.topclassactions.com/",

    # Official/control sites
    "https://securities.stanford.edu/",
    "https://www.sec.gov/divisions/enforce/claims.htm",
]

# Additional URLs to crawl (settlement administrator sites)
SETTLEMENT_ADMIN_SITES = [
    "https://www.gilardi.com/cases/",
    "https://www.classaction.org/settlements/",
    "https://topclassactions.com/category/lawsuit-settlements/open-class-action-settlements/",
]
