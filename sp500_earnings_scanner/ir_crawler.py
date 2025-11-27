"""
Investor Relations (IR) website crawler module.

This module handles:
- BFS crawling of company IR websites
- Filtering for earnings-related pages
- Respecting robots.txt and rate limits
- Collecting HTML content for analysis
"""

import re
import time
import random
import logging
from datetime import datetime
from typing import Generator
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from collections import deque

import requests
from bs4 import BeautifulSoup

from config import (
    IR_USER_AGENT,
    IR_MAX_DEPTH,
    IR_MAX_PAGES_PER_DOMAIN,
    IR_REQUEST_TIMEOUT,
    IR_MIN_DELAY,
    IR_MAX_DELAY,
    IR_OBEY_ROBOTS_TXT,
    IR_URL_KEYWORDS,
    EARNINGS_KEYWORDS,
    SKIP_EXTENSIONS,
)

logger = logging.getLogger(__name__)


@dataclass
class CrawledPage:
    """Represents a crawled IR page."""
    ticker: str
    company_name: str
    ir_root_url: str
    page_url: str
    title: str
    html_raw: str
    crawl_timestamp: str
    depth: int
    is_earnings_related: bool = False


@dataclass
class CrawlState:
    """Tracks crawl state for a domain."""
    visited: set = field(default_factory=set)
    queue: deque = field(default_factory=deque)  # (url, depth, priority)
    pages_crawled: int = 0
    pages_collected: list = field(default_factory=list)


class IRCrawler:
    """
    BFS crawler for investor relations websites.

    Crawls company IR sites looking for earnings-related content,
    respecting robots.txt and rate limits.
    """

    def __init__(
        self,
        max_depth: int = IR_MAX_DEPTH,
        max_pages: int = IR_MAX_PAGES_PER_DOMAIN,
        user_agent: str = IR_USER_AGENT,
        obey_robots: bool = IR_OBEY_ROBOTS_TXT,
    ):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.user_agent = user_agent
        self.obey_robots = obey_robots

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

        self._last_request_time = 0
        self._robots_cache: dict[str, RobotFileParser] = {}

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        min_wait = IR_MIN_DELAY + random.uniform(0, IR_MAX_DELAY - IR_MIN_DELAY)
        if elapsed < min_wait:
            time.sleep(min_wait - elapsed)
        self._last_request_time = time.time()

    def _get_robots_parser(self, base_url: str) -> RobotFileParser | None:
        """
        Get or fetch robots.txt parser for a domain.

        Args:
            base_url: Base URL of the site

        Returns:
            RobotFileParser or None if not available
        """
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        if robots_url in self._robots_cache:
            return self._robots_cache[robots_url]

        try:
            self._rate_limit()
            response = self.session.get(robots_url, timeout=10)
            if response.status_code == 200:
                rp = RobotFileParser()
                rp.set_url(robots_url)
                rp.parse(response.text.splitlines())
                self._robots_cache[robots_url] = rp
                return rp
        except requests.RequestException:
            pass

        self._robots_cache[robots_url] = None
        return None

    def _can_fetch(self, url: str) -> bool:
        """
        Check if URL can be fetched according to robots.txt.

        Args:
            url: URL to check

        Returns:
            True if allowed to fetch
        """
        if not self.obey_robots:
            return True

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._get_robots_parser(base_url)

        if rp is None:
            return True  # No robots.txt = allowed

        return rp.can_fetch(self.user_agent, url)

    def _normalize_url(self, url: str, base_url: str = "") -> str | None:
        """
        Normalize and validate a URL.

        Args:
            url: URL to normalize
            base_url: Base URL for resolving relative URLs

        Returns:
            Normalized URL or None if invalid
        """
        if not url:
            return None

        # Skip non-HTTP URLs
        if url.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
            return None

        # Resolve relative URLs
        if base_url:
            url = urljoin(base_url, url)

        # Parse and validate
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return None

        # Check for skip extensions
        path_lower = parsed.path.lower()
        for ext in SKIP_EXTENSIONS:
            if path_lower.endswith(ext):
                return None

        # Reconstruct clean URL (remove fragment)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            clean_url += f"?{parsed.query}"

        return clean_url

    def _is_same_domain(self, url: str, base_url: str) -> bool:
        """
        Check if URL is on the same domain as base URL.

        Args:
            url: URL to check
            base_url: Base/root URL

        Returns:
            True if same domain
        """
        url_parsed = urlparse(url)
        base_parsed = urlparse(base_url)

        # Allow subdomains (e.g., investor.apple.com matches apple.com)
        url_domain = url_parsed.netloc.lower()
        base_domain = base_parsed.netloc.lower()

        # Exact match
        if url_domain == base_domain:
            return True

        # Subdomain match (e.g., investor.company.com for company.com)
        if url_domain.endswith("." + base_domain):
            return True

        # Check if base_domain is a subdomain and url_domain is the parent or sibling
        base_parts = base_domain.split(".")
        url_parts = url_domain.split(".")

        # Get root domain (last 2 parts for most TLDs)
        if len(base_parts) >= 2 and len(url_parts) >= 2:
            base_root = ".".join(base_parts[-2:])
            url_root = ".".join(url_parts[-2:])
            if base_root == url_root:
                return True

        return False

    def _has_earnings_keywords(self, text: str) -> bool:
        """Check if text contains earnings-related keywords."""
        if not text:
            return False
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in EARNINGS_KEYWORDS)

    def _url_has_ir_keywords(self, url: str) -> bool:
        """Check if URL path contains IR-related keywords."""
        parsed = urlparse(url)
        path_lower = parsed.path.lower()
        return any(kw in path_lower for kw in IR_URL_KEYWORDS)

    def _calculate_priority(self, url: str) -> int:
        """
        Calculate crawl priority for URL (lower = higher priority).

        Args:
            url: URL to evaluate

        Returns:
            Priority value (0-100)
        """
        priority = 50

        path_lower = urlparse(url).path.lower()

        # High priority for earnings-related URLs
        for kw in ["earnings", "results", "quarterly", "financial"]:
            if kw in path_lower:
                priority -= 20
                break

        # Medium priority for news/press releases
        for kw in ["news", "press", "release", "announcement"]:
            if kw in path_lower:
                priority -= 10
                break

        # Lower priority for generic investor pages
        if "investor" in path_lower or "/ir/" in path_lower:
            priority -= 5

        return max(0, priority)

    def _fetch_page(self, url: str) -> tuple[str, str] | None:
        """
        Fetch a page and return its HTML content.

        Args:
            url: URL to fetch

        Returns:
            Tuple of (html_content, final_url) or None if failed
        """
        if not self._can_fetch(url):
            logger.debug(f"Blocked by robots.txt: {url}")
            return None

        try:
            self._rate_limit()
            response = self.session.get(
                url,
                timeout=IR_REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            # Check for HTML content
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return None

            response.raise_for_status()
            return response.text, response.url

        except requests.RequestException as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return None

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """
        Extract valid links from page.

        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links

        Returns:
            List of normalized URLs
        """
        links = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            normalized = self._normalize_url(href, base_url)

            if normalized:
                links.append(normalized)

        return links

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        h1_tag = soup.find("h1")
        if h1_tag:
            return h1_tag.get_text(strip=True)

        return ""

    def _is_earnings_page(self, url: str, title: str, text: str) -> bool:
        """
        Determine if page is earnings-related.

        Args:
            url: Page URL
            title: Page title
            text: Page text content

        Returns:
            True if earnings-related
        """
        # Check URL
        if self._url_has_ir_keywords(url):
            return True

        # Check title
        if self._has_earnings_keywords(title):
            return True

        # Check content (with minimum threshold)
        text_lower = text.lower()
        keyword_count = sum(
            1 for kw in EARNINGS_KEYWORDS
            if kw.lower() in text_lower
        )

        return keyword_count >= 3

    def crawl_ir_site(
        self,
        ir_root_url: str,
        ticker: str,
        company_name: str,
    ) -> Generator[CrawledPage, None, None]:
        """
        Crawl an investor relations website.

        Args:
            ir_root_url: Root URL of IR site
            ticker: Stock ticker
            company_name: Company name

        Yields:
            CrawledPage objects for earnings-related pages
        """
        # Initialize crawl state
        state = CrawlState()
        state.queue.append((ir_root_url, 0, 0))  # (url, depth, priority)

        logger.info(f"Starting crawl of {ir_root_url} for {ticker}")

        while state.queue and state.pages_crawled < self.max_pages:
            # Sort queue by priority (lower = higher priority)
            sorted_queue = sorted(state.queue, key=lambda x: (x[2], x[1]))
            state.queue = deque(sorted_queue)

            url, depth, priority = state.queue.popleft()

            # Skip if already visited
            if url in state.visited:
                continue

            # Skip if too deep
            if depth > self.max_depth:
                continue

            state.visited.add(url)

            # Fetch page
            result = self._fetch_page(url)
            if not result:
                continue

            html_content, final_url = result
            state.pages_crawled += 1

            # Parse HTML
            soup = BeautifulSoup(html_content, "lxml")
            title = self._extract_title(soup)
            text_content = soup.get_text(" ", strip=True)

            # Check if earnings-related
            is_earnings = self._is_earnings_page(url, title, text_content)

            # Create page object
            page = CrawledPage(
                ticker=ticker,
                company_name=company_name,
                ir_root_url=ir_root_url,
                page_url=final_url,
                title=title,
                html_raw=html_content,
                crawl_timestamp=datetime.utcnow().isoformat(),
                depth=depth,
                is_earnings_related=is_earnings,
            )

            if is_earnings:
                logger.info(f"Found earnings page: {final_url}")
                yield page

            # Extract and enqueue links
            links = self._extract_links(soup, final_url)

            for link in links:
                if link in state.visited:
                    continue

                # Only follow same-domain links
                if not self._is_same_domain(link, ir_root_url):
                    continue

                link_priority = self._calculate_priority(link)
                state.queue.append((link, depth + 1, link_priority))

        logger.info(
            f"Finished crawl of {ticker}: "
            f"{state.pages_crawled} pages crawled"
        )

    def crawl_ir_site_all(
        self,
        ir_root_url: str,
        ticker: str,
        company_name: str,
    ) -> list[CrawledPage]:
        """
        Crawl IR site and return all earnings-related pages.

        Args:
            ir_root_url: Root URL of IR site
            ticker: Stock ticker
            company_name: Company name

        Returns:
            List of CrawledPage objects
        """
        return list(self.crawl_ir_site(ir_root_url, ticker, company_name))


def crawl_firm_ir(
    ir_root_url: str,
    ticker: str,
    company_name: str,
    max_depth: int | None = None,
    max_pages: int | None = None,
) -> list[CrawledPage]:
    """
    Convenience function to crawl a firm's IR site.

    Args:
        ir_root_url: Root URL of IR site
        ticker: Stock ticker
        company_name: Company name
        max_depth: Maximum crawl depth (default from config)
        max_pages: Maximum pages per domain (default from config)

    Returns:
        List of CrawledPage objects
    """
    crawler = IRCrawler(
        max_depth=max_depth or IR_MAX_DEPTH,
        max_pages=max_pages or IR_MAX_PAGES_PER_DOMAIN,
    )

    return crawler.crawl_ir_site_all(ir_root_url, ticker, company_name)


if __name__ == "__main__":
    # Test with Apple IR site
    logging.basicConfig(level=logging.INFO)

    pages = crawl_firm_ir(
        ir_root_url="https://investor.apple.com",
        ticker="AAPL",
        company_name="Apple Inc.",
        max_pages=20,  # Limit for testing
    )

    print(f"\nFound {len(pages)} earnings-related pages")
    for page in pages[:5]:
        print(f"  - {page.title[:50]}... ({page.page_url})")
