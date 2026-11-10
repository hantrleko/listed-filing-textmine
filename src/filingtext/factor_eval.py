"""把两个文本因子按 available_date 接到月末表，并沿用因子工作台的检验口径。

第 9 个是管理层讨论语气，第 10 个是披露漂移。方向事先写死，不用这次结果再改。
截面不够时只报告覆盖，不计算收益。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_NAMES = 12
HOLDOUT_MONTHS = 12
TRAIN_MONTHS = 24
TEST_MONTHS = 6
MAX_TEXT_AGE_DAYS = 450
FULL_COST = {"commission_bps": 3.0, "half_spread_bps": 5.0, "impact_bps": 10.0, "borrow_monthly": 0.003}

TEXT_FACTORS = (
    {
        "name": "mda_tone_net",
        "label": "管理层讨论语气",
        "direction": 1,
        "definition": "语气净值越高，预注册为下月收益越高。",
    },
    {
        "name": "mda_disclosure_drift",
        "label": "披露漂移",
        "direction": -1,
        "definition": "沿 Cohen、Malloy、Nguyen（2020）：文本变得越多，后续收益越低。做多低漂移。",
    },
)


@dataclass(frozen=True)
class TextFactor:
    name: str
    label: str
    direction: int
    definition: str


def text_factor_specs() -> tuple[TextFactor, ...]:
    return tuple(TextFactor(**item) for item in TEXT_FACTORS)


def attach_text(monthly: pd.DataFrame, text: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """每个月末只用 available_date 不晚于该月的最新一条。超过 15 个月没有更新则留空。"""
    out = monthly.copy()
    out["ticker"] = _ticker(out["ticker"]).to_numpy()
    out["date"] = _naive(out["date"])
    filings = text.copy()
    filings["ticker"] = _ticker(filings["ticker"]).to_numpy()
    filings["available_date"] = _naive(filings["available_date"])
    if "mda_comparable" in filings.columns:
        filings = filings[pd.to_numeric(filings["mda_comparable"], errors="coerce") == 1]
    filings = filings.dropna(subset=["available_date"]).sort_values(["ticker", "available_date"])
    for column in columns:
        out[column] = np.nan
    out["text_available_date"] = pd.NaT
    for ticker, part in filings.groupby("ticker", sort=False):
        mask = out["ticker"] == ticker
        if not mask.any():
            continue
        avail = part["available_date"].to_numpy()
        positions = np.searchsorted(avail, out.loc[mask, "date"].to_numpy(), side="right") - 1
        chosen = part.iloc[np.clip(positions, 0, len(part) - 1)]
        age = (out.loc[mask, "date"].to_numpy() - chosen["available_date"].to_numpy()) / np.timedelta64(1, "D")
        good = (positions >= 0) & (age <= MAX_TEXT_AGE_DAYS)
        index = out.index[mask][good]
        for column in columns:
            values = pd.to_numeric(chosen[column], errors="coerce").to_numpy()
            out.loc[index, column] = values[good]
        out.loc[index, "text_available_date"] = chosen["available_date"].to_numpy()[good]
    return out


def evaluate_text_factors(monthly: pd.DataFrame, text: pd.DataFrame | None = None) -> dict:
    frame = _canonicalize(monthly)
    specs = text_factor_specs()
    names = [spec.name for spec in specs]
    if text is not None:
        missing = [name for name in names if name not in text.columns]
        if missing:
            return {
                "status": "missing_columns",
                "missing": missing,
                "note": "文本因子表里没有：" + "、".join(missing),
            }
        frame = attach_text(frame, text, names)
    present = [name for name in names if name in frame.columns]
    if len(present) < len(names):
        return {"status": "missing_columns", "missing": [name for name in names if name not in present], "note": "月末表里没有文本因子。"}
    usable = frame.dropna(subset=["fwd_ret", "mktcap", "industry"])
    overlap = int(usable[names].notna().any(axis=1).sum())
    note = (
        "中性化是各月末单独做的市值平方根加权最小二乘，解释变量为截距、对数市值和行业哑元。"
        "保留样本是最后 12 个月。在此之前按 24 个月训练、6 个月测试滚动，测试月不参与训练。"
        "完整成本为单边佣金 3bp、半点差 5bp、冲击 10bp，买卖各付一次，另加空头每月 30bp 借券。"
        "当月可用股票少于 12 只时，该月不进入检验。数字只描述这次对齐到的样本。"
    )
    factors = {}
    for spec in specs:
        factors[spec.name] = _one_factor(usable, spec)
    status = "ok" if any(item.get("status") == "ok" for item in factors.values()) else "too_few_months"
    return {"status": status, "n_overlap_rows": overlap, "note": note, "factors": factors}


def _one_factor(frame: pd.DataFrame, spec: TextFactor) -> dict:
    rows = _prepare_series(frame, spec)
    if len(rows) <= HOLDOUT_MONTHS + TRAIN_MONTHS:
        return {
            "label": spec.label,
            "direction": spec.direction,
            "definition": spec.definition,
            "status": "too_few_months",
            "n_months": len(rows),
            "note": f"有效月末 {len(rows)} 个，少于训练窗加 12 个月保留样本，因此不算收益。",
        }
    dates = [row["date"] for row in rows]
    dev_dates = set(dates[:-HOLDOUT_MONTHS])
    hold_dates = set(dates[-HOLDOUT_MONTHS:])
    dev = [row for row in rows if row["date"] in dev_dates]
    hold = [row for row in rows if row["date"] in hold_dates]
    oos_rows = _rolling_test_rows(dates[:-HOLDOUT_MONTHS], rows)
    return {
        "label": spec.label,
        "direction": spec.direction,
        "definition": spec.definition,
        "status": "ok",
        "n_months": len(rows),
        "dev_ic": _mean([row["ic"] for row in dev]),
        "dev_nw_t": _nw_t([row["ic"] for row in dev]),
        "oos_net_ann": _ann([row["net"] for row in oos_rows]),
        "oos_nw_t": _nw_t([row["net"] for row in oos_rows]),
        "holdout_net_ann": _ann([row["net"] for row in hold]),
        "avg_turnover": _mean([row["turnover"] for row in rows if row["turnover"] is not None]),
    }


def _month_row(part: pd.DataFrame, spec: TextFactor) -> dict | None:
    data = part.dropna(subset=[spec.name, "fwd_ret", "mktcap", "industry"]).copy()
    data = data[data["mktcap"] > 0]
    if len(data) < MIN_NAMES:
        return None
    resid = _neutralize(data[spec.name].to_numpy(float), data["mktcap"].to_numpy(float), data["industry"].astype(str).to_numpy())
    if resid is None:
        return None
    signed = resid * spec.direction
    returns = data["fwd_ret"].to_numpy(float)
    weights = _long_short_weights(signed)
    if weights is None:
        return None
    gross = float(np.sum(weights * returns))
    turnover = None
    net = gross - FULL_COST["borrow_monthly"]
    return {
        "ic": _spearman(signed, returns),
        "gross": gross,
        "net": net,
        "turnover": turnover,
        "weights": dict(zip(data["ticker"].astype(str), weights, strict=True)),
    }


def apply_turnover(rows: list[dict]) -> None:
    previous: dict[str, float] | None = None
    for row in rows:
        weights = row.pop("weights")
        if previous is None:
            row["turnover"] = None
            row["net"] = row["gross"] - FULL_COST["borrow_monthly"]
        else:
            names = set(previous) | set(weights)
            turnover = 0.5 * sum(abs(weights.get(name, 0.0) - previous.get(name, 0.0)) for name in names)
            row["turnover"] = turnover
            row["net"] = row["gross"] - _trade_cost(turnover)
        previous = weights


def _rolling_test_rows(dev_dates: list[str], rows: list[dict]) -> list[dict]:
    by_date = {row["date"]: row for row in rows}
    chosen = []
    start = TRAIN_MONTHS
    while start + TEST_MONTHS <= len(dev_dates):
        for day in dev_dates[start : start + TEST_MONTHS]:
            chosen.append(by_date[day])
        start += TEST_MONTHS
    return chosen


def _neutralize(values: np.ndarray, mktcap: np.ndarray, industry: np.ndarray) -> np.ndarray | None:
    y = _winsorize(values)
    log_cap = np.log(mktcap)
    center = log_cap.mean()
    scale = log_cap.std()
    log_cap = (log_cap - center) / scale if scale else np.zeros_like(log_cap)
    counts = pd.Series(industry).value_counts()
    kept = [name for name, count in counts.items() if count >= 2]
    base = kept[-1] if kept else None
    dummies = []
    for name in kept:
        if name == base:
            continue
        dummies.append((industry == name).astype(float))
    columns = [np.ones(len(y)), log_cap, *dummies]
    design = np.column_stack(columns)
    if len(y) < design.shape[1] + 5:
        return None
    weight = np.sqrt(mktcap)
    scale_w = np.sqrt(weight)
    beta = np.linalg.lstsq(design * scale_w[:, None], y * scale_w, rcond=None)[0]
    return y - design @ beta


def _winsorize(values: np.ndarray) -> np.ndarray:
    low, high = np.quantile(values, [0.01, 0.99])
    return np.clip(values, low, high)


def _long_short_weights(signed: np.ndarray) -> np.ndarray | None:
    n = len(signed)
    if n < 10:
        return None
    order = np.argsort(signed, kind="mergesort")
    ranks = np.empty(n, dtype=int)
    ranks[order] = np.arange(n)
    groups = np.minimum(ranks * 5 // n, 4) + 1
    long = groups == 5
    short = groups == 1
    if not long.any() or not short.any():
        return None
    weights = np.zeros(n, dtype=float)
    weights[long] = 1.0 / long.sum()
    weights[short] = -1.0 / short.sum()
    return weights


def _trade_cost(turnover: float) -> float:
    side = (FULL_COST["commission_bps"] + FULL_COST["half_spread_bps"] + FULL_COST["impact_bps"]) / 10000.0
    return 2.0 * turnover * side + FULL_COST["borrow_monthly"]


def _spearman(left: np.ndarray, right: np.ndarray) -> float:
    if len(left) < 3:
        return float("nan")
    return float(pd.Series(left).corr(pd.Series(right), method="spearman"))


def _mean(values: list[float]) -> float:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not clean:
        return float("nan")
    return float(np.mean(clean))


def _ann(values: list[float]) -> float:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not clean:
        return float("nan")
    return float((1.0 + np.mean(clean)) ** 12 - 1.0)


def _nw_t(values: list[float], lags: int = 1) -> float:
    clean = np.array([float(value) for value in values if value is not None and math.isfinite(float(value))])
    n = len(clean)
    if n < 3:
        return float("nan")
    error = clean - clean.mean()
    gamma0 = float(np.dot(error, error) / n)
    variance = gamma0
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1)
        gamma = float(np.dot(error[lag:], error[:-lag]) / n)
        variance += 2.0 * weight * gamma
    if variance <= 0:
        return float("nan")
    se = math.sqrt(variance / n)
    return float(clean.mean() / se) if se else float("nan")


def _canonicalize(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "date": ("date", "month", "trade_date"),
        "ticker": ("ticker", "stkcd"),
        "fwd_ret": ("fwd_ret", "fwd_ret_1"),
        "mktcap": ("mktcap", "market_cap", "float_mktcap"),
        "industry": ("industry", "ind"),
    }
    out = frame.copy()
    for target, options in aliases.items():
        if target in out.columns:
            continue
        for option in options:
            if option in out.columns:
                out[target] = out[option]
                break
    missing = [name for name in ("date", "ticker", "fwd_ret", "mktcap", "industry") if name not in out.columns]
    if missing:
        raise ValueError("月末表缺少字段：" + "、".join(missing))
    out["date"] = pd.to_datetime(out["date"])
    out["ticker"] = _ticker(out["ticker"]).to_numpy()
    for column in ("fwd_ret", "mktcap"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def _ticker(values) -> pd.Series:
    return pd.Series(values).astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)


def _naive(values) -> pd.Series:
    stamps = pd.to_datetime(values, utc=True)
    return stamps.dt.tz_convert(None)


def _prepare_series(frame: pd.DataFrame, spec: TextFactor) -> list[dict]:
    rows = []
    for day, part in frame.groupby("date", sort=True):
        scored = _month_row(part, spec)
        if scored is not None:
            scored["date"] = pd.Timestamp(day).strftime("%Y-%m-%d")
            rows.append(scored)
    apply_turnover(rows)
    return rows
