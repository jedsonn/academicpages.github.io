# research-radar/sources/arxiv.py
"""
arXiv crawler using their Atom feed API.
"""
import feedparser
from datetime import datetime, timedelta
from typing import List
import re

import sys
sys.path.insert(0, '..')
from sources.base import BaseCrawler
from config import Paper


class ArxivCrawler(BaseCrawler):
    """Crawls arXiv for new papers in specified categories."""

    BASE_URL = "http://export.arxiv.org/api/query"

    CATEGORY_NAMES = {
        "q-fin": "Quantitative Finance",
        "econ": "Economics",
        "stat.ML": "Machine Learning",
    }

    def __init__(self, source_id: str, category: str = "q-fin"):
        super().__init__(source_id, f"arXiv {self.CATEGORY_NAMES.get(category, category)}")
        self.category = category
        self.rate_limit = 3.0  # arXiv asks for 3 seconds between requests

    def _build_query_url(self, max_results: int = 100) -> str:
        return (
            f"{self.BASE_URL}"
            f"?search_query=cat:{self.category}"
            f"&sortBy=submittedDate"
            f"&sortOrder=descending"
            f"&max_results={max_results}"
        )

    def _parse_arxiv_id(self, entry_id: str) -> str:
        match = re.search(r'abs/(.+)$', entry_id)
        if match:
            return match.group(1)
        return entry_id.split('/')[-1]

    def _parse_date(self, date_tuple) -> datetime:
        if date_tuple:
            return datetime(*date_tuple[:6])
        return datetime.now()

    def fetch_papers(self, since: datetime = None) -> List[Paper]:
        if since is None:
            since = datetime.now() - timedelta(days=7)

        url = self._build_query_url(max_results=100)
        print(f"[{self.source_id}] Fetching from arXiv category: {self.category}")

        try:
            response = self._safe_request(url)
            feed = feedparser.parse(response.content)
        except Exception as e:
            print(f"[{self.source_id}] Failed to fetch arXiv: {e}")
            return []

        papers = []
        for entry in feed.entries:
            published = self._parse_date(entry.get('published_parsed'))

            if published < since:
                continue

            categories = [tag.term for tag in entry.get('tags', [])]
            title = re.sub(r'\s+', ' ', entry.title).strip()
            abstract = re.sub(r'\s+', ' ', entry.summary).strip()
            authors = [author.name for author in entry.get('authors', [])]

            paper = Paper(
                external_id=f"arxiv-{self._parse_arxiv_id(entry.id)}",
                source=self.source_id,
                title=title,
                authors=authors,
                abstract=abstract,
                url=entry.link,
                published_at=published,
                topics=categories,
                metadata={
                    "arxiv_id": self._parse_arxiv_id(entry.id),
                    "categories": categories,
                }
            )
            papers.append(paper)

        print(f"[{self.source_id}] Found {len(papers)} papers since {since.date()}")
        return papers
