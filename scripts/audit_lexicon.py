"""统计词典各词在验收集 MD&A 中的命中次数，供人工审计。"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from filingtext.lexicon import DICTIONARY_VERSION
from filingtext.parse_job import parse_path

RAW = ROOT / "data" / "validation" / "raw"
OUT = ROOT / "data" / "validation" / "lexicon_audit.json"


def main() -> None:
    totals: Counter[str] = Counter()
    for pdf in sorted(RAW.glob("*.pdf")):
        rows = parse_path({"path": str(pdf), "sections": ["mda"]})
        row = next((item for item in rows if item.get("section") == "mda" and item.get("found")), None)
        if not row:
            continue
        hits = row.get("term_hits") or {}
        for bucket in hits.values():
            if isinstance(bucket, dict):
                for term, count in bucket.items():
                    totals[term] += int(count or 0)
    payload = {"dictionary_version": DICTIONARY_VERSION, "top_terms": totals.most_common(80), "n_terms": len(totals)}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
