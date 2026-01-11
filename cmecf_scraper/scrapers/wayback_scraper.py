"""
Wayback Machine scraper for historical court website data.
"""

import logging
from typing import List, Optional, Tuple
from urllib.parse import urljoin, quote
import json

from scrapers.base_scraper import BaseScraper
from models.court_data import CourtData, DateCandidate, SourceType, DatePrecision
from parsers.html_parser import HTMLParser
from parsers.date_extractor import DateExtractor
from config import WAYBACK_API_URL, WAYBACK_SNAPSHOT_URL

logger = logging.getLogger(__name__)


class WaybackScraper(BaseScraper):
    """Scraper for Internet Archive Wayback Machine."""

    def __init__(self, **kwargs):
        """Initialize Wayback scraper."""
        super().__init__(**kwargs)
        self.html_parser = HTMLParser()
        self.date_extractor = DateExtractor()
        # Longer timeout for Wayback Machine
        self.timeout = 60

    def scrape(self, court_data: CourtData) -> CourtData:
        """
        Search Wayback Machine for historical court website snapshots.

        Args:
            court_data: CourtData object to populate

        Returns:
            Updated CourtData with any found dates
        """
        base_url = court_data.base_url
        logger.info(f"Searching Wayback Machine for {court_data.court_id}: {base_url}")

        # Get available snapshots from 2001-2008
        snapshots = self._get_snapshots(base_url, start_year=2001, end_year=2008)

        if not snapshots:
            logger.info(f"No Wayback snapshots found for {base_url}")
            return court_data

        logger.info(f"Found {len(snapshots)} snapshots for {base_url}")

        # Sample snapshots (don't fetch all - too many requests)
        sampled_snapshots = self._sample_snapshots(snapshots, max_per_year=2)

        for timestamp, snapshot_url in sampled_snapshots:
            try:
                candidates = self._scrape_snapshot(snapshot_url, timestamp)
                if candidates:
                    court_data.all_candidates.extend(candidates)
                    logger.info(f"Found {len(candidates)} candidates in snapshot from {timestamp}")
            except Exception as e:
                logger.error(f"Error scraping Wayback snapshot {snapshot_url}: {e}")

        # Apply the best candidate
        court_data.apply_best_candidate()

        return court_data

    def _get_snapshots(
        self,
        url: str,
        start_year: int = 2001,
        end_year: int = 2008
    ) -> List[Tuple[str, str]]:
        """
        Get available Wayback Machine snapshots for a URL.

        Args:
            url: URL to search for
            start_year: Start year for snapshots
            end_year: End year for snapshots

        Returns:
            List of (timestamp, snapshot_url) tuples
        """
        # CDX API query
        cdx_url = (
            f"{WAYBACK_API_URL}?"
            f"url={quote(url, safe='')}&"
            f"matchType=prefix&"
            f"from={start_year}&"
            f"to={end_year}&"
            f"output=json&"
            f"filter=statuscode:200&"
            f"collapse=timestamp:6"  # One per month
        )

        response, error = self._make_request(cdx_url)

        if error or response is None:
            logger.warning(f"Error querying Wayback CDX: {error}")
            return []

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from Wayback CDX")
            return []

        if not data or len(data) < 2:
            return []

        # First row is headers
        headers = data[0]
        timestamp_idx = headers.index('timestamp') if 'timestamp' in headers else 1
        original_idx = headers.index('original') if 'original' in headers else 2

        snapshots = []
        for row in data[1:]:
            try:
                timestamp = row[timestamp_idx]
                original_url = row[original_idx]
                snapshot_url = f"{WAYBACK_SNAPSHOT_URL}/{timestamp}/{original_url}"
                snapshots.append((timestamp, snapshot_url))
            except (IndexError, TypeError):
                continue

        return snapshots

    def _sample_snapshots(
        self,
        snapshots: List[Tuple[str, str]],
        max_per_year: int = 2
    ) -> List[Tuple[str, str]]:
        """
        Sample snapshots to avoid too many requests.

        Args:
            snapshots: All available snapshots
            max_per_year: Maximum snapshots per year

        Returns:
            Sampled list of snapshots
        """
        # Group by year
        by_year = {}
        for timestamp, url in snapshots:
            year = timestamp[:4]
            if year not in by_year:
                by_year[year] = []
            by_year[year].append((timestamp, url))

        # Sample from each year
        sampled = []
        for year in sorted(by_year.keys()):
            year_snapshots = by_year[year]
            # Take first and last of year (most likely to show implementation)
            if len(year_snapshots) <= max_per_year:
                sampled.extend(year_snapshots)
            else:
                sampled.append(year_snapshots[0])  # First
                sampled.append(year_snapshots[-1])  # Last

        return sampled

    def _scrape_snapshot(self, snapshot_url: str, timestamp: str) -> List[DateCandidate]:
        """
        Scrape a Wayback Machine snapshot.

        Args:
            snapshot_url: Full Wayback snapshot URL
            timestamp: Snapshot timestamp

        Returns:
            List of DateCandidate objects
        """
        html, result = self.fetch_html(snapshot_url)

        if not html or not result.success:
            logger.debug(f"Failed to fetch snapshot {snapshot_url}: {result.error_message}")
            return []

        # Extract text
        text = self.html_parser.extract_text(html)

        if not text:
            return []

        # Check relevance
        if not self._is_relevant_text(text):
            return []

        # Extract dates
        candidates = self.date_extractor.extract_dates(
            text,
            source_url=snapshot_url,
            source_type=SourceType.WAYBACK
        )

        # Add context about snapshot date
        for candidate in candidates:
            snapshot_date = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
            candidate.context += f" [Wayback snapshot from {snapshot_date}]"

            # Boost confidence if the date in the snapshot predates or matches snapshot date
            if candidate.normalized_date and candidate.normalized_date <= snapshot_date:
                candidate.confidence_score = min(candidate.confidence_score + 1, 5)

        return candidates

    def _is_relevant_text(self, text: str) -> bool:
        """Check if text is relevant to CM/ECF."""
        text_lower = text.lower()
        keywords = ['cm/ecf', 'cmecf', 'electronic case filing', 'electronic filing',
                    'ecf', 'e-filing']
        return any(kw in text_lower for kw in keywords)

    def get_earliest_mention(self, url: str) -> Optional[str]:
        """
        Find the earliest Wayback snapshot mentioning CM/ECF.

        This can help infer when CM/ECF was implemented.

        Args:
            url: Court website URL

        Returns:
            Earliest snapshot date (YYYY-MM-DD) or None
        """
        snapshots = self._get_snapshots(url, start_year=2001, end_year=2008)

        if not snapshots:
            return None

        # Check snapshots from oldest to newest
        for timestamp, snapshot_url in sorted(snapshots):
            html, result = self.fetch_html(snapshot_url)

            if not html or not result.success:
                continue

            text = self.html_parser.extract_text(html)
            if self._is_relevant_text(text):
                return f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"

        return None

    def check_announcement_pages(self, base_url: str) -> List[DateCandidate]:
        """
        Check archived announcement/news pages for CM/ECF launch announcements.

        Args:
            base_url: Court website base URL

        Returns:
            List of DateCandidate objects
        """
        candidates = []

        # News/announcement paths to check
        news_paths = ['/news', '/announcements', '/press', '/updates']

        for path in news_paths:
            url = urljoin(base_url, path)
            snapshots = self._get_snapshots(url, start_year=2002, end_year=2007)

            if not snapshots:
                continue

            # Sample a few snapshots
            for timestamp, snapshot_url in self._sample_snapshots(snapshots, max_per_year=1):
                try:
                    page_candidates = self._scrape_snapshot(snapshot_url, timestamp)
                    candidates.extend(page_candidates)
                except Exception as e:
                    logger.debug(f"Error checking announcement page: {e}")

        return candidates
