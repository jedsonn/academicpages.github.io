"""
HTML parser for extracting text and links from court websites.
"""

import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import logging

from bs4 import BeautifulSoup, NavigableString

logger = logging.getLogger(__name__)


class HTMLParser:
    """Parse HTML content from court websites."""

    # Tags to skip when extracting text
    SKIP_TAGS = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'iframe'}

    # Tags that indicate main content
    CONTENT_TAGS = {'main', 'article', 'section', 'div'}

    # IDs/classes that typically contain main content
    CONTENT_IDENTIFIERS = [
        'content', 'main', 'article', 'body-content', 'page-content',
        'main-content', 'primary', 'center', 'middle'
    ]

    def __init__(self, base_url: str = ""):
        """
        Initialize HTML parser.

        Args:
            base_url: Base URL for resolving relative links
        """
        self.base_url = base_url

    def parse(self, html: str) -> BeautifulSoup:
        """Parse HTML string into BeautifulSoup object."""
        return BeautifulSoup(html, 'lxml')

    def extract_text(self, html: str, include_all: bool = False) -> str:
        """
        Extract readable text from HTML.

        Args:
            html: Raw HTML string
            include_all: If True, include text from all elements; otherwise focus on main content

        Returns:
            Extracted text content
        """
        soup = self.parse(html)

        # Remove unwanted elements
        for tag in soup.find_all(self.SKIP_TAGS):
            tag.decompose()

        if not include_all:
            # Try to find main content area
            main_content = self._find_main_content(soup)
            if main_content:
                return self._get_text(main_content)

        return self._get_text(soup)

    def _find_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Find the main content area of the page."""
        # Try semantic tags first
        for tag_name in ['main', 'article']:
            element = soup.find(tag_name)
            if element:
                return element

        # Try common IDs and classes
        for identifier in self.CONTENT_IDENTIFIERS:
            element = soup.find(id=re.compile(identifier, re.I))
            if element:
                return element

            element = soup.find(class_=re.compile(identifier, re.I))
            if element:
                return element

        return None

    def _get_text(self, element) -> str:
        """Get clean text from an element."""
        if element is None:
            return ""

        # Get text with proper spacing
        text = element.get_text(separator=' ', strip=True)

        # Clean up excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)

        return text.strip()

    def extract_links(self, html: str, filter_pattern: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        Extract links from HTML.

        Args:
            html: Raw HTML string
            filter_pattern: Optional regex pattern to filter links

        Returns:
            List of (url, link_text) tuples
        """
        soup = self.parse(html)
        links = []

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            text = a_tag.get_text(strip=True)

            # Resolve relative URLs
            if self.base_url:
                href = urljoin(self.base_url, href)

            # Apply filter if provided
            if filter_pattern:
                if not re.search(filter_pattern, href, re.I) and not re.search(filter_pattern, text, re.I):
                    continue

            links.append((href, text))

        return links

    def extract_pdf_links(self, html: str) -> List[Tuple[str, str]]:
        """Extract all PDF links from HTML."""
        return self.extract_links(html, r'\.pdf($|\?)|/pdf/')

    def extract_order_links(self, html: str) -> List[Tuple[str, str]]:
        """Extract links that might be court orders."""
        pattern = r'order|rule|procedure|ecf|cm.ecf|electronic.fil'
        return self.extract_links(html, pattern)

    def find_cmecf_sections(self, html: str) -> List[str]:
        """
        Find sections of HTML that mention CM/ECF.

        Args:
            html: Raw HTML string

        Returns:
            List of HTML sections containing CM/ECF mentions
        """
        soup = self.parse(html)
        sections = []

        # Keywords to search for
        keywords = ['cm/ecf', 'cmecf', 'cm-ecf', 'electronic case filing',
                    'electronic filing', 'ecf system', 'e-filing']

        # Find all text nodes containing keywords
        for text_node in soup.find_all(string=True):
            text_lower = str(text_node).lower()
            for keyword in keywords:
                if keyword in text_lower:
                    # Get parent element's HTML
                    parent = text_node.parent
                    if parent and parent.name not in self.SKIP_TAGS:
                        # Go up to find a reasonable container
                        container = self._find_container(parent)
                        if container:
                            section_html = str(container)
                            if section_html not in sections:
                                sections.append(section_html)
                    break

        return sections

    def _find_container(self, element, max_levels: int = 3) -> Optional[BeautifulSoup]:
        """Find a reasonable container element for context."""
        current = element
        level = 0

        while current and level < max_levels:
            if current.name in {'div', 'section', 'article', 'p', 'li', 'td'}:
                # Check if it has substantial content
                text = self._get_text(current)
                if len(text) > 50:
                    return current

            current = current.parent
            level += 1

        return element

    def extract_tables(self, html: str) -> List[List[List[str]]]:
        """
        Extract all tables from HTML as nested lists.

        Args:
            html: Raw HTML string

        Returns:
            List of tables, each table is a list of rows, each row is a list of cell values
        """
        soup = self.parse(html)
        tables = []

        for table in soup.find_all('table'):
            table_data = []
            for row in table.find_all('tr'):
                row_data = []
                for cell in row.find_all(['td', 'th']):
                    row_data.append(cell.get_text(strip=True))
                if row_data:
                    table_data.append(row_data)
            if table_data:
                tables.append(table_data)

        return tables

    def extract_metadata(self, html: str) -> dict:
        """
        Extract metadata from HTML head.

        Returns:
            Dictionary with title, description, keywords, etc.
        """
        soup = self.parse(html)
        metadata = {}

        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True)

        # Meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name', meta.get('property', '')).lower()
            content = meta.get('content', '')

            if name in ['description', 'keywords', 'author']:
                metadata[name] = content
            elif name.startswith('og:'):
                metadata[name] = content

        return metadata

    def get_page_title(self, html: str) -> str:
        """Get the page title."""
        soup = self.parse(html)
        title = soup.find('title')
        if title:
            return title.get_text(strip=True)

        # Try h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        return ""
