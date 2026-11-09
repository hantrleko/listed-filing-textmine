from pathlib import Path

import pytest

from filingtext.gold import load_section_pages, page_misses, page_within
from filingtext.parse_job import parse_path

FIXTURE = Path(__file__).parent / "fixtures" / "section_pages.csv"
RAW = Path(__file__).resolve().parents[1] / "data" / "validation" / "raw"


def test_page_window_rejects_a_five_page_miss():
    assert page_within(21, 21)
    assert page_within(22, 21)
    assert not page_within(5, 21)
    rows = load_section_pages(FIXTURE)
    moutai = next(row for row in rows if row["ticker"] == "600519" and row["fiscal_year"] == "2023" and row["section"] == "risk")
    assert moutai["page_start"] == "21"
    misses = page_misses({("600519", 2023, "risk"): {"page_start": 5, "page_end": ""}}, [moutai])
    assert misses


def test_checked_filings_stay_within_one_page():
    rows = load_section_pages(FIXTURE)
    needed = {f"{row['ticker']}_{row['fiscal_year']}_annual.pdf" for row in rows}
    missing = [name for name in sorted(needed) if not (RAW / name).exists()]
    if missing:
        pytest.skip("验收集 PDF 不在本机：" + ", ".join(missing))
    actual = {}
    for name in sorted(needed):
        ticker, year, _rest = name.split("_", 2)
        parsed = parse_path(
            {
                "path": str(RAW / name),
                "market": "CN",
                "ticker": ticker,
                "fiscal_year": int(year),
                "sections": ["mda", "risk"],
            }
        )
        for item in parsed:
            actual[(item["ticker"], int(item["fiscal_year"]), item["section"])] = item
    misses = page_misses(actual, rows)
    assert not misses, misses
