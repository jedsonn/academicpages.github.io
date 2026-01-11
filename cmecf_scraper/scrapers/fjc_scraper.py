"""
Federal Judicial Center (FJC) scraper for CM/ECF implementation data.
"""

import logging
from typing import List, Optional, Dict
from urllib.parse import urljoin

from scrapers.base_scraper import BaseScraper
from models.court_data import CourtData, DateCandidate, SourceType, DatePrecision
from parsers.html_parser import HTMLParser
from parsers.pdf_extractor import PDFExtractor
from parsers.date_extractor import DateExtractor

logger = logging.getLogger(__name__)


class FJCScraper(BaseScraper):
    """Scraper for Federal Judicial Center resources."""

    FJC_BASE_URL = "https://www.fjc.gov"
    FJC_CMECF_URL = "https://www.fjc.gov/subject/electronic-case-filing-cmecf"
    FJC_HISTORY_URL = "https://www.fjc.gov/history/courts"

    def __init__(self, **kwargs):
        """Initialize FJC scraper."""
        super().__init__(**kwargs)
        self.html_parser = HTMLParser(self.FJC_BASE_URL)
        self.pdf_extractor = PDFExtractor()
        self.date_extractor = DateExtractor()

    def scrape(self, court_data: CourtData) -> CourtData:
        """
        Search FJC resources for CM/ECF implementation information.

        Args:
            court_data: CourtData object to populate

        Returns:
            Updated CourtData with any found dates
        """
        logger.info(f"Searching FJC for {court_data.court_id}")

        # Search FJC CM/ECF page
        candidates = self._scrape_fjc_cmecf_page(court_data.court_name)

        if candidates:
            court_data.all_candidates.extend(candidates)
            logger.info(f"Found {len(candidates)} candidates from FJC")

        # Search court history page
        history_candidates = self._scrape_court_history(court_data.court_name, court_data.state)
        if history_candidates:
            court_data.all_candidates.extend(history_candidates)

        # Apply best candidate
        court_data.apply_best_candidate()

        return court_data

    def _scrape_fjc_cmecf_page(self, court_name: str) -> List[DateCandidate]:
        """
        Scrape FJC's CM/ECF subject page.

        Args:
            court_name: Name of the court

        Returns:
            List of DateCandidate objects
        """
        html, result = self.fetch_html(self.FJC_CMECF_URL)

        if not html or not result.success:
            logger.warning(f"Failed to fetch FJC CM/ECF page: {result.error_message}")
            return []

        # Extract text and search for court-specific information
        text = self.html_parser.extract_text(html)

        # Look for court name mentions
        court_name_lower = court_name.lower()
        if court_name_lower not in text.lower():
            return []

        # Extract dates near court name mentions
        candidates = []
        text_lower = text.lower()
        start = 0

        while True:
            pos = text_lower.find(court_name_lower, start)
            if pos == -1:
                break

            # Get context around the mention
            ctx_start = max(0, pos - 200)
            ctx_end = min(len(text), pos + len(court_name) + 200)
            context = text[ctx_start:ctx_end]

            # Extract dates from context
            context_candidates = self.date_extractor.extract_dates(
                context,
                source_url=self.FJC_CMECF_URL,
                source_type=SourceType.FJC_REPORT
            )

            candidates.extend(context_candidates)
            start = pos + 1

        return candidates

    def _scrape_court_history(self, court_name: str, state: str) -> List[DateCandidate]:
        """
        Scrape FJC court history pages.

        Args:
            court_name: Name of the court
            state: State code

        Returns:
            List of DateCandidate objects
        """
        # FJC has state-specific history pages
        state_url = f"{self.FJC_HISTORY_URL}/{state.lower()}"

        html, result = self.fetch_html(state_url)

        if not html or not result.success:
            return []

        text = self.html_parser.extract_text(html)

        # Look for CM/ECF mentions
        if 'cm/ecf' not in text.lower() and 'electronic filing' not in text.lower():
            return []

        # Extract dates
        return self.date_extractor.extract_dates(
            text,
            source_url=state_url,
            source_type=SourceType.FJC_REPORT
        )

    def search_fjc_publications(self) -> Dict[str, List[DateCandidate]]:
        """
        Search FJC publications for CM/ECF implementation reports.

        Returns:
            Dictionary mapping court_id to list of DateCandidate objects
        """
        results = {}

        # Search FJC publications index
        pub_url = f"{self.FJC_BASE_URL}/publications"
        html, result = self.fetch_html(pub_url)

        if not html or not result.success:
            return results

        # Look for CM/ECF related publications
        links = self.html_parser.extract_links(html, r'cm.?ecf|electronic.?fil')

        for link_url, link_text in links:
            if link_url.endswith('.pdf'):
                candidates = self._process_fjc_pdf(link_url)
                if candidates:
                    # Group by court mentioned
                    for candidate in candidates:
                        # Try to identify court from context
                        court_id = self._identify_court_from_context(candidate.context)
                        if court_id:
                            if court_id not in results:
                                results[court_id] = []
                            results[court_id].append(candidate)

        return results

    def _process_fjc_pdf(self, pdf_url: str) -> List[DateCandidate]:
        """
        Process an FJC PDF publication.

        Args:
            pdf_url: URL of the PDF

        Returns:
            List of DateCandidate objects
        """
        if not pdf_url.startswith('http'):
            pdf_url = urljoin(self.FJC_BASE_URL, pdf_url)

        pdf_content, result = self.fetch_pdf(pdf_url)

        if not pdf_content or not result.success:
            return []

        # Extract text
        text = self.pdf_extractor.extract_text(pdf_content)
        text = self.pdf_extractor.clean_text(text)

        if not text:
            return []

        # Extract dates with CM/ECF context
        return self.date_extractor.extract_dates(
            text,
            source_url=pdf_url,
            source_type=SourceType.FJC_REPORT
        )

    def _identify_court_from_context(self, context: str) -> Optional[str]:
        """
        Try to identify which court is mentioned in context.

        Args:
            context: Text context around a date

        Returns:
            Court ID if identified, None otherwise
        """
        from config import DISTRICT_COURTS

        context_lower = context.lower()

        for court_id, info in DISTRICT_COURTS.items():
            court_name_lower = info['name'].lower()
            if court_name_lower in context_lower:
                return court_id

            # Also check abbreviated forms
            # e.g., "S.D.N.Y." for Southern District of New York
            if info['state'] in context_lower:
                # Check for district indicator
                if 'southern' in context_lower and 'sd' in court_id:
                    return court_id
                if 'northern' in context_lower and 'nd' in court_id:
                    return court_id
                if 'eastern' in context_lower and 'ed' in court_id:
                    return court_id
                if 'western' in context_lower and 'wd' in court_id:
                    return court_id
                if 'middle' in context_lower and 'md' in court_id:
                    return court_id
                if 'central' in context_lower and 'cd' in court_id:
                    return court_id

        return None

    def get_implementation_timeline_data(self) -> List[Dict]:
        """
        Try to find aggregated CM/ECF implementation timeline data from FJC.

        Returns:
            List of dictionaries with court and date information
        """
        timeline_data = []

        # Check for any reports that might have timeline data
        search_terms = [
            'cm/ecf implementation timeline',
            'electronic filing rollout',
            'cm/ecf deployment schedule',
        ]

        for term in search_terms:
            # Search FJC site
            search_url = f"{self.FJC_BASE_URL}/search?q={term.replace(' ', '+')}"
            html, result = self.fetch_html(search_url)

            if not html or not result.success:
                continue

            # Look for relevant results
            links = self.html_parser.extract_links(html)
            for link_url, link_text in links:
                if any(kw in link_text.lower() for kw in ['implementation', 'timeline', 'rollout']):
                    if link_url.endswith('.pdf'):
                        # Process PDF for structured data
                        data = self._extract_timeline_from_pdf(link_url)
                        if data:
                            timeline_data.extend(data)

        return timeline_data

    def _extract_timeline_from_pdf(self, pdf_url: str) -> List[Dict]:
        """
        Try to extract structured timeline data from a PDF.

        Args:
            pdf_url: URL of the PDF

        Returns:
            List of dictionaries with court/date pairs
        """
        if not pdf_url.startswith('http'):
            pdf_url = urljoin(self.FJC_BASE_URL, pdf_url)

        pdf_content, result = self.fetch_pdf(pdf_url)

        if not pdf_content or not result.success:
            return []

        text = self.pdf_extractor.extract_text(pdf_content)
        if not text:
            return []

        # This is a heuristic approach - look for patterns like:
        # "District of Massachusetts - October 1, 2003"
        # or table-like data

        data = []
        from config import DISTRICT_COURTS

        for court_id, info in DISTRICT_COURTS.items():
            court_name = info['name']
            # Look for court name followed by a date
            import re
            pattern = rf'{re.escape(court_name)}[:\s\-]+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{{1,2}},?\s+\d{{4}}|\d{{1,2}}/\d{{1,2}}/\d{{4}}|\d{{4}})'
            matches = re.findall(pattern, text, re.IGNORECASE)

            for match in matches:
                data.append({
                    'court_id': court_id,
                    'court_name': court_name,
                    'date_str': match,
                    'source_url': pdf_url
                })

        return data
