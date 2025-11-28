"""
PDF order scraper for extracting CM/ECF implementation dates from court orders.
"""

import logging
from typing import List, Optional, Tuple
from urllib.parse import urljoin

from .base_scraper import BaseScraper
from ..models.court_data import CourtData, DateCandidate, SourceType, DatePrecision
from ..parsers.html_parser import HTMLParser
from ..parsers.pdf_extractor import PDFExtractor
from ..parsers.date_extractor import DateExtractor

logger = logging.getLogger(__name__)


class PDFOrderScraper(BaseScraper):
    """Scraper for PDF court orders."""

    def __init__(self, **kwargs):
        """Initialize PDF order scraper."""
        super().__init__(**kwargs)
        self.html_parser = HTMLParser()
        self.pdf_extractor = PDFExtractor()
        self.date_extractor = DateExtractor()

    def scrape(self, court_data: CourtData) -> CourtData:
        """
        Scrape PDF orders from a court's website.

        Args:
            court_data: CourtData object to populate

        Returns:
            Updated CourtData with any found dates
        """
        base_url = court_data.base_url
        logger.info(f"Scraping PDFs for {court_data.court_id}: {base_url}")

        # Find PDF links
        pdf_urls = self._find_pdf_links(base_url)

        for pdf_url, link_text in pdf_urls:
            try:
                candidates = self._scrape_pdf(pdf_url, link_text)
                if candidates:
                    court_data.all_candidates.extend(candidates)
                    logger.info(f"Found {len(candidates)} date candidates in PDF: {pdf_url}")
            except Exception as e:
                logger.error(f"Error scraping PDF {pdf_url}: {e}")

        # Apply the best candidate
        court_data.apply_best_candidate()

        return court_data

    def _find_pdf_links(self, base_url: str) -> List[Tuple[str, str]]:
        """
        Find PDF links on order pages.

        Args:
            base_url: Court website base URL

        Returns:
            List of (pdf_url, link_text) tuples
        """
        self.html_parser.base_url = base_url

        # Pages likely to have PDF orders
        order_paths = [
            '/general-orders',
            '/orders/general-orders',
            '/administrative-orders',
            '/orders/administrative-orders',
            '/standing-orders',
            '/orders',
            '/cmecf',
            '/cm-ecf',
            '/electronic-filing',
        ]

        pdf_links = []
        seen_urls = set()

        for path in order_paths:
            url = urljoin(base_url, path)
            html, result = self.fetch_html(url)

            if not html or not result.success:
                continue

            # Find PDF links
            links = self.html_parser.extract_pdf_links(html)

            for link_url, link_text in links:
                # Resolve relative URLs
                if not link_url.startswith('http'):
                    link_url = urljoin(base_url, link_url)

                if link_url in seen_urls:
                    continue
                seen_urls.add(link_url)

                # Check if link appears relevant
                if self._is_relevant_link(link_url, link_text):
                    pdf_links.append((link_url, link_text))

        return pdf_links

    def _is_relevant_link(self, url: str, text: str) -> bool:
        """Check if a PDF link might contain CM/ECF implementation info."""
        combined = (url + ' ' + text).lower()

        keywords = [
            'cm/ecf', 'cmecf', 'cm-ecf',
            'electronic case filing', 'electronic filing', 'e-filing', 'efiling',
            'ecf', 'general order', 'administrative order',
            '2002', '2003', '2004', '2005', '2006', '2007',  # Common implementation years
        ]

        return any(kw in combined for kw in keywords)

    def _scrape_pdf(self, pdf_url: str, link_text: str = "") -> List[DateCandidate]:
        """
        Scrape a single PDF for date candidates.

        Args:
            pdf_url: URL of the PDF
            link_text: Link text (may contain relevant info)

        Returns:
            List of DateCandidate objects found
        """
        pdf_content, result = self.fetch_pdf(pdf_url)

        if not pdf_content or not result.success:
            logger.debug(f"Failed to fetch PDF {pdf_url}: {result.error_message}")
            return []

        # Extract text from PDF
        text = self.pdf_extractor.extract_text(pdf_content)

        if not text:
            logger.debug(f"Could not extract text from PDF: {pdf_url}")
            return []

        # Clean the text
        text = self.pdf_extractor.clean_text(text)

        # Check if PDF is relevant
        if not self._is_relevant_text(text):
            logger.debug(f"PDF doesn't appear relevant to CM/ECF: {pdf_url}")
            return []

        # Determine source type based on content
        source_type = self._determine_source_type(text, link_text)

        # Extract dates
        candidates = self.date_extractor.extract_dates(
            text,
            source_url=pdf_url,
            source_type=source_type
        )

        # Boost confidence for dates found in official court orders
        if source_type in (SourceType.ADMINISTRATIVE_ORDER, SourceType.GENERAL_ORDER):
            for candidate in candidates:
                candidate.confidence_score = min(candidate.confidence_score + 1, 5)

        return candidates

    def _is_relevant_text(self, text: str) -> bool:
        """Check if PDF text is relevant to CM/ECF."""
        text_lower = text.lower()
        keywords = ['cm/ecf', 'cmecf', 'electronic case filing', 'electronic filing',
                    'ecf system', 'e-filing']
        return any(kw in text_lower for kw in keywords)

    def _determine_source_type(self, text: str, link_text: str) -> SourceType:
        """Determine the type of PDF based on content."""
        combined = (text[:1000] + ' ' + link_text).lower()

        if 'general order' in combined:
            return SourceType.GENERAL_ORDER
        elif 'administrative order' in combined:
            return SourceType.ADMINISTRATIVE_ORDER
        elif 'local rule' in combined:
            return SourceType.LOCAL_RULES
        else:
            return SourceType.COURT_WEBSITE

    def scrape_specific_pdf(self, pdf_url: str) -> List[DateCandidate]:
        """
        Scrape a specific PDF URL.

        Args:
            pdf_url: URL of the PDF to scrape

        Returns:
            List of DateCandidate objects
        """
        return self._scrape_pdf(pdf_url)

    def search_pdf_for_dates(self, pdf_content: bytes, source_url: str) -> List[DateCandidate]:
        """
        Search PDF content for CM/ECF dates.

        Args:
            pdf_content: Raw PDF bytes
            source_url: URL for attribution

        Returns:
            List of DateCandidate objects
        """
        # Extract text
        text = self.pdf_extractor.extract_text(pdf_content)
        if not text:
            return []

        text = self.pdf_extractor.clean_text(text)

        # Determine source type
        source_type = self._determine_source_type(text, "")

        # Extract dates
        return self.date_extractor.extract_dates(
            text,
            source_url=source_url,
            source_type=source_type
        )

    def get_pdf_metadata(self, pdf_url: str) -> dict:
        """
        Get metadata from a PDF.

        Args:
            pdf_url: URL of the PDF

        Returns:
            Dictionary with PDF metadata
        """
        pdf_content, result = self.fetch_pdf(pdf_url)

        if not pdf_content or not result.success:
            return {}

        return self.pdf_extractor.get_metadata(pdf_content)
