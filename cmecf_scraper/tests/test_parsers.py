"""
Tests for parser modules.
"""

import pytest
from cmecf_scraper.parsers.date_extractor import DateExtractor
from cmecf_scraper.parsers.html_parser import HTMLParser
from cmecf_scraper.models.court_data import SourceType, DatePrecision


class TestDateExtractor:
    """Tests for DateExtractor."""

    def setup_method(self):
        self.extractor = DateExtractor()

    def test_extract_full_date(self):
        """Test extraction of full dates."""
        text = "The CM/ECF system began on October 1, 2003."
        candidates = self.extractor.extract_dates(
            text,
            source_url="https://example.com",
            source_type=SourceType.COURT_WEBSITE
        )

        assert len(candidates) == 1
        assert candidates[0].normalized_date == "2003-10-01"
        assert candidates[0].precision == DatePrecision.EXACT

    def test_extract_mdy_slash_format(self):
        """Test extraction of MM/DD/YYYY format."""
        text = "Electronic filing launched 7/3/2003"
        candidates = self.extractor.extract_dates(
            text,
            source_url="https://example.com",
            source_type=SourceType.COURT_WEBSITE
        )

        assert len(candidates) >= 1
        dates = [c.normalized_date for c in candidates]
        assert "2003-07-03" in dates

    def test_extract_month_year_only(self):
        """Test extraction of month-year format."""
        text = "CM/ECF was implemented in January 2004."
        candidates = self.extractor.extract_dates(
            text,
            source_url="https://example.com",
            source_type=SourceType.COURT_WEBSITE
        )

        assert len(candidates) >= 1
        month_candidates = [c for c in candidates if c.normalized_date == "2004-01-01"]
        assert len(month_candidates) >= 1
        assert month_candidates[0].precision == DatePrecision.MONTH

    def test_extract_year_only(self):
        """Test extraction of year-only format."""
        text = "The court began electronic filing in 2003"
        candidates = self.extractor.extract_dates(
            text,
            source_url="https://example.com",
            source_type=SourceType.COURT_WEBSITE
        )

        assert len(candidates) >= 1
        year_candidates = [c for c in candidates if c.normalized_date == "2003-01-01"]
        assert len(year_candidates) >= 1

    def test_context_scoring(self):
        """Test that CM/ECF context boosts confidence."""
        text_with_context = "The CM/ECF system was launched on January 15, 2004."
        text_without_context = "The meeting was held on January 15, 2004."

        candidates_with = self.extractor.extract_dates(
            text_with_context,
            source_url="https://example.com",
            source_type=SourceType.COURT_WEBSITE
        )
        candidates_without = self.extractor.extract_dates(
            text_without_context,
            source_url="https://example.com",
            source_type=SourceType.COURT_WEBSITE
        )

        assert len(candidates_with) >= 1
        assert len(candidates_without) >= 1
        # Candidates with CM/ECF context should have higher confidence
        assert candidates_with[0].confidence_score >= candidates_without[0].confidence_score

    def test_pilot_detection(self):
        """Test detection of pilot program dates."""
        text = "A pilot program began in 1997 before full implementation in 2003."
        candidates = self.extractor.extract_dates(
            text,
            source_url="https://example.com",
            source_type=SourceType.COURT_WEBSITE
        )

        pilot_candidates = [c for c in candidates if c.is_pilot]
        assert len(pilot_candidates) >= 1

    def test_date_outside_range(self):
        """Test that dates outside expected range are excluded."""
        text = "The court was established in 1950. CM/ECF began in 2015."
        candidates = self.extractor.extract_dates(
            text,
            source_url="https://example.com",
            source_type=SourceType.COURT_WEBSITE
        )

        dates = [c.normalized_date for c in candidates]
        assert "1950-01-01" not in dates  # Too early
        # 2015 should be excluded as it's after MAX_YEAR (2008)

    def test_find_best_date(self):
        """Test finding the single best date."""
        text = """
        The pilot program started in 1997.
        Full CM/ECF implementation began on July 3, 2003.
        The system was upgraded in 2010.
        """
        best = self.extractor.find_best_date(
            text,
            source_url="https://example.com",
            source_type=SourceType.COURT_WEBSITE
        )

        assert best is not None
        assert best.normalized_date == "2003-07-03"
        assert not best.is_pilot


class TestHTMLParser:
    """Tests for HTMLParser."""

    def setup_method(self):
        self.parser = HTMLParser()

    def test_extract_text(self):
        """Test basic text extraction."""
        html = """
        <html>
            <body>
                <main>
                    <h1>Court Information</h1>
                    <p>CM/ECF began on October 1, 2003.</p>
                </main>
            </body>
        </html>
        """
        text = self.parser.extract_text(html)
        assert "CM/ECF began on October 1, 2003" in text
        assert "Court Information" in text

    def test_skip_script_and_style(self):
        """Test that script and style tags are skipped."""
        html = """
        <html>
            <head>
                <style>.hidden { display: none; }</style>
            </head>
            <body>
                <script>alert('test');</script>
                <p>Important content here.</p>
            </body>
        </html>
        """
        text = self.parser.extract_text(html)
        assert "alert" not in text
        assert "display: none" not in text
        assert "Important content here" in text

    def test_extract_links(self):
        """Test link extraction."""
        html = """
        <html>
            <body>
                <a href="/general-orders">General Orders</a>
                <a href="/cmecf">CM/ECF Information</a>
                <a href="https://example.com/test.pdf">PDF Document</a>
            </body>
        </html>
        """
        self.parser.base_url = "https://www.court.gov"
        links = self.parser.extract_links(html)

        assert len(links) == 3
        urls = [link[0] for link in links]
        assert "https://www.court.gov/general-orders" in urls
        assert "https://www.court.gov/cmecf" in urls

    def test_extract_pdf_links(self):
        """Test PDF link extraction."""
        html = """
        <html>
            <body>
                <a href="/orders/order1.pdf">Order 1</a>
                <a href="/about">About</a>
                <a href="/documents/ecf-order.pdf">ECF Order</a>
            </body>
        </html>
        """
        pdf_links = self.parser.extract_pdf_links(html)

        assert len(pdf_links) == 2
        urls = [link[0] for link in pdf_links]
        assert any("order1.pdf" in url for url in urls)
        assert any("ecf-order.pdf" in url for url in urls)

    def test_find_cmecf_sections(self):
        """Test finding CM/ECF related sections."""
        html = """
        <html>
            <body>
                <div id="header">Header content</div>
                <div id="content">
                    <p>General information about the court.</p>
                    <section>
                        <h2>Electronic Filing</h2>
                        <p>The CM/ECF system was implemented on January 1, 2004.</p>
                    </section>
                </div>
            </body>
        </html>
        """
        sections = self.parser.find_cmecf_sections(html)

        assert len(sections) >= 1
        assert any("CM/ECF" in section for section in sections)
        assert any("January 1, 2004" in section for section in sections)

    def test_extract_tables(self):
        """Test table extraction."""
        html = """
        <html>
            <body>
                <table>
                    <tr><th>Court</th><th>Date</th></tr>
                    <tr><td>D. Mass.</td><td>10/1/2003</td></tr>
                    <tr><td>S.D.N.Y.</td><td>1/15/2004</td></tr>
                </table>
            </body>
        </html>
        """
        tables = self.parser.extract_tables(html)

        assert len(tables) == 1
        assert len(tables[0]) == 3  # 3 rows
        assert tables[0][0] == ["Court", "Date"]
        assert tables[0][1] == ["D. Mass.", "10/1/2003"]


class TestDateValidation:
    """Tests for date validation utilities."""

    def test_normalize_various_formats(self):
        """Test normalization of various date formats."""
        from cmecf_scraper.utils.validators import DateValidator
        validator = DateValidator()

        test_cases = [
            ("October 1, 2003", "2003-10-01", "exact"),
            ("10/1/2003", "2003-10-01", "exact"),
            ("2003-10-01", "2003-10-01", "exact"),
            ("January 2004", "2004-01-01", "month"),
            ("2003", "2003-01-01", "year"),
        ]

        for input_date, expected_normalized, expected_precision in test_cases:
            normalized, precision = validator.normalize_date(input_date)
            assert normalized == expected_normalized, f"Failed for {input_date}"
            assert precision == expected_precision, f"Failed precision for {input_date}"

    def test_validate_year_range(self):
        """Test year range validation."""
        from cmecf_scraper.utils.validators import DateValidator
        validator = DateValidator(min_year=1996, max_year=2008)

        assert validator.validate_year_range("2003-10-01")
        assert validator.validate_year_range("1996")
        assert validator.validate_year_range("2008")
        assert not validator.validate_year_range("1990")
        assert not validator.validate_year_range("2015")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
