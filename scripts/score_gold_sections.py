"""用已核对的起止页给验收集报告打分。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from filingtext.gold import load_section_pages, page_misses

GOLD = ROOT / "tests" / "fixtures" / "section_pages.csv"
REPORT = ROOT / "data" / "validation" / "validation_report.csv"


def actual_from_report(report: pd.DataFrame) -> dict:
    actual = {}
    for row in report.itertuples():
        year = int(row.fiscal_year)
        ticker = str(row.stkcd)
        actual[(ticker, year, "mda")] = {"page_start": row.page_start, "page_end": row.page_end}
        risk_end = getattr(row, "risk_page_end", "")
        actual[(ticker, year, "risk")] = {"page_start": row.risk_page_start, "page_end": risk_end}
    return actual


def main() -> None:
    if not REPORT.exists():
        raise SystemExit("需要 data/validation/validation_report.csv")
    gold = load_section_pages(GOLD)
    report = pd.read_csv(REPORT, dtype=str).fillna("")
    misses = page_misses(actual_from_report(report), gold)
    print(f"起止页误差不超过 1 页：{len(gold) - len(misses)}/{len(gold)}")
    for item in misses:
        print(item)
    if misses:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
