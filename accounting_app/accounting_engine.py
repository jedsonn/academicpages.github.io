"""Core accounting calculations and statement generation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
from pandas import DataFrame

from . import utils


@dataclass
class StatementResult:
    name: str
    data: DataFrame
    metadata: Dict[str, str]


def _filter_period(df: DataFrame, start_date: Optional[datetime], end_date: Optional[datetime]) -> DataFrame:
    if start_date:
        df = df[df["date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["date"] <= pd.Timestamp(end_date)]
    return df


def _category_totals(df: DataFrame) -> DataFrame:
    if "category" not in df.columns:
        return pd.DataFrame(columns=["category", "amount"])
    totals = df.groupby("category")["amount"].sum().reset_index()
    totals = totals.sort_values(by="amount", ascending=False)
    return totals


def generate_income_statement(df: DataFrame, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> StatementResult:
    frame = _filter_period(df, start_date, end_date)
    if "category" not in frame.columns:
        frame["category"] = frame["account"].map(utils.infer_category)
    revenue = frame[frame["category"].str.contains("Revenue", case=False, na=False)]
    expense = frame[frame["category"].str.contains("Expense", case=False, na=False)]
    other = frame[~frame.index.isin(revenue.index.union(expense.index))]
    summary = pd.DataFrame(
        {
            "Category": ["Revenue", "Expense", "Net Income"],
            "Amount": [revenue["amount"].sum(), expense["amount"].sum(), revenue["amount"].sum() - expense["amount"].sum()],
        }
    )
    detail = pd.concat(
        {
            "Revenue": _category_totals(revenue),
            "Expense": _category_totals(expense),
            "Other": _category_totals(other),
        },
        names=["Section"],
    ).reset_index(level=0)
    return StatementResult(
        name="Income Statement",
        data=summary,
        metadata={"detail": detail.to_json(orient="records")},
    )


def generate_balance_sheet(df: DataFrame, as_of: Optional[datetime] = None) -> StatementResult:
    frame = df.copy()
    if as_of:
        frame = frame[frame["date"] <= pd.Timestamp(as_of)]
    if "balance" not in frame.columns:
        frame["balance"] = frame["amount"].cumsum()
    pivot = frame.groupby("category")["balance"].sum()
    assets = pivot.filter(regex="Asset", axis=0).sum()
    liabilities = pivot.filter(regex="Liability", axis=0).sum()
    equity = pivot.filter(regex="Equity", axis=0).sum()
    sheet = pd.DataFrame(
        {
            "Category": ["Assets", "Liabilities", "Equity"],
            "Amount": [assets, liabilities, equity],
        }
    )
    sheet["Amount"].fillna(0.0, inplace=True)
    return StatementResult("Balance Sheet", sheet, metadata={})


def generate_cash_flow(df: DataFrame, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> StatementResult:
    frame = _filter_period(df, start_date, end_date)
    if "category" not in frame.columns:
        frame["category"] = frame["account"].map(utils.infer_category)
    frame = frame.sort_values(by="date")
    operating = frame[frame["category"].str.contains("Expense|Revenue", case=False, na=False)]["amount"].sum()
    investing = frame[frame["category"].str.contains("Asset", case=False, na=False)]["amount"].sum()
    financing = frame[frame["category"].str.contains("Liability|Equity", case=False, na=False)]["amount"].sum()
    cash_change = operating + investing + financing
    cf = pd.DataFrame(
        {
            "Category": ["Operating Activities", "Investing Activities", "Financing Activities", "Net Change in Cash"],
            "Amount": [operating, investing, financing, cash_change],
        }
    )
    return StatementResult("Cash Flow Statement", cf, metadata={})


def generate_trial_balance(df: DataFrame, as_of: Optional[datetime] = None) -> StatementResult:
    frame = df.copy()
    if as_of:
        frame = frame[frame["date"] <= pd.Timestamp(as_of)]
    grouped = frame.groupby("account").agg({"debit": "sum", "credit": "sum"}).fillna(0.0)
    grouped["net"] = grouped["debit"] - grouped["credit"]
    grouped = grouped.reset_index()
    return StatementResult("Trial Balance", grouped, metadata={})


def generate_statements(df: DataFrame, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, StatementResult]:
    statements = {
        "income_statement": generate_income_statement(df, start_date, end_date),
        "balance_sheet": generate_balance_sheet(df, end_date),
        "cash_flow": generate_cash_flow(df, start_date, end_date),
        "trial_balance": generate_trial_balance(df, end_date),
    }
    return statements


__all__ = [
    "StatementResult",
    "generate_income_statement",
    "generate_balance_sheet",
    "generate_cash_flow",
    "generate_trial_balance",
    "generate_statements",
]
