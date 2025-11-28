#!/usr/bin/env python3
"""
CM/ECF Implementation Date Scraper

Main orchestration script for scraping CM/ECF implementation dates
from all 94 U.S. federal district courts.

Usage:
    python main.py --full              # Run full scrape of all courts
    python main.py --court nysd        # Scrape single court
    python main.py --resume            # Resume from checkpoint
    python main.py --report            # Generate report from existing data
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

from tqdm import tqdm

from config import (
    DISTRICT_COURTS, KNOWN_DATES, LOG_FORMAT, LOG_FILE,
    RATE_LIMIT_DELAY, MAX_RETRIES
)
from models.court_data import (
    CourtData, DateCandidate, DatePrecision, SourceType,
    export_to_csv, export_to_json
)
from scrapers.court_website import CourtWebsiteScraper
from scrapers.pdf_parser import PDFOrderScraper
from scrapers.wayback_scraper import WaybackScraper
from scrapers.fjc_scraper import FJCScraper
from utils.rate_limiter import RateLimiter
from utils.user_agent import UserAgentRotator
from utils.validators import validate_court_data, cross_validate_circuits

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode='a'),
    ]
)
logger = logging.getLogger(__name__)


class CMECFScraper:
    """Main orchestrator for CM/ECF date scraping."""

    def __init__(self, output_dir: str = "output"):
        """
        Initialize the scraper.

        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize shared components
        self.rate_limiter = RateLimiter(default_delay=RATE_LIMIT_DELAY)
        self.ua_rotator = UserAgentRotator()

        # Initialize scrapers
        self.court_scraper = CourtWebsiteScraper(
            rate_limiter=self.rate_limiter,
            user_agent_rotator=self.ua_rotator
        )
        self.pdf_scraper = PDFOrderScraper(
            rate_limiter=self.rate_limiter,
            user_agent_rotator=self.ua_rotator
        )
        self.wayback_scraper = WaybackScraper(
            rate_limiter=self.rate_limiter,
            user_agent_rotator=self.ua_rotator
        )
        self.fjc_scraper = FJCScraper(
            rate_limiter=self.rate_limiter,
            user_agent_rotator=self.ua_rotator
        )

        # Results storage
        self.results: Dict[str, CourtData] = {}
        self.checkpoint_file = self.output_dir / "checkpoint.json"

    def apply_known_dates(self, court_data: CourtData) -> None:
        """Apply known reference dates to court data."""
        court_id = court_data.court_id

        if court_id in KNOWN_DATES:
            known = KNOWN_DATES[court_id]

            # Create a candidate from known data
            precision_map = {
                'exact': DatePrecision.EXACT,
                'month': DatePrecision.MONTH,
                'year': DatePrecision.YEAR,
            }

            candidate = DateCandidate(
                date_str=known['date'],
                normalized_date=known['date'] if len(known['date']) == 10 else f"{known['date']}-01-01",
                precision=precision_map.get(known['precision'], DatePrecision.YEAR),
                source_url="known_reference",
                source_type=SourceType.KNOWN_REFERENCE,
                source_text=known.get('notes', ''),
                confidence_score=5,
                context=f"Known reference: {known.get('notes', '')}",
                is_pilot='pilot' in known.get('notes', '').lower(),
            )

            court_data.all_candidates.append(candidate)
            logger.info(f"Applied known date for {court_id}: {known['date']}")

    def scrape_court(self, court_id: str, use_wayback: bool = True) -> CourtData:
        """
        Scrape a single court for CM/ECF implementation date.

        Args:
            court_id: Court identifier
            use_wayback: Whether to use Wayback Machine

        Returns:
            CourtData with found dates
        """
        if court_id not in DISTRICT_COURTS:
            raise ValueError(f"Unknown court: {court_id}")

        config = DISTRICT_COURTS[court_id]
        court_data = CourtData.from_config(court_id, config)

        logger.info(f"Starting scrape for {court_data.court_name} ({court_id})")

        # Apply known dates first
        self.apply_known_dates(court_data)

        # Step 1: Scrape court website
        try:
            logger.info(f"Scraping court website for {court_id}")
            self.court_scraper.scrape(court_data)
        except Exception as e:
            logger.error(f"Error scraping court website for {court_id}: {e}")

        # Step 2: Scrape PDF orders
        try:
            logger.info(f"Scraping PDF orders for {court_id}")
            self.pdf_scraper.scrape(court_data)
        except Exception as e:
            logger.error(f"Error scraping PDFs for {court_id}: {e}")

        # Step 3: Use Wayback Machine if we don't have good data yet
        if use_wayback and court_data.confidence_score < 4:
            try:
                logger.info(f"Searching Wayback Machine for {court_id}")
                self.wayback_scraper.scrape(court_data)
            except Exception as e:
                logger.error(f"Error with Wayback for {court_id}: {e}")

        # Apply best candidate to main fields
        court_data.apply_best_candidate()

        # Log result
        if court_data.cmecf_go_live_date:
            logger.info(
                f"Found date for {court_id}: {court_data.cmecf_go_live_date} "
                f"(confidence: {court_data.confidence_score})"
            )
        else:
            logger.warning(f"No date found for {court_id}")

        return court_data

    def scrape_all(
        self,
        use_wayback: bool = True,
        resume: bool = False,
        courts_subset: Optional[List[str]] = None
    ) -> List[CourtData]:
        """
        Scrape all courts for CM/ECF implementation dates.

        Args:
            use_wayback: Whether to use Wayback Machine
            resume: Whether to resume from checkpoint
            courts_subset: Optional list of court IDs to scrape

        Returns:
            List of CourtData objects
        """
        # Load checkpoint if resuming
        if resume and self.checkpoint_file.exists():
            self.load_checkpoint()
            logger.info(f"Resumed from checkpoint with {len(self.results)} courts")

        # Determine which courts to scrape
        if courts_subset:
            courts_to_scrape = courts_subset
        else:
            courts_to_scrape = list(DISTRICT_COURTS.keys())

        # Skip already scraped courts if resuming
        if resume:
            courts_to_scrape = [c for c in courts_to_scrape if c not in self.results]

        logger.info(f"Scraping {len(courts_to_scrape)} courts")

        # First, try FJC for any aggregated data
        try:
            logger.info("Checking FJC for aggregated CM/ECF data")
            fjc_data = self.fjc_scraper.search_fjc_publications()
            for court_id, candidates in fjc_data.items():
                if court_id in DISTRICT_COURTS:
                    config = DISTRICT_COURTS[court_id]
                    court_data = CourtData.from_config(court_id, config)
                    court_data.all_candidates.extend(candidates)
                    court_data.apply_best_candidate()
                    self.results[court_id] = court_data
                    logger.info(f"Found FJC data for {court_id}")
        except Exception as e:
            logger.error(f"Error fetching FJC data: {e}")

        # Scrape each court
        for court_id in tqdm(courts_to_scrape, desc="Scraping courts"):
            if court_id in self.results and self.results[court_id].confidence_score >= 4:
                logger.info(f"Skipping {court_id} - already have high-confidence data")
                continue

            try:
                court_data = self.scrape_court(court_id, use_wayback=use_wayback)
                self.results[court_id] = court_data

                # Save checkpoint periodically
                if len(self.results) % 10 == 0:
                    self.save_checkpoint()

            except Exception as e:
                logger.error(f"Failed to scrape {court_id}: {e}")
                continue

            # Be nice to servers
            time.sleep(1)

        # Save final checkpoint
        self.save_checkpoint()

        return list(self.results.values())

    def save_checkpoint(self) -> None:
        """Save current results to checkpoint file."""
        checkpoint_data = {
            court_id: court_data.to_dict()
            for court_id, court_data in self.results.items()
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        logger.debug(f"Saved checkpoint with {len(self.results)} courts")

    def load_checkpoint(self) -> None:
        """Load results from checkpoint file."""
        if not self.checkpoint_file.exists():
            return

        with open(self.checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)

        for court_id, data in checkpoint_data.items():
            if court_id in DISTRICT_COURTS:
                config = DISTRICT_COURTS[court_id]
                court_data = CourtData.from_config(court_id, config)

                # Restore fields
                court_data.cmecf_go_live_date = data.get('cmecf_go_live_date')
                court_data.cmecf_go_live_date_precision = DatePrecision(
                    data.get('cmecf_go_live_date_precision', 'unknown')
                )
                court_data.mandatory_efiling_date = data.get('mandatory_efiling_date')
                court_data.pilot_program_date = data.get('pilot_program_date')
                court_data.source_url = data.get('source_url')
                court_data.source_type = SourceType(
                    data.get('source_type', 'not_found')
                )
                court_data.source_text = data.get('source_text')
                court_data.confidence_score = data.get('confidence_score', 0)
                court_data.notes = data.get('notes', '')

                self.results[court_id] = court_data

    def export_results(self) -> None:
        """Export results to CSV and JSON files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        courts_list = list(self.results.values())

        # Sort by court_id
        courts_list.sort(key=lambda c: c.court_id)

        # Export CSV
        csv_file = self.output_dir / f"cmecf_dates_{timestamp}.csv"
        export_to_csv(courts_list, str(csv_file))
        logger.info(f"Exported CSV to {csv_file}")

        # Export JSON
        json_file = self.output_dir / f"cmecf_dates_{timestamp}.json"
        export_to_json(courts_list, str(json_file))
        logger.info(f"Exported JSON to {json_file}")

        # Also save as "latest" files
        export_to_csv(courts_list, str(self.output_dir / "cmecf_dates.csv"))
        export_to_json(courts_list, str(self.output_dir / "cmecf_dates.json"))

    def generate_report(self) -> str:
        """Generate a summary report of scraping results."""
        courts_list = list(self.results.values())

        total = len(courts_list)
        with_dates = sum(1 for c in courts_list if c.cmecf_go_live_date)
        high_confidence = sum(1 for c in courts_list if c.confidence_score >= 4)
        exact_dates = sum(1 for c in courts_list if c.cmecf_go_live_date_precision == DatePrecision.EXACT)

        # Count by source type
        source_counts = {}
        for court in courts_list:
            source = court.source_type.value
            source_counts[source] = source_counts.get(source, 0) + 1

        # Validate data
        all_warnings = []
        for court in courts_list:
            warnings = validate_court_data(court.court_id, court.to_dict())
            all_warnings.extend(warnings)

        circuit_warnings = cross_validate_circuits([c.to_dict() for c in courts_list])
        all_warnings.extend(circuit_warnings)

        # Build report
        report = []
        report.append("=" * 60)
        report.append("CM/ECF SCRAPING REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        report.append("")
        report.append("SUMMARY STATISTICS")
        report.append("-" * 40)
        report.append(f"Total courts:           {total}")
        report.append(f"Courts with dates:      {with_dates} ({100*with_dates/total:.1f}%)")
        report.append(f"High confidence (4-5):  {high_confidence} ({100*high_confidence/total:.1f}%)")
        report.append(f"Exact dates:            {exact_dates} ({100*exact_dates/total:.1f}%)")
        report.append("")
        report.append("BY SOURCE TYPE")
        report.append("-" * 40)
        for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            report.append(f"  {source}: {count}")
        report.append("")

        # Missing courts
        missing = [c for c in courts_list if not c.cmecf_go_live_date]
        if missing:
            report.append("COURTS WITHOUT DATES")
            report.append("-" * 40)
            for court in missing:
                report.append(f"  {court.court_id}: {court.court_name}")
            report.append("")

        # Low confidence courts
        low_conf = [c for c in courts_list if c.cmecf_go_live_date and c.confidence_score < 3]
        if low_conf:
            report.append("LOW CONFIDENCE COURTS (needs review)")
            report.append("-" * 40)
            for court in low_conf:
                report.append(f"  {court.court_id}: {court.cmecf_go_live_date} (conf: {court.confidence_score})")
            report.append("")

        # Validation warnings
        if all_warnings:
            report.append("VALIDATION WARNINGS")
            report.append("-" * 40)
            for warning in all_warnings[:20]:  # Limit to first 20
                report.append(f"  - {warning}")
            if len(all_warnings) > 20:
                report.append(f"  ... and {len(all_warnings) - 20} more warnings")
            report.append("")

        report.append("=" * 60)

        report_text = "\n".join(report)

        # Save report
        report_file = self.output_dir / "scraping_report.txt"
        with open(report_file, 'w') as f:
            f.write(report_text)
        logger.info(f"Report saved to {report_file}")

        return report_text

    def close(self) -> None:
        """Close all scrapers."""
        self.court_scraper.close()
        self.pdf_scraper.close()
        self.wayback_scraper.close()
        self.fjc_scraper.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scrape CM/ECF implementation dates from federal district courts"
    )
    parser.add_argument(
        '--full', action='store_true',
        help='Run full scrape of all courts'
    )
    parser.add_argument(
        '--court', type=str,
        help='Scrape a single court by ID (e.g., nysd)'
    )
    parser.add_argument(
        '--resume', action='store_true',
        help='Resume from checkpoint'
    )
    parser.add_argument(
        '--report', action='store_true',
        help='Generate report from existing data'
    )
    parser.add_argument(
        '--no-wayback', action='store_true',
        help='Skip Wayback Machine searches'
    )
    parser.add_argument(
        '--output-dir', type=str, default='output',
        help='Output directory'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize scraper
    scraper = CMECFScraper(output_dir=args.output_dir)

    try:
        if args.report:
            # Just generate report from checkpoint
            scraper.load_checkpoint()
            if scraper.results:
                report = scraper.generate_report()
                print(report)
            else:
                print("No checkpoint data found. Run --full first.")
            return

        if args.court:
            # Single court
            court_data = scraper.scrape_court(
                args.court,
                use_wayback=not args.no_wayback
            )
            scraper.results[args.court] = court_data
            scraper.export_results()
            print(f"\nResult for {args.court}:")
            print(json.dumps(court_data.to_dict(), indent=2))

        elif args.full or args.resume:
            # Full scrape
            results = scraper.scrape_all(
                use_wayback=not args.no_wayback,
                resume=args.resume
            )
            scraper.export_results()
            report = scraper.generate_report()
            print(report)

        else:
            parser.print_help()

    except KeyboardInterrupt:
        logger.info("Interrupted by user, saving checkpoint...")
        scraper.save_checkpoint()

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
