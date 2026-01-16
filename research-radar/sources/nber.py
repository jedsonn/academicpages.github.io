# research-radar/sources/nber.py
"""
NBER Working Papers crawler.
Uses BeautifulSoup for RSS parsing (no feedparser dependency).
"""
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from typing import List

import sys
sys.path.insert(0, '..')
from sources.base import BaseCrawler
from config import Paper


class NBERCrawler(BaseCrawler):
    """Crawls NBER for new working papers."""

    RSS_URL = "https://www.nber.org/rss/new.rss"

    def __init__(self, source_id: str = "nber"):
        super().__init__(source_id, "NBER Working Papers")

    def _parse_date(self, date_str: str) -> datetime:
        if not date_str:
            return datetime.now()

        date_str = date_str.strip()

        # Try common RSS date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Try to extract just the date part
        date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', date_str)
        if date_match:
            try:
                return datetime.strptime(date_match.group(1), "%d %b %Y")
            except ValueError:
                pass

        return datetime.now()

    def _extract_authors(self, description: str) -> List[str]:
        """Extract authors from description text."""
        authors = []

        # Look for "by Author1, Author2, and Author3" pattern
        by_match = re.search(r'by\s+(.+?)(?:\.|$)', description, re.IGNORECASE)
        if by_match:
            author_str = by_match.group(1)
            # Split by comma and "and"
            authors = [a.strip() for a in re.split(r',\s*(?:and\s+)?|\s+and\s+', author_str) if a.strip()]

        return authors

    def _extract_nber_id(self, url: str) -> str:
        match = re.search(r'w?(\d+)', url)
        return match.group(1) if match else url

    def fetch_papers(self, since: datetime = None) -> List[Paper]:
        if since is None:
            since = datetime.now() - timedelta(days=7)

        print(f"[{self.source_id}] Fetching from NBER RSS feed")

        try:
            response = self._safe_request(self.RSS_URL)
            soup = BeautifulSoup(response.content, 'lxml-xml')
        except Exception as e:
            print(f"[{self.source_id}] Failed to fetch NBER: {e}")
            return []

        papers = []
        items = soup.find_all('item')

        for item in items:
            # Parse date
            pub_date_elem = item.find('pubDate')
            pub_date = self._parse_date(pub_date_elem.text if pub_date_elem else None)

            if pub_date and pub_date < since:
                continue

            # Get link
            link_elem = item.find('link')
            link = link_elem.text.strip() if link_elem else ""

            # Get ID from link
            paper_id = self._extract_nber_id(link) if link else "unknown"

            # Get title
            title_elem = item.find('title')
            title = re.sub(r'\s+', ' ', title_elem.text).strip() if title_elem else "Unknown"

            # Get description (often contains abstract)
            desc_elem = item.find('description')
            description = ""
            if desc_elem:
                description = re.sub(r'<[^>]+>', '', desc_elem.text)  # Strip HTML
                description = re.sub(r'\s+', ' ', description).strip()

            # Extract authors from description or creator element
            authors = []
            creator_elem = item.find('dc:creator') or item.find('creator')
            if creator_elem:
                author_str = creator_elem.text
                authors = [a.strip() for a in re.split(r',\s*(?:and\s+)?|\s+and\s+', author_str) if a.strip()]

            if not authors and description:
                authors = self._extract_authors(description)

            paper = Paper(
                external_id=f"nber-{paper_id}",
                source=self.source_id,
                title=title,
                authors=authors,
                abstract=description,
                url=link if link else f"https://www.nber.org/papers/w{paper_id}",
                published_at=pub_date,
                metadata={"nber_id": paper_id}
            )
            papers.append(paper)

        print(f"[{self.source_id}] Found {len(papers)} papers since {since.date()}")
        return papers
