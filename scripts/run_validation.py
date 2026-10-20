"""跑跨行业验收集。每份年报都留一行，失败不跳过。

用法：python scripts/run_validation.py
原文 PDF 写到 data/validation/raw，不进入 git。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from filingtext import __version__
from filingtext.cohort import cohort_jobs
from filingtext.features import evidence_sentences
from filingtext.lexicon import DICTIONARY_VERSION
from filingtext.parse_job import parse_path
from filingtext.sources import download_cninfo

RAW = ROOT / "data" / "validation" / "raw"
REPORT = ROOT / "data" / "validation" / "validation_report.csv"

COLUMNS = [
    "industry",
    "firm_name",
    "stkcd",
    "fiscal_year",
    "status",
    "error",
    "filing_date",
    "source_url",
    "exchange",
    "fetched_at",
    "mda_found",
    "page_start",
    "page_end",
    "n_chars",
    "n_tokens",
    "n_dropped_lines",
    "esg_count",
    "esg_per_k",
    "esg_per_char_k",
    "digital_count",
    "digital_per_k",
    "digital_per_char_k",
    "geopol_count",
    "geopol_per_k",
    "geopol_per_char_k",
    "dictionary_version",
    "app_version",
]


def _blank(job: dict, status: str, error: str = "") -> dict:
    row = {column: "" for column in COLUMNS}
    row.update(
        {
            "industry": job["industry"],
            "firm_name": job["firm_name"],
            "stkcd": job["ticker"],
            "fiscal_year": job["fiscal_year"],
            "status": status,
            "error": error,
            "mda_found": 0,
            "dictionary_version": DICTIONARY_VERSION,
            "app_version": __version__,
        }
    )
    return row


def _manifest_row(ticker: str, year: int) -> dict:
    path = RAW / "manifest.csv"
    if not path.exists():
        return {}
    table = pd.read_csv(path, dtype=str).fillna("")
    hit = table[(table["ticker"] == ticker) & (table["fiscal_year"] == str(year))]
    if hit.empty:
        return {}
    return hit.iloc[-1].to_dict()


def validate_job(job: dict) -> dict:
    ticker = job["ticker"]
    year = int(job["fiscal_year"])
    dest = RAW / f"{ticker}_{year}_annual.pdf"
    try:
        if not dest.exists():
            saved = download_cninfo([ticker], year, year, RAW)
            if not saved and not dest.exists():
                return _blank(job, "not_found", "巨潮未返回该年全文年报")
    except Exception as exc:
        return _blank(job, "download_fail", f"{type(exc).__name__}: {exc}")
    meta = _manifest_row(ticker, year)
    if not dest.exists():
        return _blank(job, "not_found", "下载后文件不存在")
    try:
        parsed = parse_path(
            {
                "path": str(dest),
                "market": "CN",
                "ticker": ticker,
                "firm_name": meta.get("firm_name") or job["firm_name"],
                "fiscal_year": year,
                "report_type": "annual",
                "filing_date": meta.get("filing_date", ""),
                "source_url": meta.get("source_url", ""),
                "exchange": meta.get("exchange", ""),
                "fetched_at": meta.get("fetched_at", ""),
                "sections": ["mda"],
            }
        )
    except Exception as exc:
        row = _blank(job, "parse_fail", f"{type(exc).__name__}: {exc}")
        row["source_url"] = meta.get("source_url", "")
        row["filing_date"] = meta.get("filing_date", "")
        return row
    section = next((item for item in parsed if item.get("section") == "mda"), None)
    if section is None:
        return _blank(job, "parse_fail", "解析结果里没有 mda 行")
    row = _blank(job, "ok" if section.get("found") else "section_missing", section.get("error") or "")
    if not section.get("found"):
        row["status"] = "section_missing"
        row["error"] = row["error"] or "未切出足够长的 MD&A"
    row.update(
        {
            "firm_name": section.get("firm_name") or job["firm_name"],
            "stkcd": section.get("stkcd") or ticker,
            "filing_date": section.get("filing_date") or meta.get("filing_date", ""),
            "source_url": section.get("source_url") or meta.get("source_url", ""),
            "exchange": section.get("exchange") or meta.get("exchange", ""),
            "fetched_at": section.get("fetched_at") or meta.get("fetched_at", ""),
            "mda_found": int(section.get("found") or 0),
            "page_start": section.get("page_start") or "",
            "page_end": section.get("page_end") or "",
            "n_chars": section.get("n_chars") if section.get("found") else "",
            "n_tokens": section.get("n_tokens") if section.get("found") else "",
            "n_dropped_lines": section.get("n_dropped_lines") or 0,
            "esg_count": section.get("esg_count") if section.get("found") else "",
            "esg_per_k": section.get("esg_per_k") if section.get("found") else "",
            "esg_per_char_k": section.get("esg_per_char_k") if section.get("found") else "",
            "digital_count": section.get("digital_count") if section.get("found") else "",
            "digital_per_k": section.get("digital_per_k") if section.get("found") else "",
            "digital_per_char_k": section.get("digital_per_char_k") if section.get("found") else "",
            "geopol_count": section.get("geopol_count") if section.get("found") else "",
            "geopol_per_k": section.get("geopol_per_k") if section.get("found") else "",
            "geopol_per_char_k": section.get("geopol_per_char_k") if section.get("found") else "",
        }
    )
    if section.get("found"):
        evidence = evidence_sentences(
            section.get("section_text") or "",
            section.get("section_raw") or "",
            ["绿色", "碳", "数字化", "人工智能", "关税", "制裁"],
            "zh",
            limit=1,
        )
        if evidence and not evidence[0].get("page") and row["page_start"]:
            row["error"] = row["error"]
    return row


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    jobs = cohort_jobs()
    done = {}
    if REPORT.exists():
        old = pd.read_csv(REPORT, dtype=str).fillna("")
        for item in old.to_dict("records"):
            done[(item["stkcd"], item["fiscal_year"])] = item
    rows = []
    for index, job in enumerate(jobs, start=1):
        key = (job["ticker"], str(job["fiscal_year"]))
        previous = done.get(key)
        if previous and previous.get("status") == "ok" and previous.get("source_url"):
            print(f"{index}/{len(jobs)} skip {job['ticker']} {job['fiscal_year']}", flush=True)
            rows.append(previous)
            continue
        print(f"{index}/{len(jobs)} {job['industry']} {job['firm_name']} {job['fiscal_year']}", flush=True)
        row = validate_job(job)
        rows.append(row)
        print(f"  {row['status']} {row['error'][:120]}", flush=True)
        pd.DataFrame(rows, columns=COLUMNS).to_csv(REPORT, index=False, encoding="utf-8-sig")
    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame.to_csv(REPORT, index=False, encoding="utf-8-sig")
    failures = frame[frame["status"] != "ok"]
    failures.to_csv(REPORT.with_name("validation_failures.csv"), index=False, encoding="utf-8-sig")
    print(f"ok {int((frame['status']=='ok').sum())} / {len(frame)}", flush=True)
    print(REPORT, flush=True)


if __name__ == "__main__":
    main()
