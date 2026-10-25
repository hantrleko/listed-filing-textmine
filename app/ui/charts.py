"""看板图表：频次与语气分开展示。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

FREQ_COLS = ["esg_per_k", "digital_per_k", "geopol_per_k"]
TONE_COLS = ["tone_net"]


def render_freq_tone_trends(frame: pd.DataFrame, index_col: str = "fiscal_year") -> None:
    if frame.empty or index_col not in frame.columns:
        return
    ordered = frame.sort_values(index_col)
    years = ordered[index_col].dropna().unique()
    if len(years) == 1:
        row = ordered.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("报告期", int(years[0]))
        c2.metric("ESG/千词", _fmt(row.get("esg_per_k")))
        c3.metric("数智/千词", _fmt(row.get("digital_per_k")))
        c4.metric("语气净值", _fmt(row.get("tone_net")))
        return
    left, right = st.columns(2)
    with left:
        st.caption("每千词频次")
        st.line_chart(ordered.set_index(index_col)[FREQ_COLS])
    with right:
        st.caption("语气净值")
        st.line_chart(ordered.set_index(index_col)[TONE_COLS])


def _fmt(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)
