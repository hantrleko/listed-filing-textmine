"""把文本因子按 available_date 并进因子工作台，并给出覆盖率和公告窗口收益。

价格文件不在时只报告合并覆盖，不编造收益。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

FW = Path(r"F:\factor-workbench\data\releases\cn_pit_v1")


def _load_factor(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame["ticker"] = frame["ticker"].astype(str).str.zfill(6)
    frame["fiscal_year"] = frame["fiscal_year"].astype(int)
    frame["fiscal_quarter"] = frame["fiscal_quarter"].astype(int)
    frame["available_date"] = pd.to_datetime(frame["available_date"])
    return frame


def coverage(text: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.DataFrame:
    annual = fundamentals[fundamentals["fiscal_quarter"] == 4].copy()
    annual["ticker"] = annual["ticker"].astype(str).str.zfill(6)
    annual["available_date"] = pd.to_datetime(annual["available_date"])
    keys = ["ticker", "fiscal_year", "fiscal_quarter", "available_date"]
    merged = text.merge(annual[keys].drop_duplicates(), on=keys, how="left", indicator=True)
    return merged


def window_return(prices: pd.DataFrame, ticker: str, day: pd.Timestamp, start: int, end: int) -> float | None:
    part = prices[prices["ticker"].astype(str).str.zfill(6) == ticker].copy()
    if "date" not in part.columns or "close" not in part.columns:
        return None
    part["date"] = pd.to_datetime(part["date"])
    part = part.sort_values("date")
    future = part[part["date"] >= day]
    if len(future) <= end:
        return None
    base = future.iloc[start]["close"]
    last = future.iloc[end]["close"]
    if not base:
        return None
    return float(last) / float(base) - 1.0


def main() -> None:
    factor_path = ROOT / "data" / "validation" / "output" / "panel_factor.parquet"
    if not factor_path.exists():
        raise SystemExit("先运行 scripts/refresh_validation_report.py")
    if not (FW / "fundamentals.parquet").exists():
        raise SystemExit(f"找不到因子工作台发布数据：{FW}")
    text = _load_factor(factor_path)
    fundamentals = pd.read_parquet(FW / "fundamentals.parquet")
    merged = coverage(text, fundamentals)
    overlap = text["ticker"].isin(set(fundamentals["ticker"].astype(str).str.zfill(6)))
    exact = int((merged["_merge"] == "both").sum())
    print(f"文本行 {len(text)}，代码重叠 {int(overlap.sum())}，available_date 四键命中 {exact}")
    value_cols = [column for column in text.columns if column.startswith("mda_") and column.endswith("_per_k")]
    if value_cols and exact:
        both = merged[merged["_merge"] == "both"]
        print(both[["ticker", "fiscal_year", "available_date", *value_cols[:3]]].head(12).to_string(index=False))
    prices_path = FW / "prices.parquet"
    if not prices_path.exists():
        print("没有 prices.parquet，跳过公告窗口收益")
        return
    prices = pd.read_parquet(prices_path)
    rows = []
    for row in text.itertuples():
        ret = window_return(prices, row.ticker, row.available_date, 0, 5)
        if ret is not None:
            rows.append({"ticker": row.ticker, "fiscal_year": row.fiscal_year, "ret_0_5": ret})
    if rows:
        out = pd.DataFrame(rows)
        dest = ROOT / "data" / "validation" / "event_window.csv"
        out.to_csv(dest, index=False, encoding="utf-8-sig")
        print(f"公告后 0–5 个交易日收益 {len(out)} 行，均值 {out['ret_0_5'].mean():.4f}，写入 {dest}")
    else:
        print("价格表里没有能对齐的收盘价列，未计算收益")


if __name__ == "__main__":
    main()
