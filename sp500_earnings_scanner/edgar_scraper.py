"""
SEC EDGAR 8-K earnings scraper module.

This module handles:
- Fetching company submissions from SEC EDGAR API
- Filtering for earnings-related 8-K filings
- Downloading 8-K documents and Exhibit 99.x files
- Extracting text from PDFs
"""

import re
import time
import random
import logging
from datetime import date
from typing import Any, Generator
from dataclasses import dataclass, field
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import (
    SEC_SUBMISSIONS_URL,
    SEC_ARCHIVES_URL,
    SEC_USER_AGENT,
    SEC_MIN_DELAY,
    SEC_MAX_DELAY,
    FILING_START_DATE,
    FILING_END_DATE,
    EARNINGS_KEYWORDS,
)

logger = logging.getLogger(__name__)


@dataclass
class Filing8K:
    """Represents an 8-K filing with its metadata and documents."""
    cik: str
    ticker: str
    company_name: str
    accession_number: str
    filing_date: str
    form: str
    primary_document: str
    primary_doc_description: str
    filing_url: str
    is_earnings_candidate: bool = False
    documents: list[dict] = field(default_factory=list)


@dataclass
class Document:
    """Represents a document within a filing."""
    cik: str
    ticker: str
    company_name: str
    accession_number: str
    filing_date: str
    form: str
    doc_type: str  # primary_8k, exhibit_99, etc.
    filename: str
    url: str
    description: str
    content: str = ""  # HTML or extracted text
    content_type: str = "html"  # html or pdf


class EdgarScraper:
    """
    Scraper for SEC EDGAR 8-K filings.

    Handles fetching submissions, filtering for earnings-related filings,
    and downloading documents with proper rate limiting and etiquette.
    """

    def __init__(
        self,
        start_date: date = FILING_START_DATE,
        end_date: date = FILING_END_DATE,
        user_agent: str = SEC_USER_AGENT,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        })
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        min_wait = SEC_MIN_DELAY + random.uniform(0, SEC_MAX_DELAY - SEC_MIN_DELAY)
        if elapsed < min_wait:
            time.sleep(min_wait - elapsed)
        self._last_request_time = time.time()

    def _fetch(self, url: str, max_retries: int = 3) -> requests.Response | None:
        """
        Fetch URL with rate limiting and retry logic.

        Args:
            url: URL to fetch
            max_retries: Maximum number of retry attempts

        Returns:
            Response object or None if all retries fail
        """
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {url} - {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return None

    def _format_cik(self, cik: str) -> str:
        """Format CIK to 10-digit zero-padded string."""
        return str(cik).zfill(10)

    def _strip_cik_zeros(self, cik: str) -> str:
        """Strip leading zeros from CIK for URL paths."""
        return str(int(cik))

    def _format_accession(self, accession: str, with_dashes: bool = True) -> str:
        """Format accession number with or without dashes."""
        clean = accession.replace("-", "")
        if with_dashes:
            # Format: 0000000000-00-000000
            return f"{clean[:10]}-{clean[10:12]}-{clean[12:]}"
        return clean

    def _is_earnings_keyword_match(self, text: str) -> bool:
        """Check if text contains any earnings-related keywords."""
        if not text:
            return False
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in EARNINGS_KEYWORDS)

    def fetch_company_submissions(self, cik: str) -> dict | None:
        """
        Fetch company submissions JSON from SEC EDGAR.

        Args:
            cik: Company CIK (will be zero-padded)

        Returns:
            Submissions data dict or None
        """
        formatted_cik = self._format_cik(cik)
        url = f"{SEC_SUBMISSIONS_URL}/CIK{formatted_cik}.json"

        logger.info(f"Fetching submissions for CIK {formatted_cik}")
        response = self._fetch(url)

        if response:
            return response.json()
        return None

    def filter_8k_filings(
        self,
        submissions: dict,
        cik: str,
        ticker: str,
        company_name: str,
    ) -> list[Filing8K]:
        """
        Filter submissions to 8-K filings within date range.

        Args:
            submissions: SEC submissions JSON data
            cik: Company CIK
            ticker: Stock ticker
            company_name: Company name

        Returns:
            List of Filing8K objects
        """
        filings = []

        if "filings" not in submissions or "recent" not in submissions["filings"]:
            logger.warning(f"No filings found for CIK {cik}")
            return filings

        recent = submissions["filings"]["recent"]

        # Get arrays
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])
        primary_descs = recent.get("primaryDocDescription", [])

        for i in range(len(forms)):
            # Filter for 8-K forms only
            if forms[i] != "8-K":
                continue

            # Parse filing date
            try:
                filing_date = date.fromisoformat(filing_dates[i])
            except (ValueError, IndexError):
                continue

            # Filter by date range
            if not (self.start_date <= filing_date <= self.end_date):
                continue

            accession = accessions[i] if i < len(accessions) else ""
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            primary_desc = primary_descs[i] if i < len(primary_descs) else ""

            # Build filing URL
            cik_stripped = self._strip_cik_zeros(cik)
            accession_no_dashes = self._format_accession(accession, with_dashes=False)
            filing_url = f"{SEC_ARCHIVES_URL}/{cik_stripped}/{accession_no_dashes}/"

            # Check if this is an earnings candidate based on description
            is_earnings = self._is_earnings_keyword_match(primary_desc) or \
                         self._is_earnings_keyword_match(primary_doc)

            filing = Filing8K(
                cik=cik,
                ticker=ticker,
                company_name=company_name,
                accession_number=accession,
                filing_date=filing_dates[i],
                form=forms[i],
                primary_document=primary_doc,
                primary_doc_description=primary_desc,
                filing_url=filing_url,
                is_earnings_candidate=is_earnings,
            )
            filings.append(filing)

        logger.info(f"Found {len(filings)} 8-K filings for {ticker} in date range")
        return filings

    def fetch_filing_index(self, filing: Filing8K) -> list[dict]:
        """
        Fetch and parse the filing index to get list of all documents.

        Args:
            filing: Filing8K object with filing_url

        Returns:
            List of document dicts with filename, description, type
        """
        # Try index.json first (more reliable)
        index_url = urljoin(filing.filing_url, "index.json")
        response = self._fetch(index_url)

        if response:
            try:
                index_data = response.json()
                documents = []
                for item in index_data.get("directory", {}).get("item", []):
                    doc = {
                        "filename": item.get("name", ""),
                        "description": item.get("description", ""),
                        "type": item.get("type", ""),
                        "size": item.get("size", ""),
                    }
                    documents.append(doc)
                return documents
            except (ValueError, KeyError):
                pass

        # Fallback to HTML index
        index_html_url = urljoin(filing.filing_url, f"{self._format_accession(filing.accession_number, False)}-index.html")
        response = self._fetch(index_html_url)

        if not response:
            # Try alternative index format
            response = self._fetch(filing.filing_url)

        if response:
            return self._parse_html_index(response.text)

        return []

    def _parse_html_index(self, html: str) -> list[dict]:
        """Parse HTML filing index page to extract document list."""
        documents = []
        soup = BeautifulSoup(html, "lxml")

        # Look for the document table
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows[1:]:  # Skip header
                cells = row.find_all("td")
                if len(cells) >= 3:
                    # Find link in first cell
                    link = cells[0].find("a")
                    filename = link.get_text(strip=True) if link else cells[0].get_text(strip=True)
                    description = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    doc_type = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                    if filename:
                        documents.append({
                            "filename": filename,
                            "description": description,
                            "type": doc_type,
                        })

        return documents

    def identify_relevant_documents(self, filing: Filing8K, index_docs: list[dict]) -> list[dict]:
        """
        Identify documents to download: primary 8-K and Exhibit 99.x files.

        Args:
            filing: Filing8K object
            index_docs: List of documents from filing index

        Returns:
            List of documents to download with doc_type classification
        """
        relevant = []

        for doc in index_docs:
            filename = doc.get("filename", "").lower()
            description = doc.get("description", "").lower()
            doc_type_raw = doc.get("type", "").lower()

            # Primary 8-K document
            if filename == filing.primary_document.lower():
                doc["doc_type"] = "primary_8k"
                relevant.append(doc)
            # Exhibit 99.x (earnings releases)
            elif re.search(r"ex-?99|exhibit\s*99", filename) or \
                 re.search(r"ex-?99|exhibit\s*99", description) or \
                 "99" in doc_type_raw:
                doc["doc_type"] = "exhibit_99"
                relevant.append(doc)
            # Any document with earnings keywords in description
            elif self._is_earnings_keyword_match(description):
                doc["doc_type"] = "earnings_related"
                relevant.append(doc)

        return relevant

    def download_document(self, filing: Filing8K, doc: dict) -> Document | None:
        """
        Download a document and extract content.

        Args:
            filing: Filing8K object with filing_url
            doc: Document dict with filename

        Returns:
            Document object or None
        """
        filename = doc.get("filename", "")
        if not filename:
            return None

        doc_url = urljoin(filing.filing_url, filename)
        response = self._fetch(doc_url)

        if not response:
            return None

        # Determine content type
        content_type = response.headers.get("Content-Type", "").lower()
        is_pdf = filename.lower().endswith(".pdf") or "pdf" in content_type

        document = Document(
            cik=filing.cik,
            ticker=filing.ticker,
            company_name=filing.company_name,
            accession_number=filing.accession_number,
            filing_date=filing.filing_date,
            form=filing.form,
            doc_type=doc.get("doc_type", "unknown"),
            filename=filename,
            url=doc_url,
            description=doc.get("description", ""),
        )

        if is_pdf:
            document.content_type = "pdf"
            document.content = self._extract_pdf_text(response.content)
        else:
            document.content_type = "html"
            document.content = response.text

        return document

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF bytes.

        Args:
            pdf_bytes: Raw PDF content

        Returns:
            Extracted text
        """
        try:
            from pdfminer.high_level import extract_text
            from io import BytesIO
            return extract_text(BytesIO(pdf_bytes))
        except ImportError:
            logger.warning("pdfminer.six not installed. Cannot extract PDF text.")
            return "[PDF content - extraction requires pdfminer.six]"
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return "[PDF extraction failed]"

    def check_content_for_earnings(self, content: str) -> bool:
        """
        Check if document content contains earnings-related keywords.

        Args:
            content: Document text content

        Returns:
            True if earnings-related
        """
        return self._is_earnings_keyword_match(content)

    def scrape_firm_8ks(
        self,
        cik: str,
        ticker: str,
        company_name: str,
        earnings_only: bool = True,
    ) -> Generator[Document, None, None]:
        """
        Scrape all relevant 8-K documents for a firm.

        Args:
            cik: Company CIK
            ticker: Stock ticker
            company_name: Company name
            earnings_only: If True, only return earnings-related filings

        Yields:
            Document objects
        """
        # Fetch submissions
        submissions = self.fetch_company_submissions(cik)
        if not submissions:
            logger.error(f"Failed to fetch submissions for {ticker}")
            return

        # Filter to 8-Ks
        filings = self.filter_8k_filings(submissions, cik, ticker, company_name)

        for filing in filings:
            # Fetch filing index
            index_docs = self.fetch_filing_index(filing)

            if not index_docs:
                logger.warning(f"No documents found in filing index for {filing.accession_number}")
                continue

            # Identify relevant documents
            relevant_docs = self.identify_relevant_documents(filing, index_docs)

            for doc in relevant_docs:
                document = self.download_document(filing, doc)

                if not document:
                    continue

                # Check if earnings-related (by content if not already flagged)
                if earnings_only and not filing.is_earnings_candidate:
                    if not self.check_content_for_earnings(document.content):
                        continue

                logger.info(f"Downloaded {document.doc_type}: {document.filename}")
                yield document


def scrape_firm(
    cik: str,
    ticker: str,
    company_name: str,
    start_date: date | None = None,
    end_date: date | None = None,
    earnings_only: bool = True,
) -> list[Document]:
    """
    Convenience function to scrape all 8-K documents for a single firm.

    Args:
        cik: Company CIK
        ticker: Stock ticker
        company_name: Company name
        start_date: Start of date range (default from config)
        end_date: End of date range (default from config)
        earnings_only: If True, only return earnings-related filings

    Returns:
        List of Document objects
    """
    scraper = EdgarScraper(
        start_date=start_date or FILING_START_DATE,
        end_date=end_date or FILING_END_DATE,
    )

    return list(scraper.scrape_firm_8ks(cik, ticker, company_name, earnings_only))


if __name__ == "__main__":
    # Test with Apple
    logging.basicConfig(level=logging.INFO)

    documents = scrape_firm(
        cik="0000320193",
        ticker="AAPL",
        company_name="Apple Inc.",
        earnings_only=True,
    )

    print(f"\nFound {len(documents)} documents")
    for doc in documents[:5]:
        print(f"  - {doc.doc_type}: {doc.filename} ({len(doc.content)} chars)")
