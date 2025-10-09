"""Plotly figure generation for the accounting dashboard."""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import analytics


def kpi_card(title: str, value: float, delta: Optional[float] = None) -> go.Figure:
    gauge = go.Figure(
        go.Indicator(
            mode="number+delta" if delta is not None else "number",
            value=value or 0,
            title={"text": title},
            delta={"reference": delta, "relative": True} if delta is not None else None,
            number={"valueformat": ".2f"},
        )
    )
    gauge.update_layout(height=200, margin=dict(t=40, b=20, l=20, r=20))
    return gauge


def revenue_vs_expense_chart(df: pd.DataFrame) -> go.Figure:
    trend = analytics.revenue_vs_expense_trend(df)
    fig = px.line(trend, x="period", y=["Revenue", "Expense"], markers=True, title="Revenue vs Expense")
    fig.update_layout(hovermode="x unified")
    return fig


def expense_bar_chart(df: pd.DataFrame) -> go.Figure:
    expenses = analytics.top_expenses(df, limit=10)
    fig = px.bar(expenses, x="total", y="account", orientation="h", title="Top Expenses")
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return fig


def revenue_breakdown_pie(df: pd.DataFrame) -> go.Figure:
    revenue = analytics.top_revenue(df, limit=10)
    fig = px.pie(revenue, names="account", values="total", title="Revenue Breakdown")
    return fig


def pnl_waterfall(df: pd.DataFrame) -> go.Figure:
    trend = analytics.revenue_vs_expense_trend(df)
    if trend.empty:
        return go.Figure()
    monthly = trend.iloc[-1]
    fig = go.Figure(
        go.Waterfall(
            name="P&L",
            orientation="v",
            measure=["relative", "relative", "total"],
            x=["Revenue", "Expense", "Net"],
            y=[monthly["Revenue"], -abs(monthly["Expense"]), monthly["Net"]],
        )
    )
    fig.update_layout(title="Monthly Profit and Loss", showlegend=False)
    return fig


def assets_vs_liabilities(df: pd.DataFrame) -> go.Figure:
    df = df.copy()
    df["period"] = df["date"].dt.to_period("M").dt.to_timestamp()
    pivot = df.pivot_table(index="period", values="balance", columns="category", aggfunc="sum", fill_value=0)
    assets = pivot.filter(regex="Asset", axis=1).sum(axis=1)
    liabilities = pivot.filter(regex="Liability", axis=1).sum(axis=1)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Assets", x=assets.index, y=assets.values))
    fig.add_trace(go.Bar(name="Liabilities", x=liabilities.index, y=liabilities.values))
    fig.update_layout(barmode="stack", title="Assets vs Liabilities")
    return fig


def expense_heatmap(df: pd.DataFrame) -> go.Figure:
    df = df[df["category"].str.contains("Expense", case=False, na=False)].copy()
    if df.empty:
        return go.Figure()
    df["month"] = df["date"].dt.strftime("%Y-%m")
    pivot = df.pivot_table(index="account", columns="month", values="amount", aggfunc="sum", fill_value=0)
    fig = px.imshow(pivot, aspect="auto", title="Expense Heatmap")
    return fig


def kpi_gauges(ratios: Dict[str, float]) -> go.Figure:
    fig = go.Figure()
    titles = {
        "current_ratio": "Current Ratio",
        "quick_ratio": "Quick Ratio",
        "debt_to_equity": "Debt to Equity",
        "net_margin": "Net Margin",
        "gross_margin": "Gross Margin",
    }
    for idx, (key, value) in enumerate(ratios.items()):
        display_value = 0.0 if value is None or pd.isna(value) else float(value)
        range_max = max(display_value * 2, 1.0)
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=display_value,
                domain={"row": idx // 3, "column": idx % 3},
                title={"text": titles.get(key, key.replace("_", " ").title())},
                gauge={"axis": {"range": [0, range_max]}},
            )
        )
    fig.update_layout(grid={'rows': 2, 'columns': 3, 'pattern': 'independent'}, height=600, title="Key Ratios")
    return fig


def aging_bar_chart(df: pd.DataFrame) -> go.Figure:
    aging = analytics.aging_analysis(df)
    fig = px.bar(aging, x="aging_bucket", y="amount", title="Aging Analysis")
    return fig


def budget_vs_actual_chart(df: pd.DataFrame, budget_df: Optional[pd.DataFrame]) -> go.Figure:
    comparison = analytics.budget_vs_actual(df, budget_df)
    if comparison is None:
        return go.Figure()
    fig = px.bar(comparison, x="period", y=["amount_actual", "amount_budget"], barmode="group", title="Budget vs Actual")
    fig.update_layout(xaxis_title="Period", yaxis_title="Amount")
    return fig


__all__ = [
    "kpi_card",
    "revenue_vs_expense_chart",
    "expense_bar_chart",
    "revenue_breakdown_pie",
    "pnl_waterfall",
    "assets_vs_liabilities",
    "expense_heatmap",
    "kpi_gauges",
    "aging_bar_chart",
    "budget_vs_actual_chart",
]
