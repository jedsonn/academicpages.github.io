"""
Data validation utilities for CM/ECF scraper.
"""

import re
from datetime import datetime
from typing import Optional, Tuple, List
import logging

from config import MIN_YEAR, MAX_YEAR, KNOWN_DATES

logger = logging.getLogger(__name__)


class DateValidator:
    """Validate and normalize dates."""

    # Date patterns
    DATE_PATTERNS = [
        # YYYY-MM-DD
        (r'(\d{4})-(\d{2})-(\d{2})', 'ymd'),
        # MM/DD/YYYY
        (r'(\d{1,2})/(\d{1,2})/(\d{4})', 'mdy'),
        # Month DD, YYYY
        (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', 'month_day_year'),
        # DD Month YYYY
        (r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', 'day_month_year'),
        # Month YYYY
        (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', 'month_year'),
        # YYYY only
        (r'\b(19\d{2}|20[0-2]\d)\b', 'year_only'),
    ]

    MONTH_MAP = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }

    def __init__(self, min_year: int = MIN_YEAR, max_year: int = MAX_YEAR):
        self.min_year = min_year
        self.max_year = max_year

    def normalize_date(self, date_str: str) -> Tuple[Optional[str], str]:
        """
        Normalize a date string to YYYY-MM-DD format.

        Args:
            date_str: Date string in various formats

        Returns:
            Tuple of (normalized_date, precision)
            precision: 'exact', 'month', 'year', 'unknown'
        """
        date_str = date_str.strip()

        # Try each pattern
        for pattern, fmt in self.DATE_PATTERNS:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                try:
                    if fmt == 'ymd':
                        year, month, day = match.groups()
                        return f"{year}-{month}-{day}", 'exact'

                    elif fmt == 'mdy':
                        month, day, year = match.groups()
                        return f"{year}-{int(month):02d}-{int(day):02d}", 'exact'

                    elif fmt == 'month_day_year':
                        month_name, day, year = match.groups()
                        month = self.MONTH_MAP[month_name.lower()]
                        return f"{year}-{month}-{int(day):02d}", 'exact'

                    elif fmt == 'day_month_year':
                        day, month_name, year = match.groups()
                        month = self.MONTH_MAP[month_name.lower()]
                        return f"{year}-{month}-{int(day):02d}", 'exact'

                    elif fmt == 'month_year':
                        month_name, year = match.groups()
                        month = self.MONTH_MAP[month_name.lower()]
                        return f"{year}-{month}-01", 'month'

                    elif fmt == 'year_only':
                        year = match.group(1)
                        return f"{year}-01-01", 'year'

                except (ValueError, KeyError) as e:
                    logger.debug(f"Error normalizing date '{date_str}': {e}")
                    continue

        return None, 'unknown'

    def validate_year_range(self, date_str: str) -> bool:
        """Check if date falls within expected CM/ECF implementation range."""
        normalized, _ = self.normalize_date(date_str)
        if not normalized:
            return False

        try:
            year = int(normalized[:4])
            return self.min_year <= year <= self.max_year
        except (ValueError, IndexError):
            return False

    def is_valid_date(self, date_str: str) -> bool:
        """Check if string represents a valid date."""
        normalized, precision = self.normalize_date(date_str)
        if not normalized or precision == 'unknown':
            return False

        # Check year range
        try:
            year = int(normalized[:4])
            if not (self.min_year <= year <= self.max_year):
                return False
        except ValueError:
            return False

        # Validate the date itself
        try:
            datetime.strptime(normalized, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    def extract_all_dates(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Extract all potential dates from text.

        Args:
            text: Text to search for dates

        Returns:
            List of (original_match, normalized_date, precision)
        """
        results = []
        seen = set()

        for pattern, fmt in self.DATE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                original = match.group(0)
                if original in seen:
                    continue
                seen.add(original)

                normalized, precision = self.normalize_date(original)
                if normalized and self.validate_year_range(original):
                    results.append((original, normalized, precision))

        return results


def validate_court_data(court_id: str, data: dict) -> List[str]:
    """
    Validate court data against known references and expected values.

    Args:
        court_id: The court identifier
        data: Court data dictionary

    Returns:
        List of validation warnings/errors
    """
    warnings = []

    # Check if we have a known reference date
    if court_id in KNOWN_DATES:
        known = KNOWN_DATES[court_id]
        if data.get('cmecf_go_live_date'):
            extracted_date = data['cmecf_go_live_date']
            known_date = known['date']

            # Compare dates
            if known['precision'] == 'exact':
                if extracted_date != known_date:
                    warnings.append(
                        f"Date mismatch for {court_id}: extracted {extracted_date}, "
                        f"known reference {known_date}"
                    )
            elif known['precision'] == 'year':
                extracted_year = extracted_date[:4] if extracted_date else None
                known_year = known_date[:4] if len(known_date) >= 4 else known_date
                if extracted_year != known_year:
                    warnings.append(
                        f"Year mismatch for {court_id}: extracted {extracted_year}, "
                        f"known reference {known_year}"
                    )

    # Check confidence score
    confidence = data.get('confidence_score', 0)
    if confidence < 3 and data.get('cmecf_go_live_date'):
        warnings.append(f"Low confidence ({confidence}) for {court_id} - needs manual review")

    # Check date range
    go_live_date = data.get('cmecf_go_live_date')
    if go_live_date:
        try:
            year = int(go_live_date[:4])
            if year < MIN_YEAR:
                warnings.append(f"Date {go_live_date} for {court_id} is before expected range ({MIN_YEAR})")
            elif year > MAX_YEAR:
                warnings.append(f"Date {go_live_date} for {court_id} is after expected range ({MAX_YEAR})")
        except (ValueError, TypeError):
            warnings.append(f"Invalid date format for {court_id}: {go_live_date}")

    # Check for missing data
    if not data.get('source_url'):
        warnings.append(f"No source URL for {court_id}")

    if not data.get('source_text'):
        warnings.append(f"No source text for {court_id}")

    return warnings


def cross_validate_circuits(courts_data: List[dict]) -> List[str]:
    """
    Cross-validate dates within circuits.
    Courts in the same circuit often implemented around the same time.

    Args:
        courts_data: List of court data dictionaries

    Returns:
        List of validation warnings
    """
    warnings = []

    # Group by circuit
    circuits = {}
    for court in courts_data:
        circuit = court.get('circuit')
        if circuit not in circuits:
            circuits[circuit] = []
        circuits[circuit].append(court)

    # Check for outliers within each circuit
    for circuit, courts in circuits.items():
        dates = []
        for court in courts:
            if court.get('cmecf_go_live_date'):
                try:
                    dt = datetime.strptime(court['cmecf_go_live_date'][:10], '%Y-%m-%d')
                    dates.append((court['court_id'], dt))
                except ValueError:
                    pass

        if len(dates) >= 2:
            # Sort by date
            dates.sort(key=lambda x: x[1])

            # Check for significant outliers (more than 3 years from median)
            median_idx = len(dates) // 2
            median_date = dates[median_idx][1]

            for court_id, dt in dates:
                diff_days = abs((dt - median_date).days)
                if diff_days > 365 * 3:  # More than 3 years from median
                    warnings.append(
                        f"Circuit {circuit} outlier: {court_id} ({dt.strftime('%Y-%m-%d')}) "
                        f"is {diff_days // 365} years from circuit median"
                    )

    return warnings
