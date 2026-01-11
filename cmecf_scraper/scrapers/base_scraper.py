"""
Base scraper class with common functionality.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from utils.rate_limiter import RateLimiter
from utils.user_agent import UserAgentRotator
from models.court_data import ScrapingResult, CourtData, DateCandidate
from config import REQUEST_TIMEOUT, MAX_RETRIES, RETRY_BACKOFF

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        user_agent_rotator: Optional[UserAgentRotator] = None,
        timeout: int = REQUEST_TIMEOUT
    ):
        """
        Initialize base scraper.

        Args:
            rate_limiter: Rate limiter instance
            user_agent_rotator: User agent rotator instance
            timeout: Request timeout in seconds
        """
        self.rate_limiter = rate_limiter or RateLimiter()
        self.ua_rotator = user_agent_rotator or UserAgentRotator()
        self.timeout = timeout
        self.session = requests.Session()

    def _make_request(
        self,
        url: str,
        method: str = 'GET',
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """
        Make an HTTP request with rate limiting and retry logic.

        Args:
            url: URL to request
            method: HTTP method
            headers: Optional additional headers
            **kwargs: Additional arguments for requests

        Returns:
            Tuple of (response, error_message)
        """
        # Wait for rate limiter
        self.rate_limiter.wait(url)

        # Build headers
        request_headers = self.ua_rotator.get_headers(headers)

        # Retry loop
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=request_headers,
                    timeout=self.timeout,
                    **kwargs
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    wait_time = self.rate_limiter.handle_429(url, int(retry_after) if retry_after else None)
                    logger.warning(f"Rate limited on {url}, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue

                # Success
                if response.status_code == 200:
                    logger.debug(f"Successfully fetched {url}")
                    return response, None

                # Client errors (don't retry)
                if 400 <= response.status_code < 500:
                    error_msg = f"Client error {response.status_code} for {url}"
                    logger.warning(error_msg)
                    return response, error_msg

                # Server errors (retry)
                if response.status_code >= 500:
                    last_error = f"Server error {response.status_code}"
                    logger.warning(f"{last_error} for {url}, attempt {attempt + 1}/{MAX_RETRIES}")
                    if attempt < MAX_RETRIES - 1:
                        wait_time = self.rate_limiter.get_retry_delay(attempt)
                        time.sleep(wait_time)
                    continue

                return response, None

            except Timeout:
                last_error = "Request timeout"
                logger.warning(f"Timeout for {url}, attempt {attempt + 1}/{MAX_RETRIES}")
            except ConnectionError as e:
                last_error = f"Connection error: {str(e)}"
                logger.warning(f"Connection error for {url}, attempt {attempt + 1}/{MAX_RETRIES}")
            except RequestException as e:
                last_error = f"Request error: {str(e)}"
                logger.error(f"Request error for {url}: {e}")

            # Wait before retry
            if attempt < MAX_RETRIES - 1:
                wait_time = self.rate_limiter.get_retry_delay(attempt)
                time.sleep(wait_time)

        return None, last_error or "Max retries exceeded"

    def fetch_url(self, url: str) -> ScrapingResult:
        """
        Fetch a URL and return a ScrapingResult.

        Args:
            url: URL to fetch

        Returns:
            ScrapingResult with status and content
        """
        response, error = self._make_request(url)

        if error and response is None:
            return ScrapingResult(
                url=url,
                status_code=0,
                success=False,
                error_message=error
            )

        if response is None:
            return ScrapingResult(
                url=url,
                status_code=0,
                success=False,
                error_message="No response received"
            )

        content_type = response.headers.get('Content-Type', '')

        return ScrapingResult(
            url=url,
            status_code=response.status_code,
            success=response.status_code == 200,
            content_type=content_type,
            error_message=error
        )

    def fetch_html(self, url: str) -> Tuple[Optional[str], ScrapingResult]:
        """
        Fetch HTML content from a URL.

        Args:
            url: URL to fetch

        Returns:
            Tuple of (html_content, ScrapingResult)
        """
        response, error = self._make_request(url)

        if response is None:
            return None, ScrapingResult(
                url=url,
                status_code=0,
                success=False,
                error_message=error
            )

        result = ScrapingResult(
            url=url,
            status_code=response.status_code,
            success=response.status_code == 200,
            content_type=response.headers.get('Content-Type', ''),
            error_message=error
        )

        if response.status_code == 200:
            return response.text, result

        return None, result

    def fetch_pdf(self, url: str) -> Tuple[Optional[bytes], ScrapingResult]:
        """
        Fetch PDF content from a URL.

        Args:
            url: URL to fetch

        Returns:
            Tuple of (pdf_bytes, ScrapingResult)
        """
        response, error = self._make_request(url)

        if response is None:
            return None, ScrapingResult(
                url=url,
                status_code=0,
                success=False,
                error_message=error
            )

        result = ScrapingResult(
            url=url,
            status_code=response.status_code,
            success=response.status_code == 200,
            content_type=response.headers.get('Content-Type', ''),
            error_message=error
        )

        if response.status_code == 200:
            return response.content, result

        return None, result

    def get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc

    @abstractmethod
    def scrape(self, court_data: CourtData) -> CourtData:
        """
        Scrape CM/ECF implementation date for a court.

        Args:
            court_data: CourtData object to populate

        Returns:
            Updated CourtData object
        """
        pass

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
