"""Streamlit dashboard for accounting analytics."""
from __future__ import annotations

import base64
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import analytics, data_cleaner, data_loader, utils, visualizations
from .accounting_engine import generate_statements

st.set_page_config(page_title="Accounting Insights", layout="wide", initial_sidebar_state="expanded")


@st.cache_data(show_spinner=False)
def load_data(files: List[Any]) -> pd.DataFrame:
    temp_dir = Path(tempfile.mkdtemp(prefix="acct-app-"))
    temp_paths: List[str] = []
    try:
        for uploaded in files:
            file_path = temp_dir / uploaded.name
            with file_path.open("wb") as buffer:
                buffer.write(uploaded.getvalue())
            temp_paths.append(str(file_path))
        return data_loader.load_sources(temp_paths)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@st.cache_data(show_spinner=False)
def load_budget(file: Optional[Any]) -> Optional[pd.DataFrame]:
    if file is None:
        return None
    temp_dir = Path(tempfile.mkdtemp(prefix="acct-budget-"))
    temp_path = temp_dir / file.name
    try:
        with temp_path.open("wb") as buffer:
            buffer.write(file.getvalue())
        return data_loader.load_budget_file(str(temp_path))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _export_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _export_pdf(figures: Dict[str, "go.Figure"]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    for title, figure in figures.items():
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, title, ln=True)
        image_bytes = figure.to_image(format="png")
        stream = BytesIO(image_bytes)
        pdf.image(stream, w=180)
    return pdf.output(dest="S").encode("latin-1")


def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(df["date"].min().date(), df["date"].max().date()),
    )
    department = st.sidebar.selectbox("Department", options=["All"] + sorted(df["department"].dropna().unique().tolist()))
    account = st.sidebar.selectbox("Account", options=["All"] + sorted(df["account"].dropna().unique().tolist()))
    preset = st.sidebar.selectbox("Preset Views", options=list(utils.ROLE_PRESETS.keys()))
    theme = st.sidebar.toggle("Dark Theme", value=False)
    st.session_state["dark_theme"] = theme
    filtered = df.copy()
    if date_range:
        start, end = date_range
        filtered = filtered[(filtered["date"] >= pd.Timestamp(start)) & (filtered["date"] <= pd.Timestamp(end))]
    if department != "All":
        filtered = filtered[filtered["department"] == department]
    if account != "All":
        filtered = filtered[filtered["account"] == account]
    preset_config = utils.ROLE_PRESETS.get(preset)
    if preset_config and preset_config.get("department"):
        filtered = filtered[filtered["department"] == preset_config["department"]]
    return filtered


def apply_theme() -> None:
    if st.session_state.get("dark_theme"):
        st.markdown(
            """
            <style>
            body, .stApp {
                background-color: #0e1117;
                color: #f0f2f6;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    st.title("Accounting Analysis and Insights")
    st.write("Upload accounting datasets to explore financial performance.")

    uploaded_files = st.file_uploader("Upload CSV/Excel Files", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
    budget_file = st.file_uploader("Optional Budget File", type=["csv", "xlsx", "xls"], key="budget")

    if not uploaded_files:
        st.info("Please upload one or more accounting files to begin.")
        return

    with st.spinner("Loading data..."):
        df = load_data(uploaded_files)
        df = data_cleaner.clean_data(df)
        data_cleaner.validate_required_columns(df, ["date", "account", "amount"])
        imbalances = data_cleaner.validate_balances(df)
        outliers = data_cleaner.flag_outliers(df)
        budget_df = load_budget(budget_file)

    filtered = sidebar_filters(df)
    apply_theme()

    statements = generate_statements(filtered)
    ratios = analytics.ratio_analysis(filtered)
    insights = analytics.automated_insights(filtered)

    tabs = st.tabs(["Overview", "Income Statement", "Balance Sheet", "Cash Flow", "Detailed Analytics", "Data Explorer"])

    with tabs[0]:
        st.subheader("Key Metrics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Revenue", utils.currency_format(filtered[filtered["category"].str.contains("Revenue", na=False)]["amount"].sum()))
        col2.metric("Total Expenses", utils.currency_format(filtered[filtered["category"].str.contains("Expense", na=False)]["amount"].sum()))
        col3.metric("Net Profit", utils.currency_format(filtered["amount"].sum()))

        st.plotly_chart(visualizations.revenue_vs_expense_chart(filtered), use_container_width=True)
        st.plotly_chart(visualizations.expense_bar_chart(filtered), use_container_width=True)
        st.plotly_chart(visualizations.revenue_breakdown_pie(filtered), use_container_width=True)
        st.plotly_chart(visualizations.pnl_waterfall(filtered), use_container_width=True)
        st.plotly_chart(visualizations.assets_vs_liabilities(filtered), use_container_width=True)
        st.plotly_chart(visualizations.expense_heatmap(filtered), use_container_width=True)
        st.plotly_chart(visualizations.kpi_gauges(ratios), use_container_width=True)
        st.plotly_chart(visualizations.aging_bar_chart(filtered), use_container_width=True)
        st.plotly_chart(visualizations.budget_vs_actual_chart(filtered, budget_df), use_container_width=True)

        st.markdown(f"**Automated Insight:** {insights['summary']}")

        if imbalances:
            st.warning(f"Debit/Credit imbalance detected: {imbalances}")
        if not outliers.empty:
            st.warning("Potential outlier transactions:")
            st.dataframe(outliers)

    with tabs[1]:
        st.subheader("Income Statement")
        st.dataframe(statements["income_statement"].data)
        st.download_button(
            "Download Income Statement",
            data=_export_csv(statements["income_statement"].data),
            file_name="income_statement.csv",
            mime="text/csv",
        )

    with tabs[2]:
        st.subheader("Balance Sheet")
        st.dataframe(statements["balance_sheet"].data)

    with tabs[3]:
        st.subheader("Cash Flow Statement")
        st.dataframe(statements["cash_flow"].data)

    with tabs[4]:
        st.subheader("Advanced Analytics")
        st.dataframe(analytics.month_over_month(filtered))
        st.dataframe(analytics.year_over_year(filtered))

    with tabs[5]:
        st.subheader("Data Explorer")
        st.dataframe(filtered)
        st.download_button("Export Filtered Data", data=_export_csv(filtered), file_name="filtered_data.csv", mime="text/csv")

    if st.button("Download Dashboard Report"):
        figures = {
            "Revenue vs Expense": visualizations.revenue_vs_expense_chart(filtered),
            "Top Expenses": visualizations.expense_bar_chart(filtered),
            "Assets vs Liabilities": visualizations.assets_vs_liabilities(filtered),
        }
        pdf_bytes = _export_pdf(figures)
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/pdf;base64,{b64}" download="dashboard_report.pdf">Download Report</a>'
        st.markdown(href, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
