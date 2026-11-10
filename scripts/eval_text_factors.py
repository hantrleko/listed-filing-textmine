"""用因子工作台的月末表检验语气和披露漂移。重叠不够时只写覆盖说明。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from filingtext.factor_eval import evaluate_text_factors

WORKBENCH = Path(r"F:\factor-workbench\data\releases\cn_pit_v1\factor_panel.parquet")


def main() -> None:
    text_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "validation" / "output" / "panel_factor.parquet"
    monthly_path = Path(sys.argv[2]) if len(sys.argv) > 2 else WORKBENCH
    if not text_path.exists():
        print(f"没有文本因子表 {text_path}。先导出 panel_factor.parquet。这次不编造检验结果。")
        return
    if not monthly_path.exists():
        print(f"没有因子工作台月末表 {monthly_path}。这次不编造检验结果。")
        return
    text = pd.read_parquet(text_path)
    monthly = pd.read_parquet(monthly_path)
    try:
        result = evaluate_text_factors(monthly, text)
    except ValueError as exc:
        print(exc)
        return
    dest = text_path.with_name("text_factor_eval.json")
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["status"], result["note"])
    print(f"对齐到的行 {result.get('n_overlap_rows', 0)}")
    for name, item in result.get("factors", {}).items():
        print(name, item.get("status"), item.get("note") or item.get("n_months"))
    print(dest)


if __name__ == "__main__":
    main()
