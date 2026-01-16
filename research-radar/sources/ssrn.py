# research-radar/sources/ssrn.py
"""
SSRN crawler for accounting and finance working papers.
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, '..')
from sources.base import BaseCrawler
from config import Paper


class SSRNCrawler(BaseCrawler):
    """Crawls SSRN for new working papers."""

    NETWORKS = {
        "accounting": "1733",
        "financial-economics": "1744",
        "corporate-governance": "3117",
    }

    RSS_URL = "https://papers.ssrn.com/sol3/Jeljour_results.cfm?form_name=journalBrowse&journal_id={network_id}&Network=no&lim=false&npage={page}&SortOrder=ab_approval_date"

    def __init__(self, source_id: str, network: str = "accounting"):
        network_id = self.NETWORKS.get(network, network)
        super().__init__(source_id, f"SSRN {network.replace('-', ' ').title()}")
        self.network_id = network_id
        self.network = network
        self.rate_limit = 2.0

    def _parse_ssrn_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None

        date_str = date_str.strip()
        formats = ["%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%m/%d/%Y"]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _extract_paper_id(self, url: str) -> Optional[str]:
        match = re.search(r'abstract[_=]?(\d+)', url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _fetch_paper_details(self, abstract_id: str) -> Optional[Paper]:
        url = f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={abstract_id}"

        try:
            response = self._safe_request(url)
            soup = BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"[{self.source_id}] Failed to fetch paper {abstract_id}: {e}")
            return None

        title_elem = soup.select_one('h1.title') or soup.select_one('h1')
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)

        abstract_elem = soup.select_one('.abstract-text') or soup.select_one('div.abstract')
        abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""

        authors = []
        author_elems = soup.select('.authors-list a') or soup.select('a[href*="author="]')
        for a in author_elems:
            name = a.get_text(strip=True)
            if name:
                authors.append(name)

        date_elem = soup.select_one('.abstract-date')
        pub_date = None
        if date_elem:
            date_text = date_elem.get_text()
            date_match = re.search(r'(?:Posted:|Last revised:)\s*(.+?)(?:\n|$)', date_text)
            if date_match:
                pub_date = self._parse_ssrn_date(date_match.group(1))

        return Paper(
            external_id=f"ssrn-{abstract_id}",
            source=self.source_id,
            title=title,
            authors=authors,
            abstract=abstract,
            url=url,
            published_at=pub_date,
            metadata={"ssrn_id": abstract_id, "network": self.network}
        )

    def fetch_papers(self, since: datetime = None) -> List[Paper]:
        if since is None:
            since = datetime.now() - timedelta(days=7)

        print(f"[{self.source_id}] Fetching SSRN papers from network: {self.network}")
        papers = []

        for page in range(1, 4):
            url = self.RSS_URL.format(network_id=self.network_id, page=page)

            try:
                response = self._safe_request(url)
                soup = BeautifulSoup(response.content, 'html.parser')
            except Exception as e:
                print(f"[{self.source_id}] Failed to fetch page {page}: {e}")
                break

            paper_links = soup.select('a[href*="abstract="]')

            if not paper_links:
                break

            for link in paper_links:
                href = link.get('href', '')
                abstract_id = self._extract_paper_id(href)

                if not abstract_id:
                    continue

                paper = self._fetch_paper_details(abstract_id)
                if paper:
                    if paper.published_at and paper.published_at < since:
                        print(f"[{self.source_id}] Reached older papers, stopping")
                        return papers
                    papers.append(paper)

            print(f"[{self.source_id}] Page {page}: {len(papers)} papers so far")

        print(f"[{self.source_id}] Found {len(papers)} papers since {since.date()}")
        return papers
