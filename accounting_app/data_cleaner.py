"""Data validation and cleaning utilities."""
from __future__ import annotations

from typing import Dict, List

import pandas as pd
from pandas import DataFrame

from . import utils


class DataValidationError(RuntimeError):
    """Raised when the dataset fails validation."""


def remove_duplicates(df: DataFrame) -> DataFrame:
    subset = [col for col in ("date", "account", "description", "amount") if col in df.columns]
    if subset:
        df = df.drop_duplicates(subset=subset)
    return df


def fill_missing_values(df: DataFrame) -> DataFrame:
    fill_map = {col: df[col].mode().iloc[0] for col in df.columns if df[col].dtype == "O" and not df[col].mode().empty}
    df = df.fillna(value=fill_map)
    numeric_columns = [col for col in ("debit", "credit", "balance", "amount") if col in df.columns]
    for column in numeric_columns:
        df[column] = df[column].fillna(0.0)
    return df


def validate_balances(df: DataFrame) -> Dict[str, float]:
    """Check that debits equal credits per period."""

    if "date" not in df.columns or "amount" not in df.columns:
        return {}
    df = df.copy()
    df["period"] = df["date"].dt.to_period("M")
    grouped = df.groupby("period")
    imbalances = {}
    for period, frame in grouped:
        debit = frame.get("debit")
        credit = frame.get("credit")
        if debit is not None and credit is not None:
            diff = float(debit.sum() - credit.sum())
            if abs(diff) > 0.01:
                imbalances[str(period)] = diff
    return imbalances


def flag_outliers(df: DataFrame) -> DataFrame:
    if "amount" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    outliers = utils.summarise_outliers(df["amount"].abs())
    if outliers.empty:
        return pd.DataFrame(columns=df.columns)
    return df.loc[outliers.index]


def validate_required_columns(df: DataFrame, required: List[str]) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise DataValidationError(f"Missing required columns: {', '.join(missing)}")


def clean_data(df: DataFrame) -> DataFrame:
    df = remove_duplicates(df)
    df = fill_missing_values(df)
    return df


__all__ = [
    "DataValidationError",
    "clean_data",
    "validate_required_columns",
    "validate_balances",
    "flag_outliers",
]
