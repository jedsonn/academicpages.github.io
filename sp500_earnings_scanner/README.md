# S&P 500 Earnings Hidden Text Scanner

A Python-based system for systematically scanning S&P 500 firms' earnings-related 8-K filings and investor relations announcements for hidden or AI-targeted text.

## Overview

This tool detects potential "hidden prompt" patterns in corporate disclosures, including:

- **CSS-hidden text**: Elements with `display: none`, `visibility: hidden`, `opacity: 0`, etc.
- **Off-screen positioning**: Elements positioned with large negative offsets
- **Zero-width Unicode**: Invisible characters like U+200B, U+FEFF
- **Long HTML comments**: Comments containing narrative text
- **Suspicious metadata**: JSON-LD and meta tags with unusual content
- **Prompt-like phrases**: Text targeting AI systems ("you are an AI", "ignore previous instructions", etc.)

## Project Structure

```
sp500_earnings_scanner/
├── config.py           # Configuration settings
├── edgar_scraper.py    # SEC EDGAR 8-K scraper
├── ir_crawler.py       # Investor relations website crawler
├── hidden_detector.py  # Detection algorithms
├── main_pipeline.py    # Pipeline orchestrator
├── requirements.txt    # Python dependencies
├── data/
│   └── sp500_firms.csv # Input: S&P 500 firm list
└── output/
    ├── edgar_hidden_scan.csv      # EDGAR results
    ├── edgar_hidden_scan.parquet
    ├── ir_hidden_scan.csv         # IR results
    └── ir_hidden_scan.parquet
```

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Edit `config.py` to customize:

- **SEC_USER_AGENT**: Your contact info for SEC compliance (required)
- **FILING_START_DATE / FILING_END_DATE**: Date range for 8-K filings
- **IR_MAX_PAGES_PER_DOMAIN**: Maximum pages to crawl per IR site
- **IR_MAX_DEPTH**: Maximum crawl depth
- **Rate limiting**: Adjust delays between requests

## Usage

### Run Full Pipeline

```bash
# Process all firms in sp500_firms.csv
python main_pipeline.py

# Process specific tickers
python main_pipeline.py --tickers AAPL MSFT GOOGL

# Process first 10 firms only
python main_pipeline.py --limit 10

# Resume from a specific ticker
python main_pipeline.py --resume-from NVDA

# Skip EDGAR or IR crawling
python main_pipeline.py --no-edgar
python main_pipeline.py --no-ir

# Verbose output
python main_pipeline.py -v
```

### Use Individual Modules

```python
from sp500_earnings_scanner import (
    analyze_page,
    scrape_firm,
    crawl_firm_ir,
)

# Analyze a single HTML page
html = "<html>...</html>"
results = analyze_page(html)
print(f"Suspicion score: {results['suspicion_score']}")
print(f"Hidden blocks: {results['n_hidden_blocks']}")
print(f"Prompt hits: {results['n_prompt_hits']}")

# Scrape EDGAR 8-Ks for one firm
documents = scrape_firm(
    cik="0000320193",
    ticker="AAPL",
    company_name="Apple Inc.",
)

# Crawl IR site for one firm
pages = crawl_firm_ir(
    ir_root_url="https://investor.apple.com",
    ticker="AAPL",
    company_name="Apple Inc.",
    max_pages=50,
)
```

## Input Data Format

The input CSV (`data/sp500_firms.csv`) should have columns:

| Column | Description |
|--------|-------------|
| `ticker` | Stock ticker symbol |
| `company_name` | Full company name |
| `cik` | SEC CIK (10-digit, zero-padded) |
| `ir_root_url` | Investor relations website URL |

## Output Data Format

### EDGAR Output (`edgar_hidden_scan.csv`)

| Column | Description |
|--------|-------------|
| `ticker` | Stock ticker |
| `company_name` | Company name |
| `cik` | SEC CIK |
| `form` | Form type (8-K) |
| `filing_date` | Filing date |
| `accession_number` | SEC accession number |
| `doc_type` | Document type (primary_8k, exhibit_99, etc.) |
| `source_url` | Document URL |
| `n_hidden_blocks` | Count of CSS-hidden text blocks |
| `n_offscreen_blocks` | Count of off-screen positioned blocks |
| `has_zero_width` | Boolean: contains zero-width chars |
| `n_comments` | Count of suspicious HTML comments |
| `n_prompt_hits` | Count of prompt-like pattern matches |
| `suspicion_score` | Computed suspicion score |
| `example_hidden_block` | Sample hidden text |
| `example_prompt_hit` | Sample prompt pattern match |

### IR Output (`ir_hidden_scan.csv`)

Similar structure, with `page_url` and `ir_root_url` instead of SEC-specific fields.

## Detection Details

### Suspicion Score Calculation

```
score = (n_prompt_hits * 10)
      + (n_hidden_blocks * 5)
      + (n_offscreen_blocks * 5)
      + (has_zero_width ? 3 + count * 0.5 : 0)
      + (n_comments > 5 ? 2 + (n_comments - 5) * 0.5 : 0)
```

### Prompt Patterns Detected

- "you are an AI"
- "as a large language model"
- "ignore previous instructions"
- "disregard the above"
- "summarize this positively/negatively"
- "respond in a positive tone"
- "act as an analyst/assistant"
- System prompt markers (`<<SYS>>`, `[INST]`, etc.)

## SEC EDGAR Compliance

This tool follows SEC EDGAR access guidelines:

1. Uses a descriptive User-Agent with contact info
2. Limits requests to 2-3 per second (below SEC's 10/sec limit)
3. Adds random delays between requests
4. Handles rate limiting gracefully

**Important**: Update `SEC_USER_AGENT` in `config.py` with your actual contact information.

## Extending the System

### Adding New Detection Patterns

Edit `config.py` to add patterns:

```python
PROMPT_PATTERNS = [
    # ... existing patterns
    r"\bnew pattern here\b",
]

HIDDEN_CSS_PATTERNS = {
    # ... existing patterns
    "new_pattern": r"css-property:\s*value",
}
```

### Optional: Headless Browser Comparison

For more accurate detection, enable Playwright-based visible vs raw text comparison:

```bash
pip install playwright
playwright install chromium
```

Then set `ENABLE_HEADLESS_DIFF = True` in `config.py`.

## Limitations

- PDF detection is limited to text patterns (no CSS analysis)
- IR crawler only follows same-domain links
- Some JavaScript-rendered content may be missed without headless browser
- Rate limiting adds processing time

## License

Research use only. Respect SEC and website terms of service.
