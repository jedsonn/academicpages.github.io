# research-radar/sources/arxiv.py
"""
arXiv crawler using their Atom feed API.
Uses BeautifulSoup for XML parsing (no feedparser dependency).
"""
from bs4 import BeautifulSoup
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

    def _parse_date(self, date_str: str) -> datetime:
        if not date_str:
            return datetime.now()
        try:
            # arXiv uses ISO format: 2025-01-15T12:00:00Z
            date_str = date_str.strip().replace('Z', '+00:00')
            return datetime.fromisoformat(date_str.replace('+00:00', ''))
        except ValueError:
            return datetime.now()

    def fetch_papers(self, since: datetime = None) -> List[Paper]:
        if since is None:
            since = datetime.now() - timedelta(days=7)

        url = self._build_query_url(max_results=100)
        print(f"[{self.source_id}] Fetching from arXiv category: {self.category}")

        try:
            response = self._safe_request(url)
            soup = BeautifulSoup(response.content, 'lxml-xml')
        except Exception as e:
            print(f"[{self.source_id}] Failed to fetch arXiv: {e}")
            return []

        papers = []
        entries = soup.find_all('entry')

        for entry in entries:
            # Parse published date
            published_elem = entry.find('published')
            published = self._parse_date(published_elem.text if published_elem else None)

            if published < since:
                continue

            # Get entry ID
            id_elem = entry.find('id')
            entry_id = id_elem.text if id_elem else ""

            # Get title
            title_elem = entry.find('title')
            title = re.sub(r'\s+', ' ', title_elem.text).strip() if title_elem else "Unknown"

            # Get abstract/summary
            summary_elem = entry.find('summary')
            abstract = re.sub(r'\s+', ' ', summary_elem.text).strip() if summary_elem else ""

            # Get authors
            authors = []
            for author in entry.find_all('author'):
                name_elem = author.find('name')
                if name_elem:
                    authors.append(name_elem.text)

            # Get categories
            categories = []
            for category in entry.find_all('category'):
                term = category.get('term')
                if term:
                    categories.append(term)

            # Get link
            link = ""
            for link_elem in entry.find_all('link'):
                if link_elem.get('type') == 'text/html':
                    link = link_elem.get('href', '')
                    break
            if not link:
                link_elem = entry.find('link')
                link = link_elem.get('href', '') if link_elem else f"https://arxiv.org/abs/{self._parse_arxiv_id(entry_id)}"

            paper = Paper(
                external_id=f"arxiv-{self._parse_arxiv_id(entry_id)}",
                source=self.source_id,
                title=title,
                authors=authors,
                abstract=abstract,
                url=link,
                published_at=published,
                topics=categories,
                metadata={
                    "arxiv_id": self._parse_arxiv_id(entry_id),
                    "categories": categories,
                }
            )
            papers.append(paper)

        print(f"[{self.source_id}] Found {len(papers)} papers since {since.date()}")
        return papers
