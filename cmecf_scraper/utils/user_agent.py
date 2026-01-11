"""
User agent rotation for web scraping.
"""

import random
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# Default user agents
DEFAULT_USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]


class UserAgentRotator:
    """Rotate user agents for web requests."""

    def __init__(self, user_agents: Optional[List[str]] = None, random_order: bool = True):
        """
        Initialize user agent rotator.

        Args:
            user_agents: List of user agents to use. If None, uses defaults.
            random_order: If True, randomize order; if False, use round-robin.
        """
        self.user_agents = user_agents or DEFAULT_USER_AGENTS.copy()
        self.random_order = random_order
        self._index = 0

        if random_order:
            random.shuffle(self.user_agents)

    def get(self) -> str:
        """Get the next user agent."""
        if self.random_order:
            return random.choice(self.user_agents)
        else:
            ua = self.user_agents[self._index]
            self._index = (self._index + 1) % len(self.user_agents)
            return ua

    def get_headers(self, additional_headers: Optional[dict] = None) -> dict:
        """
        Get complete headers dict with user agent.

        Args:
            additional_headers: Additional headers to include

        Returns:
            Headers dictionary ready for requests
        """
        headers = {
            "User-Agent": self.get(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers

    def add_user_agent(self, user_agent: str) -> None:
        """Add a new user agent to the rotation."""
        if user_agent not in self.user_agents:
            self.user_agents.append(user_agent)

    def remove_user_agent(self, user_agent: str) -> None:
        """Remove a user agent from rotation."""
        if user_agent in self.user_agents and len(self.user_agents) > 1:
            self.user_agents.remove(user_agent)

    def reset(self) -> None:
        """Reset the rotator to initial state."""
        self._index = 0
        if self.random_order:
            random.shuffle(self.user_agents)
