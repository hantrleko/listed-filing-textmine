"""抓取巨潮年报或 SEC 10-K/10-Q。"""

from __future__ import annotations

import argparse

from filingtext.sources import download_cninfo, download_edgar


def main() -> None:
    parser = argparse.ArgumentParser(description="下载年报或 10-K/10-Q 原文")
    sub = parser.add_subparsers(dest="cmd", required=True)

    cninfo = sub.add_parser("cninfo", help="巨潮资讯 A 股年度报告 PDF")
    cninfo.add_argument("--codes", required=True, help="证券代码，逗号分隔")
    cninfo.add_argument("--start", type=int, required=True)
    cninfo.add_argument("--end", type=int, required=True)
    cninfo.add_argument("--out", default="data/raw")

    edgar = sub.add_parser("edgar", help="SEC EDGAR。需要环境变量 EDGAR_USER_AGENT")
    edgar.add_argument("--tickers", default="", help="如 AAPL,MSFT")
    edgar.add_argument("--ciks", default="", help="如 0000320193")
    edgar.add_argument("--start", type=int, required=True)
    edgar.add_argument("--end", type=int, required=True)
    edgar.add_argument("--forms", default="10-K", help="如 10-K,10-Q")
    edgar.add_argument("--out", default="data/raw")
    edgar.add_argument("--include-amendments", action="store_true")

    args = parser.parse_args()
    if args.cmd == "cninfo":
        saved = download_cninfo(
            [code.strip() for code in args.codes.split(",")],
            args.start,
            args.end,
            args.out,
        )
    else:
        saved = download_edgar(
            [item.strip() for item in args.tickers.split(",") if item.strip()],
            [item.strip() for item in args.ciks.split(",") if item.strip()],
            args.start,
            args.end,
            args.out,
            forms=[item.strip() for item in args.forms.split(",") if item.strip()],
            include_amendments=args.include_amendments,
        )
    print(f"下载 {len(saved)} 个文件到 {args.out}")
    for path in saved:
        print(path)


if __name__ == "__main__":
    main()
