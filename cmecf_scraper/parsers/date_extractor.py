"""
Date extraction from text with context analysis for CM/ECF implementation dates.
"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass
import logging

from ..models.court_data import DateCandidate, DatePrecision, SourceType
from ..config import CMECF_KEYWORDS, IMPLEMENTATION_KEYWORDS, MIN_YEAR, MAX_YEAR

logger = logging.getLogger(__name__)


@dataclass
class DateMatch:
    """A date match with surrounding context."""
    date_str: str
    normalized_date: str
    precision: str
    start_pos: int
    end_pos: int
    context_before: str
    context_after: str
    score: float


class DateExtractor:
    """Extract CM/ECF implementation dates from text."""

    # Month names mapping
    MONTHS = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12',
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 'sept': '09',
        'oct': '10', 'nov': '11', 'dec': '12'
    }

    # Date extraction patterns (ordered by specificity)
    DATE_PATTERNS = [
        # Full date formats
        (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', 'month_day_year'),
        (r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s+(\d{4})', 'day_month_year'),
        (r'(\d{1,2})/(\d{1,2})/(\d{4})', 'mdy_slash'),
        (r'(\d{1,2})-(\d{1,2})-(\d{4})', 'mdy_dash'),
        (r'(\d{4})-(\d{2})-(\d{2})', 'ymd_dash'),
        (r'(\d{4})/(\d{2})/(\d{2})', 'ymd_slash'),
        # Month-year formats
        (r'(January|February|March|April|May|June|July|August|September|October|November|December),?\s+(\d{4})', 'month_year'),
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?,?\s+(\d{4})', 'month_abbr_year'),
        # Year only (captured carefully)
        (r'(?:in|since|from|began|starting|effective)\s+((?:19|20)\d{2})\b', 'year_context'),
        (r'\b((?:19|20)\d{2})\b', 'year_only'),
    ]

    # Keywords that indicate CM/ECF implementation
    CMECF_PATTERNS = [
        r'cm/?ecf',
        r'case\s+management[/\s]+electronic\s+case\s+fil',
        r'electronic\s+case\s+fil',
        r'electronic\s+fil',
        r'e-?filing',
        r'ecf\s+system',
    ]

    # Implementation action keywords
    ACTION_PATTERNS = [
        r'began',
        r'implemented',
        r'launched',
        r'went\s+live',
        r'started',
        r'effective',
        r'go-?live',
        r'rolled?\s*out',
        r'deployed',
        r'activated',
        r'introduced',
        r'adopted',
        r'commenced',
        r'initiated',
    ]

    # Negative keywords (these indicate NOT the go-live date)
    NEGATIVE_PATTERNS = [
        r'upgraded',
        r'nextgen',
        r'next\s+gen',
        r'version\s*[234]',
        r'new\s+version',
        r'replaced',
        r'migration',
        r'converted',
        r'mandatory',  # We track this separately
        r'required',
        r'deadline',
    ]

    # Pilot program indicators
    PILOT_PATTERNS = [
        r'pilot',
        r'test',
        r'trial',
        r'beta',
        r'initial\s+rollout',
        r'limited\s+deployment',
    ]

    def __init__(self, context_chars: int = 200):
        """
        Initialize date extractor.

        Args:
            context_chars: Number of characters to capture around date matches
        """
        self.context_chars = context_chars

    def _normalize_date(self, match: re.Match, fmt: str) -> Tuple[Optional[str], str]:
        """Normalize a regex match to YYYY-MM-DD format."""
        try:
            if fmt == 'month_day_year':
                month_name, day, year = match.groups()
                month = self.MONTHS[month_name.lower()]
                return f"{year}-{month}-{int(day):02d}", 'exact'

            elif fmt == 'day_month_year':
                day, month_name, year = match.groups()
                month = self.MONTHS[month_name.lower()]
                return f"{year}-{month}-{int(day):02d}", 'exact'

            elif fmt in ('mdy_slash', 'mdy_dash'):
                month, day, year = match.groups()
                return f"{year}-{int(month):02d}-{int(day):02d}", 'exact'

            elif fmt in ('ymd_dash', 'ymd_slash'):
                year, month, day = match.groups()
                return f"{year}-{month}-{day}", 'exact'

            elif fmt == 'month_year':
                month_name, year = match.groups()
                month = self.MONTHS[month_name.lower()]
                return f"{year}-{month}-01", 'month'

            elif fmt == 'month_abbr_year':
                month_abbr, year = match.groups()
                month = self.MONTHS[month_abbr.lower().rstrip('.')]
                return f"{year}-{month}-01", 'month'

            elif fmt in ('year_context', 'year_only'):
                year = match.group(1)
                return f"{year}-01-01", 'year'

        except (KeyError, ValueError, IndexError) as e:
            logger.debug(f"Error normalizing date: {e}")
            return None, 'unknown'

        return None, 'unknown'

    def _is_valid_year(self, date_str: str) -> bool:
        """Check if the date is within expected range."""
        try:
            year = int(date_str[:4])
            return MIN_YEAR <= year <= MAX_YEAR
        except (ValueError, IndexError):
            return False

    def _score_context(self, context: str, date_match: DateMatch) -> float:
        """
        Score a date match based on surrounding context.

        Higher scores indicate more likely CM/ECF implementation dates.
        """
        score = 0.0
        context_lower = context.lower()

        # Check for CM/ECF keywords (high value)
        for pattern in self.CMECF_PATTERNS:
            if re.search(pattern, context_lower):
                score += 3.0
                break

        # Check for implementation action keywords
        for pattern in self.ACTION_PATTERNS:
            if re.search(pattern, context_lower):
                score += 2.0
                break

        # Check for negative keywords (reduce score)
        for pattern in self.NEGATIVE_PATTERNS:
            if re.search(pattern, context_lower):
                score -= 2.0

        # Bonus for exact dates
        if date_match.precision == 'exact':
            score += 1.0
        elif date_match.precision == 'month':
            score += 0.5

        # Bonus for years in prime rollout period (2002-2006)
        try:
            year = int(date_match.normalized_date[:4])
            if 2002 <= year <= 2006:
                score += 0.5
        except (ValueError, IndexError):
            pass

        return score

    def _check_pilot(self, context: str) -> bool:
        """Check if context indicates a pilot program."""
        context_lower = context.lower()
        for pattern in self.PILOT_PATTERNS:
            if re.search(pattern, context_lower):
                return True
        return False

    def _check_mandatory(self, context: str) -> bool:
        """Check if context indicates mandatory e-filing date."""
        context_lower = context.lower()
        return bool(re.search(r'mandatory|required|must\s+file|shall\s+file', context_lower))

    def extract_dates(self, text: str, source_url: str, source_type: SourceType) -> List[DateCandidate]:
        """
        Extract all potential CM/ECF implementation dates from text.

        Args:
            text: Text to search
            source_url: URL where text was found
            source_type: Type of source

        Returns:
            List of DateCandidate objects, sorted by confidence
        """
        candidates = []
        text_lower = text.lower()

        # First, find all date matches
        date_matches: List[DateMatch] = []

        for pattern, fmt in self.DATE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                normalized, precision = self._normalize_date(match, fmt)

                if not normalized or not self._is_valid_year(normalized):
                    continue

                start = match.start()
                end = match.end()

                # Get context
                ctx_start = max(0, start - self.context_chars)
                ctx_end = min(len(text), end + self.context_chars)
                context_before = text[ctx_start:start]
                context_after = text[end:ctx_end]
                full_context = text[ctx_start:ctx_end]

                date_match = DateMatch(
                    date_str=match.group(0),
                    normalized_date=normalized,
                    precision=precision,
                    start_pos=start,
                    end_pos=end,
                    context_before=context_before,
                    context_after=context_after,
                    score=0.0
                )

                # Score the match
                date_match.score = self._score_context(full_context, date_match)
                date_matches.append(date_match)

        # Remove duplicates (same normalized date), keeping highest scored
        seen_dates = {}
        for dm in date_matches:
            if dm.normalized_date not in seen_dates or dm.score > seen_dates[dm.normalized_date].score:
                seen_dates[dm.normalized_date] = dm

        # Convert to DateCandidate objects
        for normalized_date, dm in seen_dates.items():
            full_context = dm.context_before + dm.date_str + dm.context_after

            # Determine precision enum
            precision_map = {
                'exact': DatePrecision.EXACT,
                'month': DatePrecision.MONTH,
                'quarter': DatePrecision.QUARTER,
                'year': DatePrecision.YEAR,
            }
            precision = precision_map.get(dm.precision, DatePrecision.UNKNOWN)

            # Calculate confidence score (1-5)
            if dm.score >= 4:
                confidence = 5
            elif dm.score >= 3:
                confidence = 4
            elif dm.score >= 2:
                confidence = 3
            elif dm.score >= 1:
                confidence = 2
            else:
                confidence = 1

            # Adjust confidence based on precision
            if precision == DatePrecision.YEAR:
                confidence = min(confidence, 3)
            elif precision == DatePrecision.MONTH:
                confidence = min(confidence, 4)

            candidate = DateCandidate(
                date_str=dm.date_str,
                normalized_date=normalized_date,
                precision=precision,
                source_url=source_url,
                source_type=source_type,
                source_text=full_context.strip(),
                confidence_score=confidence,
                context=full_context.strip(),
                is_pilot=self._check_pilot(full_context),
                is_mandatory=self._check_mandatory(full_context),
            )
            candidates.append(candidate)

        # Sort by confidence score (descending)
        candidates.sort(key=lambda c: (c.confidence_score, 0 if c.is_pilot else 1), reverse=True)

        return candidates

    def find_best_date(self, text: str, source_url: str, source_type: SourceType) -> Optional[DateCandidate]:
        """
        Find the single best CM/ECF implementation date from text.

        Args:
            text: Text to search
            source_url: URL where text was found
            source_type: Type of source

        Returns:
            Best DateCandidate or None if no valid date found
        """
        candidates = self.extract_dates(text, source_url, source_type)

        # Filter out pilot dates unless that's all we have
        non_pilot = [c for c in candidates if not c.is_pilot]
        if non_pilot:
            return non_pilot[0]
        elif candidates:
            return candidates[0]
        return None

    def search_for_cmecf_context(self, text: str) -> List[str]:
        """
        Find all text segments that mention CM/ECF.
        Useful for identifying relevant sections to search more carefully.

        Args:
            text: Full text to search

        Returns:
            List of text segments containing CM/ECF mentions
        """
        segments = []
        text_lower = text.lower()

        for pattern in self.CMECF_PATTERNS:
            for match in re.finditer(pattern, text_lower):
                start = max(0, match.start() - self.context_chars)
                end = min(len(text), match.end() + self.context_chars)
                segment = text[start:end]
                if segment not in segments:
                    segments.append(segment)

        return segments
