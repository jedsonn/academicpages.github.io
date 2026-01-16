# research-radar/sources/nber.py
"""
NBER Working Papers crawler.
"""
import feedparser
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

        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            pass

        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            pass

        return datetime.now()

    def _extract_authors(self, entry) -> List[str]:
        authors = []

        if hasattr(entry, 'author'):
            author_str = entry.author
            authors = [a.strip() for a in re.split(r',\s*(?:and\s+)?', author_str) if a.strip()]

        if not authors and hasattr(entry, 'authors'):
            authors = [a.get('name', '') for a in entry.authors if a.get('name')]

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
            feed = feedparser.parse(response.content)
        except Exception as e:
            print(f"[{self.source_id}] Failed to fetch NBER: {e}")
            return []

        papers = []

        for entry in feed.entries:
            pub_date = None
            if hasattr(entry, 'published'):
                pub_date = self._parse_date(entry.published)
            elif hasattr(entry, 'updated'):
                pub_date = self._parse_date(entry.updated)

            if pub_date and pub_date < since:
                continue

            paper_id = self._extract_nber_id(entry.link if hasattr(entry, 'link') else entry.id)

            title = re.sub(r'\s+', ' ', entry.title).strip() if hasattr(entry, 'title') else "Unknown"
            abstract = ""
            if hasattr(entry, 'summary'):
                abstract = re.sub(r'<[^>]+>', '', entry.summary)
                abstract = re.sub(r'\s+', ' ', abstract).strip()

            paper = Paper(
                external_id=f"nber-{paper_id}",
                source=self.source_id,
                title=title,
                authors=self._extract_authors(entry),
                abstract=abstract,
                url=entry.link if hasattr(entry, 'link') else f"https://www.nber.org/papers/w{paper_id}",
                published_at=pub_date,
                metadata={"nber_id": paper_id}
            )
            papers.append(paper)

        print(f"[{self.source_id}] Found {len(papers)} papers since {since.date()}")
        return papers
