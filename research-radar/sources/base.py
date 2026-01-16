# research-radar/sources/base.py
"""
Base crawler class that all source-specific crawlers inherit from.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List
import time
import requests

import sys
sys.path.insert(0, '..')
from config import Paper


class BaseCrawler(ABC):
    """Abstract base class for all paper crawlers."""

    def __init__(self, source_id: str, name: str):
        self.source_id = source_id
        self.name = name
        self.rate_limit = 1.0  # seconds between requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ResearchRadar/1.0 (Academic Research Aggregator)"
        })

    @abstractmethod
    def fetch_papers(self, since: datetime = None) -> List[Paper]:
        """Fetch papers from the source."""
        pass

    def _rate_limit_wait(self):
        """Wait to respect rate limits."""
        time.sleep(self.rate_limit)

    def _safe_request(self, url: str, **kwargs) -> requests.Response:
        """Make a request with error handling and rate limiting."""
        self._rate_limit_wait()
        try:
            response = self.session.get(url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"[{self.source_id}] Request failed for {url}: {e}")
            raise
