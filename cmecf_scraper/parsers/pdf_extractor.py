"""
PDF text extraction for court orders and documents.
"""

import io
import re
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from PDF documents."""

    def __init__(self):
        """Initialize PDF extractor."""
        self._pdfplumber_available = False
        self._pypdf2_available = False

        # Check available libraries
        try:
            import pdfplumber
            self._pdfplumber_available = True
        except ImportError:
            logger.warning("pdfplumber not available")

        try:
            import PyPDF2
            self._pypdf2_available = True
        except ImportError:
            logger.warning("PyPDF2 not available")

        if not self._pdfplumber_available and not self._pypdf2_available:
            logger.error("No PDF library available! Install pdfplumber or PyPDF2")

    def extract_text(self, pdf_content: bytes) -> str:
        """
        Extract text from PDF content.

        Args:
            pdf_content: Raw PDF bytes

        Returns:
            Extracted text from all pages
        """
        if self._pdfplumber_available:
            return self._extract_with_pdfplumber(pdf_content)
        elif self._pypdf2_available:
            return self._extract_with_pypdf2(pdf_content)
        else:
            logger.error("No PDF library available")
            return ""

    def _extract_with_pdfplumber(self, pdf_content: bytes) -> str:
        """Extract text using pdfplumber (better for complex layouts)."""
        import pdfplumber

        text_parts = []

        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

        except Exception as e:
            logger.error(f"Error extracting PDF with pdfplumber: {e}")
            # Fall back to PyPDF2 if available
            if self._pypdf2_available:
                return self._extract_with_pypdf2(pdf_content)

        return '\n\n'.join(text_parts)

    def _extract_with_pypdf2(self, pdf_content: bytes) -> str:
        """Extract text using PyPDF2."""
        import PyPDF2

        text_parts = []

        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))

            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        except Exception as e:
            logger.error(f"Error extracting PDF with PyPDF2: {e}")

        return '\n\n'.join(text_parts)

    def extract_text_from_pages(self, pdf_content: bytes, pages: Optional[List[int]] = None) -> str:
        """
        Extract text from specific pages.

        Args:
            pdf_content: Raw PDF bytes
            pages: List of page numbers (0-indexed) to extract, None for all

        Returns:
            Extracted text
        """
        if not self._pdfplumber_available and not self._pypdf2_available:
            return ""

        text_parts = []

        if self._pdfplumber_available:
            import pdfplumber
            try:
                with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                    total_pages = len(pdf.pages)
                    if pages is None:
                        pages = range(total_pages)

                    for page_num in pages:
                        if 0 <= page_num < total_pages:
                            page_text = pdf.pages[page_num].extract_text()
                            if page_text:
                                text_parts.append(page_text)
            except Exception as e:
                logger.error(f"Error extracting PDF pages: {e}")

        elif self._pypdf2_available:
            import PyPDF2
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
                total_pages = len(pdf_reader.pages)
                if pages is None:
                    pages = range(total_pages)

                for page_num in pages:
                    if 0 <= page_num < total_pages:
                        page_text = pdf_reader.pages[page_num].extract_text()
                        if page_text:
                            text_parts.append(page_text)
            except Exception as e:
                logger.error(f"Error extracting PDF pages: {e}")

        return '\n\n'.join(text_parts)

    def get_metadata(self, pdf_content: bytes) -> dict:
        """
        Extract PDF metadata.

        Args:
            pdf_content: Raw PDF bytes

        Returns:
            Dictionary with metadata fields
        """
        metadata = {}

        if self._pypdf2_available:
            import PyPDF2
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
                info = pdf_reader.metadata
                if info:
                    metadata['title'] = info.get('/Title', '')
                    metadata['author'] = info.get('/Author', '')
                    metadata['subject'] = info.get('/Subject', '')
                    metadata['creator'] = info.get('/Creator', '')
                    metadata['creation_date'] = str(info.get('/CreationDate', ''))
                    metadata['modification_date'] = str(info.get('/ModDate', ''))
                metadata['num_pages'] = len(pdf_reader.pages)
            except Exception as e:
                logger.error(f"Error extracting PDF metadata: {e}")

        return metadata

    def is_court_order(self, pdf_content: bytes) -> bool:
        """
        Check if PDF appears to be a court order.

        Args:
            pdf_content: Raw PDF bytes

        Returns:
            True if PDF appears to be a court order
        """
        # Extract first page text
        text = self.extract_text_from_pages(pdf_content, [0])
        if not text:
            return False

        text_lower = text.lower()

        # Indicators of court orders
        order_indicators = [
            r'in\s+re:',
            r'general\s+order',
            r'administrative\s+order',
            r'standing\s+order',
            r'it\s+is\s+(hereby\s+)?ordered',
            r'united\s+states\s+district\s+court',
            r'clerk\s+of\s+court',
            r'chief\s+judge',
        ]

        for pattern in order_indicators:
            if re.search(pattern, text_lower):
                return True

        return False

    def search_for_dates(self, pdf_content: bytes) -> List[str]:
        """
        Search PDF for date mentions in CM/ECF context.

        Args:
            pdf_content: Raw PDF bytes

        Returns:
            List of text segments containing dates with CM/ECF context
        """
        text = self.extract_text(pdf_content)
        if not text:
            return []

        segments = []
        text_lower = text.lower()

        # Keywords for CM/ECF
        cmecf_keywords = ['cm/ecf', 'cmecf', 'electronic case filing', 'electronic filing',
                         'ecf system', 'e-filing']

        # Find positions of CM/ECF mentions
        for keyword in cmecf_keywords:
            for match in re.finditer(re.escape(keyword), text_lower):
                start = max(0, match.start() - 300)
                end = min(len(text), match.end() + 300)
                segment = text[start:end]
                if segment not in segments:
                    segments.append(segment)

        return segments

    def clean_text(self, text: str) -> str:
        """
        Clean extracted PDF text.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        # Remove multiple spaces
        text = re.sub(r' +', ' ', text)

        # Fix common OCR/extraction issues
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)  # Fix hyphenated words
        text = re.sub(r'\n+', '\n', text)  # Multiple newlines to single

        # Remove page numbers and headers/footers (common patterns)
        text = re.sub(r'\n\d+\n', '\n', text)  # Standalone page numbers
        text = re.sub(r'Page \d+ of \d+', '', text)

        return text.strip()
