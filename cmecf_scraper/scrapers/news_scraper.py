"""
News/Media Article Scraper for CM/ECF Implementation Dates.

Searches legal news sources and archives for CM/ECF rollout announcements.
"""

import re
import logging
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote_plus

try:
    from .base_scraper import BaseScraper
    from ..models.court_data import DateCandidate
    from ..parsers.date_extractor import DateExtractor
except ImportError:
    from scrapers.base_scraper import BaseScraper
    from models.court_data import DateCandidate
    from parsers.date_extractor import DateExtractor

logger = logging.getLogger(__name__)


class NewsScraper(BaseScraper):
    """Scrapes news articles and legal publications for CM/ECF implementation dates."""

    # News sources that covered court technology
    NEWS_SOURCES = [
        # Legal news
        "law.com",
        "abajournal.com",
        "lawsites.com",
        "legaltechnews.com",
        # Court/gov news
        "uscourts.gov",
        "fjc.gov",
        # General news archives
        "nytimes.com",
        "washingtonpost.com",
    ]

    # Search query templates
    SEARCH_QUERIES = [
        '"{court_name}" "CM/ECF" implementation',
        '"{court_name}" "electronic filing" launch',
        '"{court_name}" PACER "goes live"',
        '"{court_name}" "case management" electronic 2001..2010',
        '"{district}" federal court "electronic filing" mandatory',
    ]

    def __init__(self, config: dict):
        super().__init__(config)
        self.date_extractor = DateExtractor()
        self.search_base = "https://www.google.com/search"

    def scrape(self, court_id: str, court_info: dict) -> List[DateCandidate]:
        """
        Search for news articles about CM/ECF implementation for a court.

        Args:
            court_id: Court identifier (e.g., 'nysd')
            court_info: Court metadata including name and state

        Returns:
            List of DateCandidate objects from news sources
        """
        candidates = []
        court_name = court_info.get('name', '')
        state = court_info.get('state', '')

        # Build district description
        district = self._build_district_desc(court_id, court_name, state)

        logger.info(f"Searching news for {court_name} CM/ECF implementation")

        # Try each search query
        for query_template in self.SEARCH_QUERIES[:2]:  # Limit queries to avoid rate limiting
            query = query_template.format(
                court_name=court_name,
                district=district,
                state=state
            )

            try:
                results = self._search_news(query, court_id)
                candidates.extend(results)
            except Exception as e:
                logger.debug(f"News search failed for {court_id}: {e}")

        # Also try searching for specific known news patterns
        candidates.extend(self._search_court_announcements(court_id, court_info))

        return self._deduplicate_candidates(candidates)

    def _build_district_desc(self, court_id: str, court_name: str, state: str) -> str:
        """Build a district description for search queries."""
        # Extract district direction from name
        if "Northern" in court_name:
            return f"Northern District of {state}"
        elif "Southern" in court_name:
            return f"Southern District of {state}"
        elif "Eastern" in court_name:
            return f"Eastern District of {state}"
        elif "Western" in court_name:
            return f"Western District of {state}"
        elif "Central" in court_name:
            return f"Central District of {state}"
        elif "Middle" in court_name:
            return f"Middle District of {state}"
        else:
            return f"District of {state}"

    def _search_news(self, query: str, court_id: str) -> List[DateCandidate]:
        """
        Perform a news search and extract dates from results.

        Note: In production, this would use a proper news API like:
        - Google Custom Search API
        - Bing News API
        - NewsAPI.org

        For now, we'll construct URLs that could be fetched.
        """
        candidates = []

        # Construct search URL (would need API key in production)
        encoded_query = quote_plus(query)
        search_url = f"{self.search_base}?q={encoded_query}&tbs=cdr:1,cd_min:1/1/1996,cd_max:12/31/2015"

        # Try to fetch (will likely fail in sandbox, but structure is there)
        try:
            response = self._make_request(search_url)
            if response and response.status_code == 200:
                # Parse search results for dates
                text = response.text
                dates = self.date_extractor.extract_dates(text)

                for date_info in dates[:3]:  # Limit candidates per search
                    candidates.append(DateCandidate(
                        date=date_info['date'],
                        confidence=min(date_info['confidence'] * 0.8, 3),  # Lower confidence for news
                        source_type="news_search",
                        source_url=search_url,
                        context=f"News search: {query[:50]}...",
                        extraction_method="news_article"
                    ))
        except Exception as e:
            logger.debug(f"Search request failed: {e}")

        return candidates

    def _search_court_announcements(self, court_id: str, court_info: dict) -> List[DateCandidate]:
        """
        Search for official court announcements about CM/ECF.

        Targets court websites' news/announcements sections.
        """
        candidates = []
        base_url = court_info.get('url', '')

        if not base_url:
            return candidates

        # Common paths for court announcements
        announcement_paths = [
            "/news",
            "/announcements",
            "/press-releases",
            "/cmecf/news",
            "/ecf/news",
            "/about/news",
        ]

        for path in announcement_paths[:2]:  # Limit to reduce requests
            url = base_url.rstrip('/') + path
            try:
                response = self._make_request(url)
                if response and response.status_code == 200:
                    # Look for CM/ECF related content
                    text = response.text.lower()
                    if 'cm/ecf' in text or 'electronic filing' in text or 'ecf' in text:
                        dates = self.date_extractor.extract_dates(response.text)
                        for date_info in dates[:2]:
                            candidates.append(DateCandidate(
                                date=date_info['date'],
                                confidence=min(date_info['confidence'], 3.5),
                                source_type="court_announcement",
                                source_url=url,
                                context=date_info.get('context', ''),
                                extraction_method="announcement_page"
                            ))
            except Exception as e:
                logger.debug(f"Announcement search failed for {url}: {e}")

        return candidates

    def _deduplicate_candidates(self, candidates: List[DateCandidate]) -> List[DateCandidate]:
        """Remove duplicate date candidates, keeping highest confidence."""
        seen = {}
        for c in candidates:
            key = c.date.isoformat() if c.date else str(c)
            if key not in seen or c.confidence > seen[key].confidence:
                seen[key] = c
        return list(seen.values())
