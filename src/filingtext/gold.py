"""已核对章节页码的比较。误差不超过 1 页算通过。"""

from __future__ import annotations

import csv
from pathlib import Path


def load_section_pages(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def page_within(got, expected, tolerance: float = 1) -> bool:
    if expected is None or str(expected).strip() == "":
        return True
    if got is None or str(got).strip() == "":
        return False
    return abs(float(got) - float(expected)) <= tolerance


def page_misses(actual: dict, gold_rows: list[dict]) -> list[str]:
    """actual 的键是 (ticker, fiscal_year, section)，值含 page_start、page_end。"""
    misses = []
    for row in gold_rows:
        key = (str(row["ticker"]), int(row["fiscal_year"]), row["section"])
        found = actual.get(key)
        if found is None:
            misses.append(f"{key} 没有解析结果")
            continue
        if not page_within(found.get("page_start"), row.get("page_start")):
            misses.append(f"{key} 起始页 {found.get('page_start')}，夹具 {row.get('page_start')}")
        if not page_within(found.get("page_end"), row.get("page_end")):
            misses.append(f"{key} 结束页 {found.get('page_end')}，夹具 {row.get('page_end')}")
    return misses
