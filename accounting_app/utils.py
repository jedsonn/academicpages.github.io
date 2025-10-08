"""Utility functions and constants for the accounting analytics app."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

import numpy as np
import pandas as pd

# Default column names expected by the application. Each column has a list of
# aliases that may appear in source data.
COLUMN_ALIASES: Mapping[str, List[str]] = {
    "date": [
        "date",
        "transaction date",
        "posting date",
        "journal date",
        "entry date",
    ],
    "account": [
        "account",
        "account name",
        "account title",
        "gl account",
        "account code",
    ],
    "account_code": ["account code", "gl code", "code"],
    "description": ["description", "memo", "details", "narration"],
    "debit": ["debit", "debits", "debit amount"],
    "credit": ["credit", "credits", "credit amount"],
    "balance": ["balance", "running balance", "amount"],
    "category": [
        "category",
        "account type",
        "type",
        "financial category",
        "class",
    ],
    "reference": [
        "reference",
        "reference number",
        "ref",
        "document number",
        "invoice number",
    ],
    "entity": [
        "vendor",
        "customer",
        "entity",
        "name",
        "counterparty",
        "vendor/customer",
    ],
    "department": ["department", "cost center", "location", "division"],
    "amount": ["amount", "value", "net amount"],
}

STANDARD_COLUMNS: List[str] = [
    "date",
    "account",
    "account_code",
    "description",
    "debit",
    "credit",
    "balance",
    "amount",
    "category",
    "reference",
    "entity",
    "department",
]

# Mapping of keywords to default categories when the source data does not
# provide an explicit account type. The mapping is intentionally broad so that
# we can infer a reasonable classification in most cases.
KEYWORD_CATEGORY_MAP: Mapping[str, str] = {
    "cash": "Asset",
    "bank": "Asset",
    "receivable": "Asset",
    "inventory": "Asset",
    "prepaid": "Asset",
    "asset": "Asset",
    "payable": "Liability",
    "loan": "Liability",
    "tax": "Liability",
    "liability": "Liability",
    "equity": "Equity",
    "capital": "Equity",
    "revenue": "Revenue",
    "sales": "Revenue",
    "income": "Revenue",
    "expense": "Expense",
    "cost": "Expense",
    "cogs": "Expense",
}

ROLE_PRESETS: Mapping[str, Dict[str, Optional[str]]] = {
    "CFO View": {"department": None, "focus_metric": "net_income"},
    "Accountant View": {"department": None, "focus_metric": "trial_balance"},
    "Department Manager": {"department": "Operations", "focus_metric": "expense"},
}


@dataclass
class Period:
    """Simple representation of a reporting period."""

    start: datetime
    end: datetime

    @property
    def label(self) -> str:
        return f"{self.start:%Y-%m-%d} to {self.end:%Y-%m-%d}"


def slugify(value: str) -> str:
    """Create a filesystem friendly slug."""

    cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.lower())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")


def ensure_directory(path: Path) -> None:
    """Ensure a directory exists."""

    path.mkdir(parents=True, exist_ok=True)


def detect_column(columns: Iterable[str], target: str) -> Optional[str]:
    """Return the first column name that matches a target alias."""

    aliases = COLUMN_ALIASES.get(target, [])
    lowered = {col.lower(): col for col in columns}
    for alias in aliases:
        if alias in lowered:
            return lowered[alias]
    return None


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise column names across disparate data sources."""

    rename_map = {}
    for standard in STANDARD_COLUMNS:
        alias = detect_column(df.columns, standard)
        if alias:
            rename_map[alias] = standard
    normalized = df.rename(columns=rename_map)
    return normalized


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse a pandas Series to datetimes with flexible format support."""

    if series.dtype == "datetime64[ns]":
        return series
    return pd.to_datetime(series, errors="coerce", infer_datetime_format=True, utc=False)


def ensure_numeric(series: pd.Series) -> pd.Series:
    """Convert a series to numeric, gracefully handling errors."""

    return pd.to_numeric(series, errors="coerce")


def infer_category(account: str) -> str:
    """Infer an account category from its name using keyword heuristics."""

    account_lower = (account or "").lower()
    for keyword, category in KEYWORD_CATEGORY_MAP.items():
        if keyword in account_lower:
            return category
    return "Uncategorized"


@lru_cache(maxsize=32)
def load_json_config(path: str) -> Dict[str, str]:
    """Load a JSON configuration file with caching."""

    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def as_month_period(date: datetime) -> datetime:
    """Return the first day of the month for grouping."""

    return datetime(date.year, date.month, 1)


def safe_divide(numerator: float, denominator: float) -> float:
    """Return a safe division result with zero denominator handling."""

    if denominator in (0, None) or (isinstance(denominator, float) and np.isclose(denominator, 0.0)):
        return np.nan
    return numerator / denominator


def currency_format(value: float) -> str:
    """Format a number as currency with thousands separator."""

    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "-"
    return f"${value:,.2f}"


def summarise_outliers(series: pd.Series, multiplier: float = 3.0) -> pd.Series:
    """Identify outliers using the z-score method."""

    if series.empty:
        return pd.Series(dtype=float)
    mean = series.mean()
    std = series.std(ddof=0)
    if std == 0:
        return pd.Series(dtype=float)
    z_scores = (series - mean) / std
    return series[np.abs(z_scores) > multiplier]


def to_excel(df_map: Mapping[str, pd.DataFrame], path: Path) -> None:
    """Write multiple dataframes to a formatted Excel workbook."""

    ensure_directory(path.parent)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, df in df_map.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def rolling_growth(series: pd.Series) -> pd.Series:
    """Calculate percentage change with safe handling of division by zero."""

    previous = series.shift(1)
    return (series - previous) / previous.replace({0: np.nan})


__all__ = [
    "COLUMN_ALIASES",
    "STANDARD_COLUMNS",
    "ROLE_PRESETS",
    "Period",
    "slugify",
    "ensure_directory",
    "detect_column",
    "normalize_columns",
    "parse_dates",
    "ensure_numeric",
    "infer_category",
    "load_json_config",
    "as_month_period",
    "safe_divide",
    "currency_format",
    "summarise_outliers",
    "to_excel",
    "rolling_growth",
]
