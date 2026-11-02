"""按人工起止页给当前切分打分。金标准留空的行会跳过。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

GOLD = ROOT / "data" / "validation" / "gold_sections.csv"
REPORT = ROOT / "data" / "validation" / "validation_report.csv"


def main() -> None:
    if not GOLD.exists() or not REPORT.exists():
        raise SystemExit("需要 gold_sections.csv 和 validation_report.csv")
    gold = pd.read_csv(GOLD, dtype=str).fillna("")
    report = pd.read_csv(REPORT, dtype=str).fillna("")
    scored = gold[(gold["page_start"] != "") & (gold["page_end"] != "")]
    if scored.empty:
        print("金标准还没有填写起止页")
        return
    hits = 0
    for row in scored.itertuples():
        part = report[(report["stkcd"] == row.ticker) & (report["fiscal_year"] == row.fiscal_year)]
        if part.empty:
            continue
        current = part.iloc[0]
        if row.section == "risk":
            got = current.get("risk_page_start") or ""
        else:
            got = current.get("page_start") or ""
        if not got:
            continue
        if abs(float(got) - float(row.page_start)) <= 1:
            hits += 1
    print(f"起止页误差不超过 1 页：{hits}/{len(scored)}")


if __name__ == "__main__":
    main()
