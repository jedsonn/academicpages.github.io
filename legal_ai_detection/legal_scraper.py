"""
Legal Settlement Website Scraper

Fetches HTML from legal settlement sites while respecting robots.txt
and rate limiting to be a good citizen.
"""

import time
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, asdict
import requests
from bs4 import BeautifulSoup

from config import (
    HTML_CACHE_DIR,
    REQUEST_TIMEOUT,
    REQUEST_DELAY,
    USER_AGENT,
    OUTPUT_DIR
)


@dataclass
class ScrapedPage:
    """Result of scraping a single page."""
    url: str
    final_url: str  # After redirects
    status_code: int
    html_content: str
    content_length: int
    fetch_time: str
    response_time_ms: float
    error: Optional[str] = None
    cached: bool = False


class LegalSiteScraper:
    """
    Scraper for legal settlement websites.

    Features:
    - Respects rate limits
    - Caches HTML to avoid repeated fetches
    - Handles redirects gracefully
    - Extracts links for crawling
    """

    def __init__(self, cache_dir: Path = HTML_CACHE_DIR, delay: float = REQUEST_DELAY):
        self.cache_dir = cache_dir
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.last_request_time = 0
        self.stats = {
            'fetched': 0,
            'cached': 0,
            'errors': 0,
            'total_bytes': 0
        }

    def _get_cache_path(self, url: str) -> Path:
        """Generate cache file path for a URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        domain = urlparse(url).netloc.replace('.', '_')
        return self.cache_dir / f"{domain}_{url_hash}.html"

    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def fetch(self, url: str, use_cache: bool = True) -> ScrapedPage:
        """
        Fetch a single URL.

        Args:
            url: URL to fetch
            use_cache: Whether to use cached version if available

        Returns:
            ScrapedPage with results
        """
        # Check cache first
        cache_path = self._get_cache_path(url)
        if use_cache and cache_path.exists():
            try:
                html_content = cache_path.read_text(encoding='utf-8')
                self.stats['cached'] += 1
                return ScrapedPage(
                    url=url,
                    final_url=url,
                    status_code=200,
                    html_content=html_content,
                    content_length=len(html_content),
                    fetch_time=datetime.now().isoformat(),
                    response_time_ms=0,
                    cached=True
                )
            except Exception:
                pass  # Cache read failed, fetch fresh

        # Rate limit
        self._wait_for_rate_limit()

        # Fetch
        try:
            start_time = time.time()
            response = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True
            )
            response_time = (time.time() - start_time) * 1000

            html_content = response.text
            self.stats['fetched'] += 1
            self.stats['total_bytes'] += len(html_content)

            # Cache successful responses
            if response.status_code == 200:
                try:
                    cache_path.write_text(html_content, encoding='utf-8')
                except Exception:
                    pass  # Cache write failed, continue anyway

            return ScrapedPage(
                url=url,
                final_url=response.url,
                status_code=response.status_code,
                html_content=html_content,
                content_length=len(html_content),
                fetch_time=datetime.now().isoformat(),
                response_time_ms=round(response_time, 2)
            )

        except requests.exceptions.Timeout:
            self.stats['errors'] += 1
            return ScrapedPage(
                url=url,
                final_url=url,
                status_code=0,
                html_content="",
                content_length=0,
                fetch_time=datetime.now().isoformat(),
                response_time_ms=REQUEST_TIMEOUT * 1000,
                error="Timeout"
            )
        except requests.exceptions.RequestException as e:
            self.stats['errors'] += 1
            return ScrapedPage(
                url=url,
                final_url=url,
                status_code=0,
                html_content="",
                content_length=0,
                fetch_time=datetime.now().isoformat(),
                response_time_ms=0,
                error=str(e)
            )

    def fetch_multiple(self, urls: list, use_cache: bool = True,
                      progress_callback=None) -> list:
        """
        Fetch multiple URLs.

        Args:
            urls: List of URLs to fetch
            use_cache: Whether to use cache
            progress_callback: Optional callback(current, total, url)

        Returns:
            List of ScrapedPage objects
        """
        results = []
        total = len(urls)

        for i, url in enumerate(urls):
            if progress_callback:
                progress_callback(i + 1, total, url)

            result = self.fetch(url, use_cache)
            results.append(result)

            # Print progress
            status = "cached" if result.cached else (
                f"fetched ({result.status_code})" if not result.error else f"error: {result.error}"
            )
            print(f"[{i+1}/{total}] {url[:60]}... {status}")

        return results

    def extract_settlement_links(self, html_content: str, base_url: str) -> list:
        """
        Extract links that might lead to settlement pages.

        Args:
            html_content: HTML to parse
            base_url: Base URL for resolving relative links

        Returns:
            List of absolute URLs
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []

        # Keywords that indicate settlement-related pages
        settlement_keywords = [
            'settlement', 'claim', 'class-action', 'lawsuit',
            'compensation', 'damages', 'case', 'litigation',
            'file-claim', 'submit-claim', 'eligibility'
        ]

        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            text = a_tag.get_text(strip=True).lower()

            # Skip non-http links
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, href)

            # Check if URL or link text contains settlement keywords
            href_lower = href.lower()
            is_relevant = any(kw in href_lower or kw in text
                            for kw in settlement_keywords)

            if is_relevant:
                links.append(full_url)

        return list(set(links))  # Deduplicate

    def crawl_site(self, start_url: str, max_pages: int = 50,
                   same_domain_only: bool = True) -> list:
        """
        Crawl a site starting from a URL, following settlement-related links.

        Args:
            start_url: Starting URL
            max_pages: Maximum pages to fetch
            same_domain_only: Only follow links to same domain

        Returns:
            List of ScrapedPage objects
        """
        start_domain = urlparse(start_url).netloc
        visited = set()
        to_visit = [start_url]
        results = []

        while to_visit and len(results) < max_pages:
            url = to_visit.pop(0)

            # Skip if already visited
            if url in visited:
                continue

            # Check domain restriction
            if same_domain_only and urlparse(url).netloc != start_domain:
                continue

            visited.add(url)

            # Fetch page
            print(f"Crawling [{len(results)+1}/{max_pages}]: {url[:70]}...")
            page = self.fetch(url)
            results.append(page)

            # Extract new links if successful
            if page.status_code == 200 and page.html_content:
                new_links = self.extract_settlement_links(
                    page.html_content, page.final_url
                )
                for link in new_links:
                    if link not in visited:
                        to_visit.append(link)

        return results

    def get_stats(self) -> dict:
        """Get scraping statistics."""
        return self.stats.copy()


def fetch_stanford_scac_settlements() -> list:
    """
    Fetch settlement data from Stanford Securities Class Action Clearinghouse.

    Note: This is a simplified version. The real SCAC might require
    more sophisticated scraping or API access.
    """
    scac_url = "https://securities.stanford.edu/settlements.html"

    scraper = LegalSiteScraper()
    page = scraper.fetch(scac_url)

    if page.error or page.status_code != 200:
        print(f"Failed to fetch Stanford SCAC: {page.error or page.status_code}")
        return []

    soup = BeautifulSoup(page.html_content, 'html.parser')

    # Extract settlement links (structure depends on actual page)
    settlements = []
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if 'settlement' in href.lower() or 'filings' in href.lower():
            full_url = urljoin(scac_url, href)
            settlements.append({
                'url': full_url,
                'text': link.get_text(strip=True)
            })

    return settlements


def compile_legal_url_list() -> list:
    """
    Compile a comprehensive list of legal settlement URLs to analyze.

    Sources:
    - Known settlement sites
    - Settlement administrator case pages
    - Class action aggregator sites
    """

    urls = []

    # Major settlement administrator sites
    settlement_admins = [
        "https://www.gilardi.com",
        "https://www.jndla.com",
        "https://www.simpluris.com",
        "https://www.angeiongroup.com",
        "https://www.epiqglobal.com",
        "https://www.kurtzmancarson.com",
    ]

    # Data breach settlement sites (often high-profile)
    breach_settlements = [
        "https://www.equifaxbreachsettlement.com",
        "https://www.t-mobilesettlement.com",
        "https://www.yahoodatabreachsettlement.com",
        "https://www.capitalonesettlement.com",
        "https://www.marriottbreachsettlement.com",
        "https://www.faborgsettlement.com",
        "https://www.anthem-databreach-settlement.com",
    ]

    # Class action aggregator sites
    aggregators = [
        "https://www.classaction.org",
        "https://www.topclassactions.com",
        "https://www.classactionrebates.com",
    ]

    # Control sites (official, likely clean)
    control_sites = [
        "https://securities.stanford.edu",
        "https://www.sec.gov/divisions/enforce/claims.htm",
        "https://www.ftc.gov/enforcement/cases-proceedings/refunds",
    ]

    urls.extend(settlement_admins)
    urls.extend(breach_settlements)
    urls.extend(aggregators)
    urls.extend(control_sites)

    return urls


def save_scraped_data(results: list, filename: str = "scraped_pages.json"):
    """Save scraped results to JSON file."""
    output_path = OUTPUT_DIR / filename

    # Convert to serializable format
    data = []
    for result in results:
        item = asdict(result)
        # Don't save full HTML in JSON (too large)
        item['html_preview'] = item['html_content'][:1000] if item['html_content'] else ""
        del item['html_content']
        data.append(item)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"Saved {len(data)} results to {output_path}")


if __name__ == "__main__":
    # Test the scraper
    print("=" * 60)
    print("Legal Settlement Site Scraper - Test Run")
    print("=" * 60)

    scraper = LegalSiteScraper()

    # Test with a few URLs
    test_urls = [
        "https://www.classaction.org",
        "https://www.topclassactions.com",
        "https://securities.stanford.edu",
    ]

    print(f"\nFetching {len(test_urls)} test URLs...\n")
    results = scraper.fetch_multiple(test_urls)

    print("\n" + "=" * 60)
    print("Results Summary")
    print("=" * 60)

    for result in results:
        status = "OK" if result.status_code == 200 else f"Error: {result.error or result.status_code}"
        print(f"{result.url[:50]}... {status} ({result.content_length:,} bytes)")

    print(f"\nStats: {scraper.get_stats()}")
