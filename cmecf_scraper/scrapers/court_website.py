"""
Court website scraper for extracting CM/ECF implementation dates.
"""

import logging
from typing import List, Optional
from urllib.parse import urljoin

from .base_scraper import BaseScraper
from ..models.court_data import CourtData, DateCandidate, SourceType, DatePrecision
from ..parsers.html_parser import HTMLParser
from ..parsers.date_extractor import DateExtractor
from ..config import COURT_PAGES_TO_CHECK

logger = logging.getLogger(__name__)


class CourtWebsiteScraper(BaseScraper):
    """Scraper for court websites."""

    def __init__(self, **kwargs):
        """Initialize court website scraper."""
        super().__init__(**kwargs)
        self.html_parser = HTMLParser()
        self.date_extractor = DateExtractor()

    def scrape(self, court_data: CourtData) -> CourtData:
        """
        Scrape a court's website for CM/ECF implementation date.

        Args:
            court_data: CourtData object to populate

        Returns:
            Updated CourtData with any found dates
        """
        base_url = court_data.base_url
        logger.info(f"Scraping {court_data.court_id}: {base_url}")

        # Update HTML parser base URL
        self.html_parser.base_url = base_url

        # Try each page path
        for page_path in COURT_PAGES_TO_CHECK:
            url = urljoin(base_url, page_path) if page_path else base_url

            try:
                candidates = self._scrape_page(url)
                if candidates:
                    court_data.all_candidates.extend(candidates)
                    logger.info(f"Found {len(candidates)} date candidates on {url}")
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")

        # Also look for order pages and PDFs
        self._scrape_order_pages(court_data)

        # Apply the best candidate
        court_data.apply_best_candidate()

        return court_data

    def _scrape_page(self, url: str) -> List[DateCandidate]:
        """
        Scrape a single page for date candidates.

        Args:
            url: URL to scrape

        Returns:
            List of DateCandidate objects found
        """
        html, result = self.fetch_html(url)

        if not html or not result.success:
            logger.debug(f"Failed to fetch {url}: {result.error_message}")
            return []

        # Extract text from HTML
        text = self.html_parser.extract_text(html)

        if not text:
            return []

        # Check if page is relevant (mentions CM/ECF)
        relevant_sections = self.html_parser.find_cmecf_sections(html)

        if not relevant_sections and not self._is_relevant_text(text):
            logger.debug(f"Page {url} doesn't appear relevant to CM/ECF")
            return []

        # Extract dates
        candidates = self.date_extractor.extract_dates(
            text,
            source_url=url,
            source_type=SourceType.COURT_WEBSITE
        )

        # Also search the relevant sections more carefully
        for section_html in relevant_sections:
            section_text = self.html_parser.extract_text(section_html)
            section_candidates = self.date_extractor.extract_dates(
                section_text,
                source_url=url,
                source_type=SourceType.COURT_WEBSITE
            )
            # Boost confidence for dates found in CM/ECF-specific sections
            for candidate in section_candidates:
                candidate.confidence_score = min(candidate.confidence_score + 1, 5)
                if candidate.normalized_date not in [c.normalized_date for c in candidates]:
                    candidates.append(candidate)

        return candidates

    def _is_relevant_text(self, text: str) -> bool:
        """Check if text is relevant to CM/ECF."""
        text_lower = text.lower()
        keywords = ['cm/ecf', 'cmecf', 'electronic case filing', 'electronic filing',
                    'ecf system', 'e-filing', 'efiling']
        return any(kw in text_lower for kw in keywords)

    def _scrape_order_pages(self, court_data: CourtData) -> None:
        """
        Look for and scrape order listing pages.

        Args:
            court_data: CourtData object to update
        """
        base_url = court_data.base_url

        # Order-related paths to check
        order_paths = [
            '/general-orders',
            '/orders/general-orders',
            '/administrative-orders',
            '/orders/administrative-orders',
            '/standing-orders',
            '/court-orders',
            '/orders',
        ]

        for path in order_paths:
            url = urljoin(base_url, path)
            html, result = self.fetch_html(url)

            if not html or not result.success:
                continue

            # Look for links to order pages or PDFs
            order_links = self.html_parser.extract_order_links(html)

            for link_url, link_text in order_links:
                # Check if link text mentions CM/ECF
                if not self._is_relevant_text(link_text):
                    continue

                # Determine if it's a PDF or HTML page
                if link_url.lower().endswith('.pdf'):
                    # We'll handle PDFs in pdf_parser scraper
                    logger.debug(f"Found potentially relevant PDF: {link_url}")
                    continue

                # Scrape the order page
                candidates = self._scrape_page(link_url)
                if candidates:
                    court_data.all_candidates.extend(candidates)

    def scrape_specific_url(self, url: str) -> List[DateCandidate]:
        """
        Scrape a specific URL for CM/ECF dates.

        Args:
            url: URL to scrape

        Returns:
            List of DateCandidate objects
        """
        return self._scrape_page(url)

    def search_site(self, base_url: str, search_term: str = "CM/ECF implementation") -> List[str]:
        """
        Attempt to use the site's search functionality.

        Note: This is best-effort as each site has different search implementations.

        Args:
            base_url: Court website base URL
            search_term: Term to search for

        Returns:
            List of URLs from search results
        """
        # Common search URL patterns
        search_patterns = [
            f"{base_url}/search?q={search_term.replace(' ', '+')}",
            f"{base_url}/search?query={search_term.replace(' ', '+')}",
            f"{base_url}/?s={search_term.replace(' ', '+')}",
        ]

        result_urls = []

        for search_url in search_patterns:
            html, result = self.fetch_html(search_url)

            if not html or not result.success:
                continue

            # Try to extract search result links
            links = self.html_parser.extract_links(html)
            for link_url, link_text in links:
                if self._is_relevant_text(link_text):
                    result_urls.append(link_url)

            if result_urls:
                break  # Found results, stop trying other search patterns

        return result_urls

    def get_court_info_page(self, base_url: str) -> Optional[str]:
        """
        Find the court info or about page.

        Args:
            base_url: Court website base URL

        Returns:
            HTML content of info page or None
        """
        info_paths = [
            '/about-the-court',
            '/about',
            '/court-info',
            '/court-information',
            '/history',
        ]

        for path in info_paths:
            url = urljoin(base_url, path)
            html, result = self.fetch_html(url)
            if html and result.success:
                return html

        return None
