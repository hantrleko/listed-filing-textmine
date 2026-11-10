"""从验收集已清洗的管理层讨论里抽主题词审计句。正文不进入 git。"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from filingtext.audit import sample_topic_sentences

TEXT_DIR = ROOT / "data" / "validation" / "text"
OUT = TEXT_DIR / "lexicon_audit_sample.csv"


def _documents() -> list[dict]:
    rows = []
    for path in sorted(TEXT_DIR.glob("CN_*_mda.txt")):
        name = path.name
        ticker = name.split("_")[1]
        year = name.split("_")[2]
        rows.append({"ticker": ticker, "fiscal_year": year, "text": path.read_text(encoding="utf-8")})
    return rows


def main() -> None:
    documents = _documents()
    if not documents:
        raise SystemExit(f"没有找到清洗后的管理层讨论：{TEXT_DIR}")
    chosen = []
    for lexicon in ("esg", "digital", "geopol"):
        chosen.extend(sample_topic_sentences(documents, lexicon))
    frame = pd.DataFrame(chosen)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(OUT)
    print(frame.groupby(["lexicon", "hit"]).size().to_string())


if __name__ == "__main__":
    main()
