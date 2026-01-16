# research-radar/config.py
"""
Configuration for Research Radar crawler.
"""
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime, timedelta

# How far back to look for papers (on first run)
DEFAULT_LOOKBACK_DAYS = 7

# Sources to crawl
SOURCES = {
    # arXiv categories relevant to accounting/finance
    "arxiv-qfin": {
        "name": "arXiv Quantitative Finance",
        "type": "arxiv",
        "category": "q-fin",
        "enabled": True
    },
    "arxiv-econ": {
        "name": "arXiv Economics",
        "type": "arxiv",
        "category": "econ",
        "enabled": True
    },

    # SSRN networks
    "ssrn-accounting": {
        "name": "SSRN Accounting",
        "type": "ssrn",
        "network_id": "1733",  # Accounting Research Network
        "enabled": True
    },
    "ssrn-financial-economics": {
        "name": "SSRN Financial Economics",
        "type": "ssrn",
        "network_id": "1744",
        "enabled": True
    },

    # NBER
    "nber": {
        "name": "NBER Working Papers",
        "type": "nber",
        "enabled": True
    },
}

# Presets for quick selection
PRESETS = {
    "top-accounting": {
        "name": "Top Accounting Sources",
        "sources": ["ssrn-accounting", "nber", "arxiv-econ"]
    },
    "top-finance": {
        "name": "Top Finance Sources",
        "sources": ["ssrn-financial-economics", "arxiv-qfin", "nber"]
    },
    "working-papers": {
        "name": "All Working Papers",
        "sources": ["ssrn-accounting", "ssrn-financial-economics", "nber", "arxiv-qfin", "arxiv-econ"]
    }
}

# Email configuration
EMAIL_CONFIG = {
    "from_email": "Research Radar <digest@yourdomain.com>",
    "to_email": "your@email.com",  # CHANGE THIS
    "subject_prefix": "Research Radar"
}

@dataclass
class Paper:
    """Represents a research paper."""
    external_id: str
    source: str
    title: str
    authors: List[str]
    abstract: str
    url: str
    published_at: datetime = None
    discovered_at: datetime = field(default_factory=datetime.now)
    topics: List[str] = field(default_factory=list)
    summary: str = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "external_id": self.external_id,
            "source": self.source,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "discovered_at": self.discovered_at.isoformat(),
            "topics": self.topics,
            "summary": self.summary,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        data = data.copy()
        if data.get("published_at"):
            data["published_at"] = datetime.fromisoformat(data["published_at"])
        if data.get("discovered_at"):
            data["discovered_at"] = datetime.fromisoformat(data["discovered_at"])
        return cls(**data)
