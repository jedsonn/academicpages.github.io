"""
Data models for CM/ECF court data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum
import json


class DatePrecision(Enum):
    """Precision level of extracted date."""
    EXACT = "exact"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    UNKNOWN = "unknown"


class SourceType(Enum):
    """Type of source where data was found."""
    COURT_WEBSITE = "court_website"
    ADMINISTRATIVE_ORDER = "administrative_order"
    GENERAL_ORDER = "general_order"
    LOCAL_RULES = "local_rules"
    WAYBACK = "wayback"
    PACER_INFERENCE = "pacer_inference"
    FJC_REPORT = "fjc_report"
    ACADEMIC_SOURCE = "academic_source"
    KNOWN_REFERENCE = "known_reference"
    NOT_FOUND = "not_found"


@dataclass
class DateCandidate:
    """A potential CM/ECF implementation date found during scraping."""
    date_str: str
    normalized_date: Optional[str]  # YYYY-MM-DD format
    precision: DatePrecision
    source_url: str
    source_type: SourceType
    source_text: str
    confidence_score: int  # 1-5
    context: str = ""
    is_pilot: bool = False
    is_mandatory: bool = False

    def to_dict(self) -> dict:
        return {
            "date_str": self.date_str,
            "normalized_date": self.normalized_date,
            "precision": self.precision.value,
            "source_url": self.source_url,
            "source_type": self.source_type.value,
            "source_text": self.source_text[:500] if self.source_text else "",
            "confidence_score": self.confidence_score,
            "context": self.context,
            "is_pilot": self.is_pilot,
            "is_mandatory": self.is_mandatory,
        }


@dataclass
class ScrapingResult:
    """Result of scraping a single page or document."""
    url: str
    status_code: int
    success: bool
    date_candidates: List[DateCandidate] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    content_type: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "success": self.success,
            "date_candidates": [dc.to_dict() for dc in self.date_candidates],
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "content_type": self.content_type,
        }


@dataclass
class CourtData:
    """Complete data for a single court."""
    court_id: str
    court_name: str
    circuit: str
    state: str
    base_url: str

    # Primary dates
    cmecf_go_live_date: Optional[str] = None
    cmecf_go_live_date_precision: DatePrecision = DatePrecision.UNKNOWN
    mandatory_efiling_date: Optional[str] = None
    pilot_program_date: Optional[str] = None

    # Source information
    source_url: Optional[str] = None
    source_type: SourceType = SourceType.NOT_FOUND
    source_text: Optional[str] = None

    # Metadata
    extraction_timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence_score: int = 0
    notes: str = ""

    # All candidates found
    all_candidates: List[DateCandidate] = field(default_factory=list)

    # Scraping history
    scraping_results: List[ScrapingResult] = field(default_factory=list)

    def select_best_candidate(self) -> Optional[DateCandidate]:
        """Select the best date candidate based on confidence and precision."""
        if not self.all_candidates:
            return None

        # Sort by confidence (higher is better), then by precision
        precision_order = {
            DatePrecision.EXACT: 4,
            DatePrecision.MONTH: 3,
            DatePrecision.QUARTER: 2,
            DatePrecision.YEAR: 1,
            DatePrecision.UNKNOWN: 0,
        }

        def score_candidate(c: DateCandidate) -> tuple:
            return (
                c.confidence_score,
                precision_order.get(c.precision, 0),
                0 if c.is_pilot else 1,  # Prefer non-pilot dates
            )

        sorted_candidates = sorted(self.all_candidates, key=score_candidate, reverse=True)
        return sorted_candidates[0] if sorted_candidates else None

    def apply_best_candidate(self) -> None:
        """Apply the best candidate to the main fields."""
        best = self.select_best_candidate()
        if best:
            if best.is_pilot:
                self.pilot_program_date = best.normalized_date
            elif best.is_mandatory:
                self.mandatory_efiling_date = best.normalized_date
            else:
                self.cmecf_go_live_date = best.normalized_date
                self.cmecf_go_live_date_precision = best.precision

            self.source_url = best.source_url
            self.source_type = best.source_type
            self.source_text = best.source_text[:500] if best.source_text else None
            self.confidence_score = best.confidence_score

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON/CSV export."""
        return {
            "court_id": self.court_id,
            "court_name": self.court_name,
            "circuit": str(self.circuit),
            "state": self.state,
            "cmecf_go_live_date": self.cmecf_go_live_date,
            "cmecf_go_live_date_precision": self.cmecf_go_live_date_precision.value,
            "mandatory_efiling_date": self.mandatory_efiling_date,
            "pilot_program_date": self.pilot_program_date,
            "source_url": self.source_url,
            "source_type": self.source_type.value,
            "source_text": self.source_text,
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
            "confidence_score": self.confidence_score,
            "notes": self.notes,
        }

    def to_csv_row(self) -> dict:
        """Convert to dictionary suitable for CSV export."""
        d = self.to_dict()
        # Escape any quotes in source_text
        if d["source_text"]:
            d["source_text"] = d["source_text"].replace('"', '""')
        return d

    @classmethod
    def from_config(cls, court_id: str, config: dict) -> "CourtData":
        """Create CourtData from configuration."""
        return cls(
            court_id=court_id,
            court_name=config["name"],
            circuit=str(config["circuit"]),
            state=config["state"],
            base_url=config["url"],
        )


def export_to_json(courts: List[CourtData], filepath: str) -> None:
    """Export court data to JSON file."""
    data = [court.to_dict() for court in courts]
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_to_csv(courts: List[CourtData], filepath: str) -> None:
    """Export court data to CSV file."""
    import csv

    if not courts:
        return

    fieldnames = [
        "court_id", "court_name", "circuit", "state",
        "cmecf_go_live_date", "cmecf_go_live_date_precision",
        "mandatory_efiling_date", "pilot_program_date",
        "source_url", "source_type", "source_text",
        "extraction_timestamp", "confidence_score", "notes"
    ]

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for court in courts:
            writer.writerow(court.to_csv_row())
