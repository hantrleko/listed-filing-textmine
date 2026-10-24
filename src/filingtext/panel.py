"""面板汇总、诊断统计和时序图。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from filingtext.config import PANEL_COLUMNS

METRIC_COLUMNS = [
    "fog_index",
    "tone_net",
    "esg_per_k",
    "digital_per_k",
    "geopol_per_k",
    "esg_tfidf",
    "digital_tfidf",
    "geopol_tfidf",
    "yoy_similarity",
    "disclosure_drift",
]


def to_frame(records: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    for column in PANEL_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame = frame[PANEL_COLUMNS].copy()
    for column in ("found", "is_duplicate", "comparable", "pit_ready"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    frame["fiscal_year"] = pd.to_numeric(frame["fiscal_year"], errors="coerce")
    for column in METRIC_COLUMNS + [
        "n_chars",
        "n_tokens",
        "n_sentences",
        "page_start",
        "page_end",
        "n_dropped_lines",
        "fiscal_quarter",
        "avg_sentence_len",
        "complex_word_ratio",
        "tone_pos",
        "tone_neg",
        "tone_unc",
        "tone_lit",
        "finbert_pos",
        "finbert_neg",
        "finbert_neu",
        "esg_count",
        "esg_per_k",
        "esg_per_char_k",
        "digital_count",
        "digital_per_k",
        "digital_per_char_k",
        "geopol_count",
        "geopol_per_k",
        "geopol_per_char_k",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ("doc_id", "market", "ticker", "stkcd", "cik", "firm_name", "report_type", "form", "section", "source_path", "text_path", "raw_text_path", "clean_log_path", "text_sha1", "filing_date", "available_date", "source_url", "source_sha1", "exchange", "fetched_at", "data_version", "app_version", "quality_flags", "fog_method", "tone_method", "error"):
        frame[column] = frame[column].fillna("").astype(str)
    return frame


WIDE_VALUE_COLUMNS = [
    "found",
    "comparable",
    "n_chars",
    "n_tokens",
    "esg_count",
    "digital_count",
    "geopol_count",
    "fog_index",
    "tone_net",
    "tone_pos",
    "tone_neg",
    "esg_per_k",
    "digital_per_k",
    "geopol_per_k",
    "esg_tfidf",
    "digital_tfidf",
    "geopol_tfidf",
    "yoy_similarity",
    "disclosure_drift",
]

FACTOR_COLUMNS = [
    "ticker",
    "fiscal_year",
    "fiscal_quarter",
    "available_date",
    "pit_ready",
    "stkcd",
    "firm_name",
    "market",
    "source_url",
    "source_sha1",
    "dictionary_version",
    "app_version",
    "mda_found",
    "mda_comparable",
    "mda_n_tokens",
    "mda_digital_count",
    "mda_esg_count",
    "mda_geopol_count",
    "mda_digital_per_k",
    "mda_esg_per_k",
    "mda_geopol_per_k",
    "mda_tone_net",
    "risk_found",
    "risk_comparable",
    "risk_n_tokens",
    "risk_digital_per_k",
    "risk_esg_per_k",
    "risk_geopol_per_k",
    "risk_tone_net",
]


def to_wide(frame: pd.DataFrame) -> pd.DataFrame:
    """一行一个公司—年度。MD&A 与风险因素分成两套变量，stkcd 保留 6 位字符串。"""
    data = frame.copy()
    if "stkcd" not in data.columns:
        data["stkcd"] = ""
    data["stkcd"] = data["stkcd"].fillna("").astype(str)
    data["ticker"] = data["ticker"].fillna("").astype(str)
    for column in ("filing_date", "available_date", "source_url", "source_sha1", "exchange", "fetched_at", "firm_name", "report_type", "data_version", "app_version"):
        if column not in data.columns:
            data[column] = ""
    if "fiscal_quarter" not in data.columns:
        data["fiscal_quarter"] = pd.NA
    if "pit_ready" not in data.columns:
        data["pit_ready"] = 0
    keys = [
        "market",
        "stkcd",
        "ticker",
        "firm_name",
        "fiscal_year",
        "fiscal_quarter",
        "report_type",
        "filing_date",
        "available_date",
        "pit_ready",
        "source_url",
        "source_sha1",
        "exchange",
        "fetched_at",
        "data_version",
        "app_version",
    ]
    for column in keys:
        if column not in data.columns:
            data[column] = pd.NA
    ordered = data.sort_values(
        ["found", "is_duplicate", "n_chars"],
        ascending=[False, True, False],
        kind="mergesort",
    )
    wide = ordered.drop_duplicates(["market", "ticker", "fiscal_year"])[keys].copy()
    for section in ("mda", "risk"):
        part = ordered[ordered["section"] == section].drop_duplicates(["market", "ticker", "fiscal_year"])
        rename = {column: f"{section}_{column}" for column in WIDE_VALUE_COLUMNS}
        slim = part[["market", "ticker", "fiscal_year", *WIDE_VALUE_COLUMNS]].rename(columns=rename)
        wide = wide.merge(slim, on=["market", "ticker", "fiscal_year"], how="left")
    return wide.sort_values(["market", "ticker", "fiscal_year"]).reset_index(drop=True)


def to_factor(frame: pd.DataFrame) -> pd.DataFrame:
    """因子工作台主键：ticker、fiscal_year、fiscal_quarter、available_date。

    available_date 等于公告日。fiscal_year 只表示报告期，不能单独拿来做时点对齐。
    """
    wide = to_wide(frame).rename(columns={"data_version": "dictionary_version"})
    for column in FACTOR_COLUMNS:
        if column not in wide.columns:
            wide[column] = pd.NA
    return wide[FACTOR_COLUMNS].copy()


def write_duckdb(frame: pd.DataFrame, path: str | Path, wide: pd.DataFrame | None = None) -> int:
    import duckdb

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = duckdb.connect(str(path))
    try:
        connection.register("panel_df", frame)
        connection.execute("CREATE TABLE filings AS SELECT * FROM panel_df")
        if wide is not None:
            connection.register("wide_df", wide)
            connection.execute("CREATE TABLE filings_wide AS SELECT * FROM wide_df")
        count = connection.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
    finally:
        connection.close()
    return int(count)


def export_panel(frame: pd.DataFrame, out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    parquet_path = out / "panel.parquet"
    dta_path = out / "panel.dta"
    wide_parquet = out / "panel_wide.parquet"
    wide_dta = out / "panel_wide.dta"
    duckdb_path = out / "panel.duckdb"
    wide = to_wide(frame)
    factor = to_factor(frame)
    frame.to_parquet(parquet_path, index=False)
    wide.to_parquet(wide_parquet, index=False)
    factor_parquet = out / "panel_factor.parquet"
    factor_dta = out / "panel_factor.dta"
    factor.to_parquet(factor_parquet, index=False)
    _to_stata(frame, dta_path)
    _to_stata(wide, wide_dta)
    _to_stata(factor, factor_dta)
    write_duckdb(frame, duckdb_path, wide)
    summary = summarize(frame)
    (out / "diagnostics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    trend = trend_table(frame)
    trend.to_csv(out / "trend_by_year.csv", index=False)
    plot_trends(frame, out / "trends.png")
    return {
        "parquet": parquet_path,
        "dta": dta_path,
        "wide_parquet": wide_parquet,
        "wide_dta": wide_dta,
        "factor_parquet": factor_parquet,
        "factor_dta": factor_dta,
        "duckdb": duckdb_path,
        "diagnostics": out / "diagnostics.json",
        "trend": out / "trend_by_year.csv",
        "figure": out / "trends.png",
    }


def _to_stata(frame: pd.DataFrame, path: Path) -> None:
    out = frame.copy()
    for column in ("stkcd", "ticker", "cik", "firm_name", "market", "available_date", "source_url", "source_sha1", "dictionary_version", "app_version"):
        if column in out.columns:
            out[column] = out[column].fillna("").astype(str)
    for column in out.columns:
        if pd.api.types.is_integer_dtype(out[column]):
            out[column] = out[column].astype("int32")
    out.to_stata(path, write_index=False, version=118)


def summarize(frame: pd.DataFrame) -> dict:
    found = frame[frame["found"] == 1]
    def dist(series: pd.Series) -> dict:
        values = series.dropna()
        if values.empty:
            return {"n": 0}
        return {
            "n": int(values.shape[0]),
            "mean": float(values.mean()),
            "p50": float(values.median()),
            "p90": float(values.quantile(0.9)),
        }

    by_market = {}
    if not found.empty:
        by_market = {str(k): int(v) for k, v in found.groupby("market").size().items()}
    return {
        "n_rows": int(len(frame)),
        "n_found": int(len(found)),
        "n_firms": int(found["ticker"].nunique()) if not found.empty else 0,
        "years": [int(y) for y in sorted(found["fiscal_year"].dropna().unique())] if not found.empty else [],
        "by_market": by_market,
        "missing_section_rate": float(1 - frame["found"].mean()) if len(frame) else None,
        "metrics": {name: dist(found[name]) for name in METRIC_COLUMNS if name in found.columns},
    }


def trend_table(frame: pd.DataFrame) -> pd.DataFrame:
    found = frame[frame["found"] == 1]
    cols = ["esg_per_k", "digital_per_k", "geopol_per_k", "tone_net", "fog_index", "disclosure_drift"]
    if found.empty:
        return pd.DataFrame(columns=["market", "fiscal_year", *cols])
    grouped = found.groupby(["market", "fiscal_year"], as_index=False)[cols].mean()
    return grouped.sort_values(["market", "fiscal_year"])


def plot_trends(frame: pd.DataFrame, path: str | Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _setup_zh_font()
    found = frame[frame["found"] == 1]
    path = Path(path)
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2))
    specs = [
        ("esg_per_k", "ESG / 绿色转型（每千词）"),
        ("digital_per_k", "数智化 / AI（每千词）"),
        ("tone_net", "语气净值"),
        ("disclosure_drift", "披露漂移 1-相似度"),
    ]
    if found.empty:
        for axis, (_col, title) in zip(axes.ravel(), specs):
            axis.set_title(title)
            axis.text(0.5, 0.5, "无有效章节", ha="center", va="center")
    else:
        for axis, (col, title) in zip(axes.ravel(), specs):
            for market, sub in found.groupby("market"):
                series = sub.groupby("fiscal_year")[col].mean()
                axis.plot(series.index, series.values, marker="o", label=str(market))
            axis.set_title(title)
            axis.set_xlabel("会计年度")
            axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _setup_zh_font() -> None:
    from matplotlib import font_manager
    import matplotlib.pyplot as plt

    candidates = [
        ("Microsoft YaHei", r"C:\Windows\Fonts\msyh.ttc"),
        ("SimHei", r"C:\Windows\Fonts\simhei.ttf"),
    ]
    for name, font_path in candidates:
        if Path(font_path).exists():
            font_manager.fontManager.addfont(font_path)
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False
            return
