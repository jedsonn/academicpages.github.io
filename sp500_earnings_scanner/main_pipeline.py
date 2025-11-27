"""
Main pipeline orchestrator for S&P 500 earnings hidden text scanner.

This module coordinates:
- Loading S&P 500 firm data
- Running EDGAR 8-K scraper
- Running IR website crawler
- Running hidden text detection
- Writing output datasets
"""

import csv
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any
from dataclasses import asdict

import pandas as pd

from config import (
    DATA_DIR,
    OUTPUT_DIR,
    SP500_FIRMS_CSV,
    EDGAR_OUTPUT_CSV,
    IR_OUTPUT_CSV,
    EDGAR_OUTPUT_PARQUET,
    IR_OUTPUT_PARQUET,
    LOG_LEVEL,
    LOG_FORMAT,
    FILING_START_DATE,
    FILING_END_DATE,
)
from edgar_scraper import EdgarScraper, Document
from ir_crawler import IRCrawler, CrawledPage
from hidden_detector import analyze_page, analyze_text_only

# Setup logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def load_sp500_firms(filepath: Path = SP500_FIRMS_CSV) -> list[dict]:
    """
    Load S&P 500 firms from CSV file.

    Expected columns: ticker, company_name, cik, ir_root_url

    Args:
        filepath: Path to CSV file

    Returns:
        List of firm dicts
    """
    firms = []

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            firms.append({
                "ticker": row.get("ticker", "").strip(),
                "company_name": row.get("company_name", "").strip(),
                "cik": row.get("cik", "").strip(),
                "ir_root_url": row.get("ir_root_url", "").strip(),
            })

    logger.info(f"Loaded {len(firms)} firms from {filepath}")
    return firms


def flatten_analysis(analysis: dict) -> dict:
    """
    Flatten nested analysis dict for CSV output.

    Converts lists to JSON strings and nested dicts to flat keys.

    Args:
        analysis: Analysis result dict

    Returns:
        Flattened dict suitable for CSV
    """
    flat = {}

    for key, value in analysis.items():
        if isinstance(value, list):
            # For lists, store count and first item(s) as JSON
            flat[key] = json.dumps(value) if value else ""
        elif isinstance(value, dict):
            # Flatten nested dicts
            for subkey, subvalue in value.items():
                flat[f"{key}_{subkey}"] = subvalue
        else:
            flat[key] = value

    return flat


def create_edgar_record(doc: Document, analysis: dict) -> dict:
    """
    Create a record for EDGAR output CSV.

    Args:
        doc: Document object
        analysis: Analysis result

    Returns:
        Record dict
    """
    record = {
        "ticker": doc.ticker,
        "company_name": doc.company_name,
        "cik": doc.cik,
        "form": doc.form,
        "filing_date": doc.filing_date,
        "accession_number": doc.accession_number,
        "doc_type": doc.doc_type,
        "filename": doc.filename,
        "source_url": doc.url,
        "content_type": doc.content_type,
        "description": doc.description,
    }

    # Add analysis fields
    record["n_hidden_blocks"] = analysis.get("n_hidden_blocks", 0)
    record["n_offscreen_blocks"] = analysis.get("n_offscreen_blocks", 0)
    record["has_zero_width"] = analysis.get("has_zero_width", False)
    record["zero_width_count"] = analysis.get("zero_width_count", 0)
    record["n_comments"] = analysis.get("n_comments", 0)
    record["n_prompt_hits"] = analysis.get("n_prompt_hits", 0)
    record["suspicion_score"] = analysis.get("suspicion_score", 0.0)
    record["raw_text_length"] = analysis.get("raw_text_length", 0)

    # Add example snippets (truncated)
    hidden_examples = analysis.get("example_hidden_blocks", [])
    record["example_hidden_block"] = hidden_examples[0].get("text", "") if hidden_examples else ""

    comment_examples = analysis.get("example_comments", [])
    record["example_comment"] = comment_examples[0] if comment_examples else ""

    prompt_hits = analysis.get("prompt_hits", [])
    record["example_prompt_hit"] = json.dumps(prompt_hits[0]) if prompt_hits else ""

    record["scan_timestamp"] = datetime.utcnow().isoformat()

    return record


def create_ir_record(page: CrawledPage, analysis: dict) -> dict:
    """
    Create a record for IR output CSV.

    Args:
        page: CrawledPage object
        analysis: Analysis result

    Returns:
        Record dict
    """
    record = {
        "ticker": page.ticker,
        "company_name": page.company_name,
        "ir_root_url": page.ir_root_url,
        "page_url": page.page_url,
        "title": page.title,
        "crawl_timestamp": page.crawl_timestamp,
        "crawl_depth": page.depth,
        "is_earnings_related": page.is_earnings_related,
    }

    # Add analysis fields (same as EDGAR)
    record["n_hidden_blocks"] = analysis.get("n_hidden_blocks", 0)
    record["n_offscreen_blocks"] = analysis.get("n_offscreen_blocks", 0)
    record["has_zero_width"] = analysis.get("has_zero_width", False)
    record["zero_width_count"] = analysis.get("zero_width_count", 0)
    record["n_comments"] = analysis.get("n_comments", 0)
    record["n_prompt_hits"] = analysis.get("n_prompt_hits", 0)
    record["suspicion_score"] = analysis.get("suspicion_score", 0.0)
    record["raw_text_length"] = analysis.get("raw_text_length", 0)

    # Add example snippets
    hidden_examples = analysis.get("example_hidden_blocks", [])
    record["example_hidden_block"] = hidden_examples[0].get("text", "") if hidden_examples else ""

    comment_examples = analysis.get("example_comments", [])
    record["example_comment"] = comment_examples[0] if comment_examples else ""

    prompt_hits = analysis.get("prompt_hits", [])
    record["example_prompt_hit"] = json.dumps(prompt_hits[0]) if prompt_hits else ""

    record["scan_timestamp"] = datetime.utcnow().isoformat()

    return record


class Pipeline:
    """
    Main pipeline orchestrator.

    Coordinates EDGAR scraping, IR crawling, and detection.
    """

    def __init__(
        self,
        firms: list[dict],
        run_edgar: bool = True,
        run_ir: bool = True,
        edgar_earnings_only: bool = True,
        ir_max_pages: int = 100,
        ir_max_depth: int = 3,
    ):
        """
        Initialize pipeline.

        Args:
            firms: List of firm dicts with ticker, company_name, cik, ir_root_url
            run_edgar: Whether to scrape EDGAR 8-Ks
            run_ir: Whether to crawl IR sites
            edgar_earnings_only: Only process earnings-related 8-Ks
            ir_max_pages: Max pages per IR site
            ir_max_depth: Max crawl depth for IR sites
        """
        self.firms = firms
        self.run_edgar = run_edgar
        self.run_ir = run_ir
        self.edgar_earnings_only = edgar_earnings_only
        self.ir_max_pages = ir_max_pages
        self.ir_max_depth = ir_max_depth

        self.edgar_records: list[dict] = []
        self.ir_records: list[dict] = []

        # Initialize scrapers
        if run_edgar:
            self.edgar_scraper = EdgarScraper(
                start_date=FILING_START_DATE,
                end_date=FILING_END_DATE,
            )

        if run_ir:
            self.ir_crawler = IRCrawler(
                max_depth=ir_max_depth,
                max_pages=ir_max_pages,
            )

    def process_edgar_document(self, doc: Document) -> dict:
        """
        Process a single EDGAR document.

        Args:
            doc: Document object

        Returns:
            Record dict with detection results
        """
        # Run detection based on content type
        if doc.content_type == "html":
            analysis = analyze_page(doc.content)
        else:
            analysis = analyze_text_only(doc.content)

        return create_edgar_record(doc, analysis)

    def process_ir_page(self, page: CrawledPage) -> dict:
        """
        Process a single IR page.

        Args:
            page: CrawledPage object

        Returns:
            Record dict with detection results
        """
        analysis = analyze_page(page.html_raw)
        return create_ir_record(page, analysis)

    def run_firm_edgar(self, firm: dict) -> list[dict]:
        """
        Run EDGAR scraping for a single firm.

        Args:
            firm: Firm dict

        Returns:
            List of record dicts
        """
        records = []

        ticker = firm["ticker"]
        company_name = firm["company_name"]
        cik = firm["cik"]

        if not cik:
            logger.warning(f"No CIK for {ticker}, skipping EDGAR")
            return records

        logger.info(f"Processing EDGAR for {ticker} (CIK: {cik})")

        try:
            for doc in self.edgar_scraper.scrape_firm_8ks(
                cik=cik,
                ticker=ticker,
                company_name=company_name,
                earnings_only=self.edgar_earnings_only,
            ):
                record = self.process_edgar_document(doc)
                records.append(record)

                # Log suspicious findings
                if record["suspicion_score"] > 0:
                    logger.info(
                        f"  Suspicious document found: {doc.filename} "
                        f"(score: {record['suspicion_score']:.1f})"
                    )

        except Exception as e:
            logger.error(f"Error processing EDGAR for {ticker}: {e}")

        return records

    def run_firm_ir(self, firm: dict) -> list[dict]:
        """
        Run IR crawling for a single firm.

        Args:
            firm: Firm dict

        Returns:
            List of record dicts
        """
        records = []

        ticker = firm["ticker"]
        company_name = firm["company_name"]
        ir_root_url = firm["ir_root_url"]

        if not ir_root_url:
            logger.warning(f"No IR URL for {ticker}, skipping IR crawl")
            return records

        logger.info(f"Crawling IR site for {ticker}: {ir_root_url}")

        try:
            for page in self.ir_crawler.crawl_ir_site(
                ir_root_url=ir_root_url,
                ticker=ticker,
                company_name=company_name,
            ):
                record = self.process_ir_page(page)
                records.append(record)

                # Log suspicious findings
                if record["suspicion_score"] > 0:
                    logger.info(
                        f"  Suspicious page found: {page.page_url} "
                        f"(score: {record['suspicion_score']:.1f})"
                    )

        except Exception as e:
            logger.error(f"Error crawling IR for {ticker}: {e}")

        return records

    def run(self, resume_from: str | None = None) -> dict:
        """
        Run the full pipeline for all firms.

        Args:
            resume_from: Ticker to resume from (skip firms before this)

        Returns:
            Summary statistics dict
        """
        start_time = datetime.utcnow()
        stats = {
            "firms_processed": 0,
            "edgar_documents": 0,
            "ir_pages": 0,
            "suspicious_edgar": 0,
            "suspicious_ir": 0,
            "errors": 0,
        }

        # Find starting index if resuming
        start_idx = 0
        if resume_from:
            for i, firm in enumerate(self.firms):
                if firm["ticker"].upper() == resume_from.upper():
                    start_idx = i
                    logger.info(f"Resuming from {resume_from} (index {i})")
                    break

        # Process each firm
        for i, firm in enumerate(self.firms[start_idx:], start=start_idx):
            ticker = firm["ticker"]
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing firm {i+1}/{len(self.firms)}: {ticker}")
            logger.info(f"{'='*60}")

            try:
                # EDGAR processing
                if self.run_edgar:
                    edgar_records = self.run_firm_edgar(firm)
                    self.edgar_records.extend(edgar_records)
                    stats["edgar_documents"] += len(edgar_records)
                    stats["suspicious_edgar"] += sum(
                        1 for r in edgar_records if r["suspicion_score"] > 0
                    )

                # IR processing
                if self.run_ir:
                    ir_records = self.run_firm_ir(firm)
                    self.ir_records.extend(ir_records)
                    stats["ir_pages"] += len(ir_records)
                    stats["suspicious_ir"] += sum(
                        1 for r in ir_records if r["suspicion_score"] > 0
                    )

                stats["firms_processed"] += 1

                # Periodic save (every 10 firms)
                if (i + 1) % 10 == 0:
                    self.save_intermediate()
                    logger.info(f"Checkpoint saved at firm {i+1}")

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                stats["errors"] += 1

        # Final save
        self.save_results()

        # Compute final stats
        end_time = datetime.utcnow()
        stats["duration_seconds"] = (end_time - start_time).total_seconds()
        stats["start_time"] = start_time.isoformat()
        stats["end_time"] = end_time.isoformat()

        return stats

    def save_intermediate(self):
        """Save intermediate results (for checkpointing)."""
        self._save_csv(self.edgar_records, OUTPUT_DIR / "edgar_hidden_scan_partial.csv")
        self._save_csv(self.ir_records, OUTPUT_DIR / "ir_hidden_scan_partial.csv")

    def save_results(self):
        """Save final results to CSV and Parquet."""
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Save EDGAR results
        if self.edgar_records:
            self._save_csv(self.edgar_records, EDGAR_OUTPUT_CSV)
            self._save_parquet(self.edgar_records, EDGAR_OUTPUT_PARQUET)
            logger.info(f"Saved {len(self.edgar_records)} EDGAR records")

        # Save IR results
        if self.ir_records:
            self._save_csv(self.ir_records, IR_OUTPUT_CSV)
            self._save_parquet(self.ir_records, IR_OUTPUT_PARQUET)
            logger.info(f"Saved {len(self.ir_records)} IR records")

    def _save_csv(self, records: list[dict], filepath: Path):
        """Save records to CSV file."""
        if not records:
            return

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)

    def _save_parquet(self, records: list[dict], filepath: Path):
        """Save records to Parquet file."""
        if not records:
            return

        try:
            df = pd.DataFrame(records)
            df.to_parquet(filepath, index=False)
        except Exception as e:
            logger.warning(f"Could not save Parquet (pandas/pyarrow not installed?): {e}")


def run_pipeline(
    firms_csv: Path | None = None,
    run_edgar: bool = True,
    run_ir: bool = True,
    resume_from: str | None = None,
    limit_firms: int | None = None,
    tickers: list[str] | None = None,
) -> dict:
    """
    Main entry point to run the pipeline.

    Args:
        firms_csv: Path to firms CSV (default from config)
        run_edgar: Run EDGAR scraper
        run_ir: Run IR crawler
        resume_from: Resume from this ticker
        limit_firms: Limit to first N firms
        tickers: Only process these tickers

    Returns:
        Pipeline statistics dict
    """
    # Load firms
    firms = load_sp500_firms(firms_csv or SP500_FIRMS_CSV)

    # Filter to specific tickers if provided
    if tickers:
        tickers_upper = [t.upper() for t in tickers]
        firms = [f for f in firms if f["ticker"].upper() in tickers_upper]
        logger.info(f"Filtered to {len(firms)} firms by ticker")

    # Limit firms if specified
    if limit_firms:
        firms = firms[:limit_firms]
        logger.info(f"Limited to first {limit_firms} firms")

    # Create and run pipeline
    pipeline = Pipeline(
        firms=firms,
        run_edgar=run_edgar,
        run_ir=run_ir,
    )

    stats = pipeline.run(resume_from=resume_from)

    # Log summary
    logger.info("\n" + "="*60)
    logger.info("PIPELINE COMPLETE")
    logger.info("="*60)
    logger.info(f"Firms processed: {stats['firms_processed']}")
    logger.info(f"EDGAR documents: {stats['edgar_documents']}")
    logger.info(f"IR pages: {stats['ir_pages']}")
    logger.info(f"Suspicious EDGAR docs: {stats['suspicious_edgar']}")
    logger.info(f"Suspicious IR pages: {stats['suspicious_ir']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info(f"Duration: {stats['duration_seconds']:.1f} seconds")

    return stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="S&P 500 Earnings Hidden Text Scanner"
    )
    parser.add_argument(
        "--firms-csv",
        type=Path,
        default=None,
        help="Path to firms CSV file"
    )
    parser.add_argument(
        "--no-edgar",
        action="store_true",
        help="Skip EDGAR scraping"
    )
    parser.add_argument(
        "--no-ir",
        action="store_true",
        help="Skip IR crawling"
    )
    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        help="Resume from ticker"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to first N firms"
    )
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        default=None,
        help="Only process these tickers"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    stats = run_pipeline(
        firms_csv=args.firms_csv,
        run_edgar=not args.no_edgar,
        run_ir=not args.no_ir,
        resume_from=args.resume_from,
        limit_firms=args.limit,
        tickers=args.tickers,
    )

    # Save stats
    stats_file = OUTPUT_DIR / "pipeline_stats.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)


if __name__ == "__main__":
    main()
