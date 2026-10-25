"""下载 A 股年报并导出可并入因子工作台的公司—年度表。

网页单次最多 8 份。这个脚本不设这个上限，请自行控制巨潮请求频率。
主键是 ticker、fiscal_year、fiscal_quarter、available_date。
available_date 是公告日 T+1（与因子工作台 NOTICE_DATE 对齐），不是报告期期末。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from filingtext.pipeline import run
from filingtext.sources import download_cninfo
from filingtext.workspace import parse_codes


def main() -> None:
    parser = argparse.ArgumentParser(description="批量下载年报并写出 panel_factor")
    parser.add_argument("--codes", required=True, help="证券代码，逗号或空格分隔")
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--out", default="data/factor_panel")
    args = parser.parse_args()
    root = Path(args.out)
    raw = root / "raw"
    saved = download_cninfo(parse_codes(args.codes), args.start, args.end, raw)
    if not saved:
        raise SystemExit("没有下载到年报。")
    paths = run(raw, root / "output", text_dir=root / "text", workers=1)
    print(f"下载 {len(saved)} 份")
    print(paths["factor_dta"])
    print(paths["factor_parquet"])


if __name__ == "__main__":
    main()
