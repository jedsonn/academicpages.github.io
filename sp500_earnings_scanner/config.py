"""
Configuration settings for S&P 500 earnings scanner.

This module contains all configurable parameters for the EDGAR scraper,
IR crawler, and hidden text detector.
"""

from pathlib import Path
from datetime import date

# =============================================================================
# Directory paths
# =============================================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# Input file
SP500_FIRMS_CSV = DATA_DIR / "sp500_firms.csv"

# Output files
EDGAR_OUTPUT_CSV = OUTPUT_DIR / "edgar_hidden_scan.csv"
IR_OUTPUT_CSV = OUTPUT_DIR / "ir_hidden_scan.csv"
EDGAR_OUTPUT_PARQUET = OUTPUT_DIR / "edgar_hidden_scan.parquet"
IR_OUTPUT_PARQUET = OUTPUT_DIR / "ir_hidden_scan.parquet"

# =============================================================================
# SEC EDGAR settings
# =============================================================================
SEC_BASE_URL = "https://data.sec.gov"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
SEC_SUBMISSIONS_URL = f"{SEC_BASE_URL}/submissions"

# IMPORTANT: Replace with your actual contact info for SEC compliance
SEC_USER_AGENT = "Academic Research Bot (contact@university.edu)"

# Rate limiting (SEC allows 10 req/sec, but we're conservative)
SEC_REQUESTS_PER_SECOND = 2.0
SEC_MIN_DELAY = 0.4  # seconds between requests
SEC_MAX_DELAY = 0.8  # add random jitter up to this

# Date range for filings
FILING_START_DATE = date(2023, 1, 1)
FILING_END_DATE = date(2025, 12, 31)

# =============================================================================
# IR Crawler settings
# =============================================================================
IR_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "AcademicResearchBot/1.0 (contact@university.edu)"
)

# Crawler behavior
IR_MAX_DEPTH = 3  # Maximum crawl depth from IR root
IR_MAX_PAGES_PER_DOMAIN = 100  # Stop after this many pages per firm
IR_REQUEST_TIMEOUT = 30  # seconds
IR_MIN_DELAY = 1.0  # seconds between requests
IR_MAX_DELAY = 2.0  # random jitter

# Respect robots.txt
IR_OBEY_ROBOTS_TXT = True

# =============================================================================
# Keywords for filtering
# =============================================================================

# Earnings-related keywords for filtering 8-Ks and IR pages
EARNINGS_KEYWORDS = [
    "earnings",
    "results",
    "quarterly",
    "q1",
    "q2",
    "q3",
    "q4",
    "full-year",
    "full year",
    "annual",
    "financial results",
    "operating results",
    "fiscal",
    "revenue",
    "income",
    "eps",
    "guidance",
]

# URL path keywords for IR crawler
IR_URL_KEYWORDS = [
    "earnings",
    "results",
    "quarterly",
    "q1",
    "q2",
    "q3",
    "q4",
    "full-year",
    "press-release",
    "press_release",
    "pressrelease",
    "news",
    "financial",
    "investor",
    "ir",
    "release",
    "announcement",
]

# Extensions to skip during crawling
SKIP_EXTENSIONS = [
    ".pdf",
    ".xls",
    ".xlsx",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".zip",
    ".tar",
    ".gz",
    ".csv",
    ".json",
    ".xml",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".css",
    ".js",
]

# =============================================================================
# Hidden text detection settings
# =============================================================================

# Minimum character count for a hidden block to be flagged
MIN_HIDDEN_BLOCK_LENGTH = 20

# Minimum comment length to be flagged
MIN_COMMENT_LENGTH = 40

# Maximum examples to store per category
MAX_EXAMPLE_SNIPPETS = 3

# Maximum snippet length for storage
MAX_SNIPPET_LENGTH = 500

# Zero-width and invisible Unicode characters to detect
ZERO_WIDTH_CHARS = [
    "\u200b",  # Zero-width space
    "\u200c",  # Zero-width non-joiner
    "\u200d",  # Zero-width joiner
    "\u200e",  # Left-to-right mark
    "\u200f",  # Right-to-left mark
    "\u2060",  # Word joiner
    "\u2061",  # Function application
    "\u2062",  # Invisible times
    "\u2063",  # Invisible separator
    "\ufeff",  # BOM / Zero-width no-break space
]

# Prompt-like regex patterns to detect
PROMPT_PATTERNS = [
    r"\byou are an? ai\b",
    r"\byou are an? (large )?language model\b",
    r"\bas a large language model\b",
    r"\bas an? ai (assistant|model|system)\b",
    r"\bignore (previous|all|the above) instructions?\b",
    r"\bdisregard (the above|previous|all)\b",
    r"\bforget (your|the|all) (previous )?instructions?\b",
    r"\bsummarize (this|the document|the following)( positively| negatively| favorably)?\b",
    r"\brespond (in a )?(positive|negative|favorable|unfavorable) (tone|manner|way)\b",
    r"\bact as an? (analyst|assistant|expert|advisor)\b",
    r"\bpretend (you are|to be)\b",
    r"\bwhen (summarizing|analyzing|responding)\b.*\b(positive|negative|favorable)\b",
    r"\bdo not (mention|include|highlight)\b.*\b(negative|risk|concern|problem)\b",
    r"\bemphasize (only )?(the )?(positive|good|strong)\b",
    r"\bhide (the|any) (negative|risk|concern|problem)\b",
    r"\b(system|user|assistant) ?prompt\b",
    r"\b<<SYS>>|<\|im_start\|>|<\|system\|>\b",
    r"\b\[INST\]|\[/INST\]\b",
]

# =============================================================================
# CSS patterns indicating hidden content
# =============================================================================

# CSS properties that hide content
HIDDEN_CSS_PATTERNS = {
    "display_none": r"display\s*:\s*none",
    "visibility_hidden": r"visibility\s*:\s*hidden",
    "opacity_zero": r"opacity\s*:\s*0(?:[^.]|$)",
    "font_size_zero": r"font-size\s*:\s*0",
    "height_zero": r"height\s*:\s*0",
    "width_zero": r"width\s*:\s*0",
    "overflow_hidden": r"overflow\s*:\s*hidden",
    "clip_rect": r"clip\s*:\s*rect\s*\(\s*0",
    "text_indent_negative": r"text-indent\s*:\s*-\d{4,}",
}

# Colors that match common backgrounds (white-on-white, etc.)
WHITE_COLOR_PATTERNS = [
    r"color\s*:\s*#fff(?:fff)?(?:\s|;|$)",
    r"color\s*:\s*white(?:\s|;|$)",
    r"color\s*:\s*rgb\s*\(\s*255\s*,\s*255\s*,\s*255\s*\)",
    r"color\s*:\s*rgba\s*\(\s*255\s*,\s*255\s*,\s*255\s*,\s*[01](?:\.\d+)?\s*\)",
]

# Off-screen positioning patterns
OFFSCREEN_PATTERNS = [
    r"(?:left|top|right|bottom)\s*:\s*-\d{3,}",  # e.g., left: -9999px
    r"(?:left|top)\s*:\s*\d{4,}",  # e.g., left: 9999px
    r"transform\s*:\s*translate[XY]?\s*\(\s*-?\d{4,}",
    r"margin-(?:left|top)\s*:\s*-\d{4,}",
]

# =============================================================================
# Logging settings
# =============================================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# Optional: Headless browser settings (for visible vs raw diff)
# =============================================================================
ENABLE_HEADLESS_DIFF = False  # Set to True to enable Playwright comparison
PLAYWRIGHT_TIMEOUT = 30000  # ms
