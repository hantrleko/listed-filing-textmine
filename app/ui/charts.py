"""看板图表：频次与语气分开展示。年份用序数轴，避免 2022 被画成 2,022。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

FREQ_COLS = ["esg_per_k", "digital_per_k", "geopol_per_k"]
TONE_COLS = ["tone_net"]

# 与正文高亮同一色相。线条用更深的颜色，白底上才看得清。
SERIES_COLORS = {
    "绿色/ESG": "#2d6a4f",
    "数智化": "#1864ab",
    "地缘政治": "#e8590c",
    "净语气": "#495057",
    "披露漂移": "#495057",
}

FREQ_LABELS = {
    "esg_per_k": "绿色/ESG",
    "digital_per_k": "数智化",
    "geopol_per_k": "地缘政治",
}
TONE_LABELS = {"tone_net": "净语气"}
DRIFT_LABELS = {"disclosure_drift": "披露漂移"}

METRIC_LABELS = {
    "digital_per_k": "数智化（每千词）",
    "esg_per_k": "绿色/ESG（每千词）",
    "geopol_per_k": "地缘政治（每千词）",
    "tone_net": "净语气",
    "fog_index": "中文类比可读性",
    "disclosure_drift": "披露漂移（1−余弦）",
    "yoy_similarity": "跨年余弦相似度",
    "yoy_jaccard": "跨年 Jaccard",
    "new_sentence_share": "新增句占比",
}


def render_freq_tone_trends(frame: pd.DataFrame, index_col: str = "fiscal_year") -> None:
    if frame.empty or index_col not in frame.columns:
        return
    ordered = frame.sort_values(index_col)
    years = [_year_label(value) for value in ordered[index_col].tolist()]
    years = [year for year in years if year]
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
        st.caption("每千词。颜色与正文高亮同一套：绿色 ESG，蓝色数智化，橙色地缘政治。")
        _ordinal_lines(ordered, index_col, FREQ_COLS, FREQ_LABELS, "每千词")
    with right:
        st.caption("语气净值")
        _ordinal_lines(ordered, index_col, TONE_COLS, TONE_LABELS, "净值")


def render_drift_trend(frame: pd.DataFrame, index_col: str = "fiscal_year") -> None:
    if frame.empty or "disclosure_drift" not in frame.columns:
        return
    _ordinal_lines(frame, index_col, ["disclosure_drift"], DRIFT_LABELS, "1 − 相似度")


def render_market_trend(frame: pd.DataFrame, metric: str) -> None:
    if frame.empty or metric not in frame.columns or "fiscal_year" not in frame.columns:
        return
    plot = frame.rename(columns={metric: METRIC_LABELS.get(metric, metric)})
    label = METRIC_LABELS.get(metric, metric)
    if "market" not in plot.columns:
        _ordinal_lines(plot, "fiscal_year", [metric], {metric: label}, None)
        return
    long = plot.copy()
    long["会计年度"] = long["fiscal_year"].map(_year_label)
    long = long[long["会计年度"] != ""].dropna(subset=[metric])
    if long.empty:
        return
    import altair as alt

    chart = (
        alt.Chart(long)
        .mark_line(point=True)
        .encode(
            x=_year_axis(sorted(long["会计年度"].unique())),
            y=alt.Y(f"{metric}:Q", title=label),
            color=alt.Color("market:N", title="市场", legend=alt.Legend(orient="bottom")),
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)


def _ordinal_lines(frame: pd.DataFrame, year_col: str, columns: list[str], labels: dict[str, str], y_title: str | None) -> None:
    present = [column for column in columns if column in frame.columns]
    if not present:
        return
    renamed = frame.rename(columns=labels)
    value_cols = [labels[column] for column in present]
    long = renamed.copy()
    long["会计年度"] = long[year_col].map(_year_label)
    long = long[long["会计年度"] != ""]
    long = long.melt(id_vars=["会计年度"], value_vars=value_cols, var_name="系列", value_name="值")
    long = long.dropna(subset=["值"])
    if long.empty:
        return
    import altair as alt

    domain = [name for name in value_cols if name in set(long["系列"])]
    palette = [SERIES_COLORS.get(name, "#495057") for name in domain]
    chart = (
        alt.Chart(long)
        .mark_line(point=True)
        .encode(
            x=_year_axis(sorted(long["会计年度"].unique())),
            y=alt.Y("值:Q", title=y_title),
            color=alt.Color(
                "系列:N",
                scale=alt.Scale(domain=domain, range=palette),
                legend=alt.Legend(orient="bottom", title=None),
            ),
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)


def _year_axis(years: list[str]):
    import altair as alt

    return alt.X("会计年度:O", sort=years, axis=alt.Axis(labelAngle=0, title="会计年度"))


def _year_label(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        text = str(value).strip()
        return "" if text.lower() in {"", "nan", "none"} else text


def _fmt(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)
