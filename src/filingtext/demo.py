"""把合成样本跑成面板，便于直接打开看板。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from filingtext.config import OUTPUT_DIR, SAMPLE_DIR
from filingtext.pipeline import run
from filingtext.samples import SAMPLE_DOCS


def write_samples(dest: Path | None = None) -> Path:
    dest = Path(dest or SAMPLE_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    for doc in SAMPLE_DOCS:
        (dest / doc["filename"]).write_text(doc["text"], encoding="utf-8")
        rows.append(
            {
                "path": doc["filename"],
                "market": doc["market"],
                "ticker": doc["ticker"],
                "firm_name": doc["firm_name"],
                "fiscal_year": doc["fiscal_year"],
                "report_type": doc["report_type"],
            }
        )
    pd.DataFrame(rows).to_csv(dest / "manifest.csv", index=False, encoding="utf-8-sig")
    return dest


def main() -> None:
    sample_dir = write_samples()
    paths = run(input_dir=sample_dir, output_dir=OUTPUT_DIR, workers=1)
    summary = paths["summary"]
    print(
        f"示例面板已写出：{summary['n_found']} 个有效章节，"
        f"{summary['n_firms']} 家公司，年份 {summary['years']}"
    )
    print(paths["parquet"])
    print("下一步：streamlit run app/dashboard.py")


if __name__ == "__main__":
    main()
