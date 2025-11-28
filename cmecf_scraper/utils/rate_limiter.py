"""
Rate limiter for web scraping.
Implements per-domain rate limiting with exponential backoff.
"""

import time
import threading
from collections import defaultdict
from urllib.parse import urlparse
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe rate limiter with per-domain tracking."""

    def __init__(self, default_delay: float = 2.5, max_retries: int = 3, backoff_factor: float = 2.0):
        """
        Initialize rate limiter.

        Args:
            default_delay: Default delay between requests to same domain (seconds)
            max_retries: Maximum retry attempts for failed requests
            backoff_factor: Multiplier for exponential backoff
        """
        self.default_delay = default_delay
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._last_request: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
        self._domain_delays: dict[str, float] = {}

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0]

    def get_delay(self, url: str) -> float:
        """Get the delay for a specific URL's domain."""
        domain = self._get_domain(url)
        return self._domain_delays.get(domain, self.default_delay)

    def set_domain_delay(self, url: str, delay: float) -> None:
        """Set a custom delay for a specific domain."""
        domain = self._get_domain(url)
        with self._lock:
            self._domain_delays[domain] = delay

    def wait(self, url: str) -> None:
        """
        Wait if necessary before making a request to the URL's domain.

        Args:
            url: The URL to be requested
        """
        domain = self._get_domain(url)
        delay = self.get_delay(url)

        with self._lock:
            last_time = self._last_request[domain]
            current_time = time.time()
            elapsed = current_time - last_time

            if elapsed < delay:
                wait_time = delay - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s for {domain}")
                time.sleep(wait_time)

            self._last_request[domain] = time.time()

    def record_request(self, url: str) -> None:
        """Record that a request was made to update timing."""
        domain = self._get_domain(url)
        with self._lock:
            self._last_request[domain] = time.time()

    def get_retry_delay(self, attempt: int) -> float:
        """
        Calculate retry delay using exponential backoff.

        Args:
            attempt: The current retry attempt (0-indexed)

        Returns:
            Delay in seconds before retrying
        """
        return self.default_delay * (self.backoff_factor ** attempt)

    def should_retry(self, attempt: int, status_code: Optional[int] = None) -> bool:
        """
        Determine if a request should be retried.

        Args:
            attempt: Current attempt number (0-indexed)
            status_code: HTTP status code (if available)

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_retries:
            return False

        # Retry on these status codes
        retryable_codes = {429, 500, 502, 503, 504}

        if status_code is not None:
            return status_code in retryable_codes

        return True

    def handle_429(self, url: str, retry_after: Optional[int] = None) -> float:
        """
        Handle 429 Too Many Requests response.

        Args:
            url: The URL that returned 429
            retry_after: Retry-After header value if present

        Returns:
            Time to wait before retrying
        """
        domain = self._get_domain(url)

        if retry_after:
            wait_time = float(retry_after)
        else:
            # Default to longer wait
            wait_time = self.default_delay * 4

        # Increase future delays for this domain
        with self._lock:
            current_delay = self._domain_delays.get(domain, self.default_delay)
            self._domain_delays[domain] = min(current_delay * 2, 60)  # Cap at 60 seconds

        logger.warning(f"Rate limited (429) for {domain}, waiting {wait_time}s")
        return wait_time


class AsyncRateLimiter:
    """Async-compatible rate limiter."""

    def __init__(self, default_delay: float = 2.5):
        self.default_delay = default_delay
        self._last_request: dict[str, float] = defaultdict(float)
        self._lock = None  # Will be asyncio.Lock()

    async def wait(self, url: str) -> None:
        """Async wait before making request."""
        import asyncio

        if self._lock is None:
            self._lock = asyncio.Lock()

        domain = urlparse(url).netloc

        async with self._lock:
            last_time = self._last_request[domain]
            current_time = time.time()
            elapsed = current_time - last_time

            if elapsed < self.default_delay:
                wait_time = self.default_delay - elapsed
                await asyncio.sleep(wait_time)

            self._last_request[domain] = time.time()
