"""看板图表：频次与语气分开展示。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

FREQ_COLS = ["esg_per_k", "digital_per_k", "geopol_per_k"]
TONE_COLS = ["tone_net"]


FREQ_LABELS = {
    "esg_per_k": "绿色/ESG（每千词）",
    "digital_per_k": "数智化（每千词）",
    "geopol_per_k": "地缘政治（每千词）",
}
TONE_LABELS = {"tone_net": "净语气"}


def render_freq_tone_trends(frame: pd.DataFrame, index_col: str = "fiscal_year") -> None:
    if frame.empty or index_col not in frame.columns:
        return
    ordered = frame.sort_values(index_col).copy()
    ordered["_year"] = ordered[index_col].map(lambda value: str(int(value)) if pd.notna(value) else "")
    years = [year for year in ordered["_year"].tolist() if year]
    if len(set(years)) == 1:
        row = ordered.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("报告期", years[0])
        c2.metric("ESG/千词", _fmt(row.get("esg_per_k")))
        c3.metric("数智/千词", _fmt(row.get("digital_per_k")))
        c4.metric("语气净值", _fmt(row.get("tone_net")))
        return
    left, right = st.columns(2)
    with left:
        st.caption("每千词频次")
        chart = ordered.set_index("_year")[FREQ_COLS].rename(columns=FREQ_LABELS)
        st.line_chart(chart)
    with right:
        st.caption("语气净值")
        chart = ordered.set_index("_year")[TONE_COLS].rename(columns=TONE_LABELS)
        st.line_chart(chart)


def _fmt(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)
