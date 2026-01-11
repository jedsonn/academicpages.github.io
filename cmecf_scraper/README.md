# CM/ECF Implementation Date Scraper

A comprehensive Python scraping system to extract CM/ECF (Case Management/Electronic Case Files) implementation dates from all 94 U.S. federal district courts.

## Overview

This tool scrapes court websites, PDF orders, and historical archives to find the exact dates when each federal district court implemented the CM/ECF electronic filing system. The data is intended for academic research requiring precise treatment timing for staggered difference-in-differences research designs.

## Features

- **Multi-source scraping**: Court websites, PDF orders, Wayback Machine, FJC reports
- **Smart date extraction**: Contextual analysis to identify CM/ECF-related dates
- **Confidence scoring**: 1-5 scale based on source quality and precision
- **PDF parsing**: Extracts text from court orders (PDFs)
- **Rate limiting**: Respectful scraping with configurable delays
- **Checkpoint/resume**: Save progress and resume interrupted scrapes
- **Validation**: Cross-reference with known dates, circuit-level validation

## Installation

```bash
cd cmecf_scraper
pip install -r requirements.txt
```

### Dependencies

- `requests`: HTTP requests
- `beautifulsoup4` + `lxml`: HTML parsing
- `PyPDF2` or `pdfplumber`: PDF text extraction
- `pandas`: Data handling
- `tqdm`: Progress bars

## Usage

### Full Scrape

```bash
python main.py --full
```

This will:
1. Check FJC for aggregated data
2. Scrape each court's website
3. Parse relevant PDF orders
4. Search Wayback Machine for courts without high-confidence dates
5. Export results to CSV and JSON

### Single Court

```bash
python main.py --court nysd
```

### Resume from Checkpoint

```bash
python main.py --resume
```

### Generate Report

```bash
python main.py --report
```

### Skip Wayback Machine

```bash
python main.py --full --no-wayback
```

## Output

### CSV Format

```csv
court_id,court_name,circuit,state,cmecf_go_live_date,cmecf_go_live_date_precision,mandatory_efiling_date,pilot_program_date,source_url,source_type,source_text,extraction_timestamp,confidence_score,notes
sdd,District of South Dakota,8,SD,2003-07-03,exact,,,https://www.sdd.uscourts.gov/...,court_website,"On July 3, 2003...",2024-01-15T10:30:00Z,5,
```

### Confidence Scores

- **5**: Exact date from official court source
- **4**: Exact date from secondary source
- **3**: Month-level precision
- **2**: Quarter/year-level precision
- **1**: Inferred from PACER or other indirect source

### Source Types

- `court_website`: Current court website
- `administrative_order`: Administrative order document
- `general_order`: General order document
- `local_rules`: Local court rules
- `wayback`: Internet Archive snapshot
- `fjc_report`: Federal Judicial Center publication
- `known_reference`: Pre-validated reference date

## Project Structure

```
cmecf_scraper/
├── main.py                    # Entry point, orchestration
├── config.py                  # Configuration, court list
├── scrapers/
│   ├── base_scraper.py        # Abstract base class
│   ├── court_website.py       # Court website scraper
│   ├── pdf_parser.py          # PDF order parser
│   ├── wayback_scraper.py     # Internet Archive scraper
│   └── fjc_scraper.py         # FJC reports scraper
├── parsers/
│   ├── date_extractor.py      # Date extraction from text
│   ├── html_parser.py         # HTML parsing
│   └── pdf_extractor.py       # PDF text extraction
├── utils/
│   ├── rate_limiter.py        # Rate limiting
│   ├── user_agent.py          # User agent rotation
│   └── validators.py          # Data validation
├── models/
│   └── court_data.py          # Data models
├── output/                    # Output files
├── tests/                     # Test suite
└── requirements.txt
```

## Known Reference Dates

The following dates are used for validation:

| Court | Date | Notes |
|-------|------|-------|
| N.D. Ohio | 1996 | Pilot - asbestos cases |
| W.D. Missouri | Late 1997 | Pilot |
| E.D. New York | Late 1997 | Pilot |
| D. Oregon | Late 1997 | Pilot |
| N.D. California | April 2, 2001 | Pilot; Full: Jan 1, 2003 |
| D. South Dakota | July 3, 2003 | |
| D. Massachusetts | October 1, 2003 | |
| S.D. Florida | 2002 | Local system; mandatory 2004 |
| E.D. Michigan | November 30, 2005 | |

## Validation

The scraper performs several validation checks:

1. **Date range validation**: Flags dates outside 1996-2008
2. **Known reference comparison**: Compares against known implementation dates
3. **Circuit cross-validation**: Identifies outliers within circuits
4. **Source verification**: Ensures all dates have source URLs and text

## Extending

### Adding a New Scraper

1. Create a new file in `scrapers/`
2. Inherit from `BaseScraper`
3. Implement the `scrape(court_data)` method
4. Register in `main.py`

### Customizing Date Extraction

Edit `parsers/date_extractor.py` to:
- Add new date patterns
- Modify context scoring
- Add new keywords

## Rate Limiting

Default settings:
- 2.5 seconds between requests to same domain
- 3 retries with exponential backoff
- 30 second timeout

Configure in `config.py`.

## License

MIT License

## Disclaimer

This tool is intended for academic research purposes. Please respect court website terms of service and use responsibly.
