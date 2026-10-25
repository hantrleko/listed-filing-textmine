"""用当前代码重跑 45 份验收集并更新 validation_report.csv（仅 MD&A 指标列，兼容旧表头）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from filingtext import __version__
from filingtext.cohort import cohort_jobs
from filingtext.lexicon import DICTIONARY_VERSION
from filingtext.pipeline import run

RAW = ROOT / "data" / "validation" / "raw"
OUT = ROOT / "data" / "validation" / "output"
TEXT = ROOT / "data" / "validation" / "text"
REPORT = ROOT / "data" / "validation" / "validation_report.csv"


def main() -> None:
    paths = run(RAW, OUT, text_dir=TEXT, workers=4, manifest=RAW / "manifest.csv")
    frame = pd.read_parquet(paths["parquet"])
    industry = {job["ticker"]: job["industry"] for job in cohort_jobs()}
    rows = []
    for job in cohort_jobs():
        mda = frame[(frame["ticker"] == job["ticker"]) & (frame["fiscal_year"] == job["fiscal_year"]) & (frame["section"] == "mda")]
        risk = frame[(frame["ticker"] == job["ticker"]) & (frame["fiscal_year"] == job["fiscal_year"]) & (frame["section"] == "risk")]
        m = mda.iloc[0] if len(mda) else None
        r = risk.iloc[0] if len(risk) else None
        status = "ok" if m is not None and int(m["found"]) == 1 else "section_missing"
        rows.append(
            {
                "industry": industry.get(job["ticker"], ""),
                "firm_name": job["firm_name"],
                "stkcd": job["ticker"],
                "fiscal_year": job["fiscal_year"],
                "status": status,
                "error": "" if status == "ok" else "未切出足够长的 MD&A",
                "filing_date": m["filing_date"] if m is not None else "",
                "source_url": m["source_url"] if m is not None else "",
                "exchange": m["exchange"] if m is not None else "",
                "fetched_at": m["fetched_at"] if m is not None else "",
                "mda_found": int(m["found"]) if m is not None else 0,
                "risk_found": int(r["found"]) if r is not None else 0,
                "mda_comparable": int(m["comparable"]) if m is not None else 0,
                "risk_comparable": int(r["comparable"]) if r is not None else 0,
                "quality_flags_mda": m["quality_flags"] if m is not None else "",
                "quality_flags_risk": r["quality_flags"] if r is not None else "",
                "section_title_mda": m.get("section_title", "") if m is not None else "",
                "match_method_mda": m.get("match_method", "") if m is not None else "",
                "page_start": m["page_start"] if m is not None else "",
                "page_end": m["page_end"] if m is not None else "",
                "n_tokens": m["n_tokens"] if m is not None else "",
                "n_dropped_lines": m["n_dropped_lines"] if m is not None else "",
                "dictionary_version": DICTIONARY_VERSION,
                "app_version": __version__,
                "run_id": paths.get("run_id", ""),
            }
        )
    pd.DataFrame(rows).to_csv(REPORT, index=False, encoding="utf-8-sig")
    print("wrote", REPORT, "run", paths.get("run_id"))


if __name__ == "__main__":
    main()
