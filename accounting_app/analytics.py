"""Analytics layer providing ratios and trend insights."""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from . import utils


def _ensure_period(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["period"] = df["date"].dt.to_period("M").dt.to_timestamp()
    return df


def revenue_vs_expense_trend(df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_period(df)
    pivot = df.pivot_table(values="amount", index="period", columns="category", aggfunc="sum", fill_value=0)
    revenue = pivot.filter(regex="Revenue", axis=1).sum(axis=1)
    expense = pivot.filter(regex="Expense", axis=1).sum(axis=1)
    trend = pd.DataFrame({"Revenue": revenue, "Expense": expense})
    trend["Net"] = trend["Revenue"] - trend["Expense"]
    return trend.reset_index()


def month_over_month(df: pd.DataFrame, column: str = "amount") -> pd.DataFrame:
    df = _ensure_period(df)
    monthly = df.groupby("period")[column].sum()
    mom = utils.rolling_growth(monthly).to_frame(name="mom_growth")
    return mom.reset_index()


def year_over_year(df: pd.DataFrame, column: str = "amount") -> pd.DataFrame:
    df = _ensure_period(df)
    yearly = df.groupby(df["date"].dt.to_period("Y")).agg({column: "sum"})
    yoy = yearly.pct_change().rename(columns={column: "yoy_growth"})
    yoy.index = yoy.index.to_timestamp()
    return yoy.reset_index().rename(columns={"date": "period"})


def ratio_analysis(df: pd.DataFrame) -> Dict[str, float]:
    if "balance" not in df.columns:
        df = df.sort_values("date").copy()
        df["balance"] = df.groupby("account")["amount"].cumsum()
    latest_period = df["date"].max()
    balance_sheet = df[df["date"] == latest_period]
    assets = balance_sheet[balance_sheet["category"].str.contains("Asset", na=False)]["balance"].sum()
    liabilities = balance_sheet[balance_sheet["category"].str.contains("Liability", na=False)]["balance"].sum()
    equity = balance_sheet[balance_sheet["category"].str.contains("Equity", na=False)]["balance"].sum()
    revenue = df[df["category"].str.contains("Revenue", na=False)]["amount"].sum()
    expense = df[df["category"].str.contains("Expense", na=False)]["amount"].sum()
    net_income = revenue - expense
    return {
        "current_ratio": utils.safe_divide(assets, liabilities),
        "quick_ratio": utils.safe_divide(assets - balance_sheet[balance_sheet["account"].str.contains("Inventory", na=False)]["balance"].sum(), liabilities),
        "debt_to_equity": utils.safe_divide(liabilities, equity),
        "net_margin": utils.safe_divide(net_income, revenue),
        "gross_margin": utils.safe_divide(
            revenue - df[df["account"].str.contains("COGS|Cost of Goods", case=False, na=False)]["amount"].sum(),
            revenue,
        ),
    }


def top_expenses(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    expenses = df[df["category"].str.contains("Expense", case=False, na=False)]
    grouped = expenses.groupby("account")["amount"].sum().abs().sort_values(ascending=False)
    return grouped.head(limit).reset_index().rename(columns={"amount": "total"})


def top_revenue(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    revenue = df[df["category"].str.contains("Revenue", case=False, na=False)]
    grouped = revenue.groupby("account")["amount"].sum().sort_values(ascending=False)
    return grouped.head(limit).reset_index().rename(columns={"amount": "total"})


def aging_analysis(df: pd.DataFrame, aging_column: str = "amount") -> pd.DataFrame:
    df = df.copy()
    df["days_outstanding"] = (pd.Timestamp.utcnow().normalize() - df["date"]).dt.days
    bins = [0, 30, 60, 90, np.inf]
    labels = ["0-30", "31-60", "61-90", "90+"]
    df["aging_bucket"] = pd.cut(df["days_outstanding"], bins=bins, labels=labels, right=False)
    aging = df.groupby("aging_bucket")[aging_column].sum().reset_index()
    return aging


def budget_vs_actual(df: pd.DataFrame, budget_df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if budget_df is None:
        return None
    df = _ensure_period(df)
    budget = budget_df.copy()
    if "date" in budget.columns:
        budget["date"] = utils.parse_dates(budget["date"])
        budget["period"] = budget["date"].dt.to_period("M").dt.to_timestamp()
    else:
        raise ValueError("Budget data must contain a date column")
    actual = df.groupby("period")["amount"].sum().reset_index()
    plan = budget.groupby("period")["amount"].sum().reset_index()
    merged = pd.merge(actual, plan, on="period", how="outer", suffixes=("_actual", "_budget")).fillna(0)
    merged["variance"] = merged["amount_actual"] - merged["amount_budget"]
    merged["variance_pct"] = utils.safe_divide(merged["variance"], merged["amount_budget"].replace({0: np.nan}))
    return merged


def automated_insights(df: pd.DataFrame) -> Dict[str, str]:
    trend = revenue_vs_expense_trend(df)
    if trend.empty:
        return {"summary": "Insufficient data for insights."}
    latest = trend.iloc[-1]
    previous = trend.iloc[-2] if len(trend) > 1 else None
    summary = f"Net income for {latest['period']:%B %Y} was {utils.currency_format(latest['Net'])}."
    if previous is not None and previous["Net"]:
        change = utils.safe_divide(latest["Net"] - previous["Net"], previous["Net"])
        summary += f" This represents a {change:.1%} change from the prior month."
    expense_trend = top_expenses(df, limit=3)
    if not expense_trend.empty:
        top_expense = expense_trend.iloc[0]
        summary += f" Top expense category: {top_expense['account']} ({utils.currency_format(top_expense['total'])})."
    return {"summary": summary}


__all__ = [
    "revenue_vs_expense_trend",
    "month_over_month",
    "year_over_year",
    "ratio_analysis",
    "top_expenses",
    "top_revenue",
    "aging_analysis",
    "budget_vs_actual",
    "automated_insights",
]
