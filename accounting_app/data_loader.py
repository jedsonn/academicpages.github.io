"""Data loading utilities for the accounting analytics application."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
from pandas import DataFrame

from . import utils

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class DataLoaderError(RuntimeError):
    """Raised when the loader encounters an unrecoverable problem."""


def _read_csv(path: Path) -> DataFrame:
    return pd.read_csv(path, dtype=str).replace({"": None})


def _read_excel(path: Path) -> Dict[str, DataFrame]:
    excel = pd.read_excel(path, sheet_name=None, dtype=str)
    return {sheet: df.replace({"": None}) for sheet, df in excel.items()}


def _coerce_types(df: DataFrame) -> DataFrame:
    df = utils.normalize_columns(df)
    if "date" in df.columns:
        df["date"] = utils.parse_dates(df["date"])
    for column in ("debit", "credit", "balance", "amount"):
        if column in df.columns:
            df[column] = utils.ensure_numeric(df[column])
    return df


def _standardise(df: DataFrame) -> DataFrame:
    df = _coerce_types(df)
    if "amount" not in df.columns:
        debit = df.get("debit")
        credit = df.get("credit")
        if debit is not None or credit is not None:
            df["amount"] = (debit.fillna(0) if debit is not None else 0) - (
                credit.fillna(0) if credit is not None else 0
            )
    if "category" not in df.columns and "account" in df.columns:
        df["category"] = df["account"].map(utils.infer_category)
    if "date" in df.columns:
        df = df.dropna(subset=["date"])  # discard rows without a valid date
    return df


def load_file(path: Path) -> List[Tuple[str, DataFrame]]:
    """Load a single file returning a list of (source_id, dataframe)."""

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise DataLoaderError(f"Unsupported file format: {path.suffix}")
    if ext == ".csv":
        return [(path.stem, _standardise(_read_csv(path)))]
    sheets = _read_excel(path)
    frames: List[Tuple[str, DataFrame]] = []
    for sheet, df in sheets.items():
        frames.append((f"{path.stem}:{sheet}", _standardise(df)))
    return frames


def load_sources(file_paths: Iterable[str]) -> DataFrame:
    """Load multiple sources into a unified dataframe."""

    frames: List[DataFrame] = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            raise DataLoaderError(f"File not found: {file_path}")
        for source_id, frame in load_file(path):
            frame["source"] = source_id
            frames.append(frame)
    if not frames:
        raise DataLoaderError("No data was loaded from the provided sources")
    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined = combined.sort_values(by="date") if "date" in combined else combined
    return combined.reset_index(drop=True)


def load_budget_file(path: Optional[str]) -> Optional[DataFrame]:
    """Load optional budget data used for budget vs actual reporting."""

    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        raise DataLoaderError(f"Budget file not found: {path}")
    frames = load_file(file_path)
    if not frames:
        return None
    budget_df = frames[0][1]
    if "amount" not in budget_df.columns:
        raise DataLoaderError("Budget file must include an 'amount' column")
    return budget_df


__all__ = [
    "DataLoaderError",
    "load_sources",
    "load_budget_file",
]
