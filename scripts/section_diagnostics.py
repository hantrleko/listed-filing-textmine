"""按年份和交易所汇总章节切分。默认读验收集，也可传入更大的报告。"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from filingtext.diagnostics import section_success_table

DEFAULT = ROOT / "data" / "validation" / "validation_report.csv"


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    report = pd.read_csv(source)
    table = section_success_table(report)
    dest = source.with_name("section_diagnostics.csv")
    table.to_csv(dest, index=False, encoding="utf-8-sig")
    print(table.to_string(index=False))
    print(dest)


if __name__ == "__main__":
    main()