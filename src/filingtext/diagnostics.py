"""章节切分成功率。按年份和交易所汇总，不重新解析正文。"""

from __future__ import annotations

import pandas as pd


def section_success_table(report: pd.DataFrame) -> pd.DataFrame:
    """每一行是一个会计年度、一家交易所。

    「已核对缺失」是确认年报里没有这一节。「没切到」才是切分没有落到标题。
    """
    if report is None or report.empty:
        return pd.DataFrame(columns=["会计年度", "交易所", "份数", "讨论切出", "风险切出", "风险已核对缺失", "风险没切到"])
    data = report.copy()
    data["fiscal_year"] = pd.to_numeric(data["fiscal_year"], errors="coerce")
    data["mda_found"] = pd.to_numeric(data.get("mda_found"), errors="coerce").fillna(0)
    data["risk_found"] = pd.to_numeric(data.get("risk_found"), errors="coerce").fillna(0)
    status = data.get("section_status_risk", pd.Series("", index=data.index)).fillna("").astype(str)
    data["_risk_status"] = status
    data["exchange"] = data.get("exchange", pd.Series("", index=data.index)).fillna("").astype(str)
    rows = []
    grouped = data.groupby(["fiscal_year", "exchange"], dropna=False)
    for (year, exchange), part in grouped:
        n = int(len(part))
        mda_n = int((part["mda_found"] == 1).sum())
        risk_n = int((part["risk_found"] == 1).sum())
        absent_n = int((part["_risk_status"] == "absent").sum())
        missing_n = int((part["_risk_status"] == "missing").sum())
        year_label = "" if pd.isna(year) else str(int(year))
        rows.append(
            {
                "会计年度": year_label,
                "交易所": exchange or "未标交易所",
                "份数": n,
                "讨论切出": f"{mda_n}/{n}",
                "风险切出": f"{risk_n}/{n}",
                "风险已核对缺失": f"{absent_n}/{n}",
                "风险没切到": f"{missing_n}/{n}",
            }
        )
    frame = pd.DataFrame(rows)
    return frame.sort_values(["会计年度", "交易所"]).reset_index(drop=True)
