"""批量解析入口。"""

from __future__ import annotations

import argparse
import hashlib
import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from filingtext.config import OUTPUT_DIR, TEXT_DIR
from filingtext.features import apply_corpus, finbert_tone
from filingtext.lexicon import load_loughran_mcdonald
from filingtext.panel import export_panel, summarize, to_frame
from filingtext.parse_job import parse_path

log = logging.getLogger(__name__)

TEXT_SUFFIXES = {".pdf", ".txt", ".htm", ".html"}


def collect_jobs(
    input_dir: str | Path,
    market: str | None = None,
    sections: list[str] | None = None,
    manifest: str | Path | None = None,
    tone_override: dict | None = None,
    limit: int = 0,
) -> list[dict]:
    root = Path(input_dir)
    manifest_path = Path(manifest) if manifest else root / "manifest.csv"
    meta: dict[str, dict] = {}
    if manifest_path.exists():
        import pandas as pd

        table = pd.read_csv(manifest_path, dtype=str, encoding="utf-8-sig").fillna("")
        for row in table.to_dict("records"):
            path = Path(row["path"])
            if not path.is_absolute():
                path = root / path
            meta[str(path.resolve())] = row
    discovered = [p.resolve() for p in root.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES]
    if meta:
        known = {Path(p).resolve() for p in meta}
        paths = [p for p in discovered if p in known] + [p for p in discovered if p not in known]
        # 清单里登记、但扫描没看到的文件也保留，方便清单使用绝对路径。
        for key in meta:
            candidate = Path(key)
            if candidate not in paths and candidate.suffix.lower() in TEXT_SUFFIXES:
                paths.append(candidate)
    else:
        paths = discovered
    jobs = []
    for path in paths:
        info = meta.get(str(path.resolve()), {})
        hint = (info.get("market") or market or "").upper()
        year = info.get("fiscal_year") or None
        jobs.append(
            {
                "path": str(path.resolve()),
                "market": hint if hint in {"CN", "US"} else None,
                "ticker": info.get("ticker") or None,
                "firm_name": info.get("firm_name") or None,
                "fiscal_year": int(year) if year else None,
                "report_type": info.get("report_type") or None,
                "sections": sections,
                "tone_override": tone_override,
            }
        )
    if limit:
        jobs = jobs[:limit]
    return jobs


def run(
    input_dir: str | Path,
    output_dir: str | Path = OUTPUT_DIR,
    market: str | None = None,
    sections: list[str] | None = None,
    manifest: str | Path | None = None,
    workers: int = 1,
    lm_path: str | None = None,
    use_finbert: bool = False,
    limit: int = 0,
    text_dir: str | Path | None = None,
    on_event=None,
) -> dict:
    tone_override = load_loughran_mcdonald(lm_path) if lm_path else None
    jobs = collect_jobs(input_dir, market=market, sections=sections, manifest=manifest, tone_override=tone_override, limit=limit)
    if not jobs:
        raise FileNotFoundError(f"没有可解析的 PDF/HTML/TXT：{input_dir}")
    batches = []
    if workers <= 1:
        for job in jobs:
            name = Path(job["path"]).name
            if on_event:
                on_event({"stage": "章节切分", "detail": name, "state": "run"})
            try:
                batch = parse_path(job)
            except Exception as exc:
                if on_event:
                    on_event({"stage": "章节切分", "detail": f"{name}：{exc}", "state": "fail"})
                continue
            found = sum(1 for row in batch if row.get("found"))
            if on_event:
                state = "ok" if found else "fail"
                on_event({"stage": "章节切分", "detail": f"{name}，有效章节 {found}", "state": state})
            batches.append(batch)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            batches = list(pool.map(parse_path, jobs))
    if on_event:
        on_event({"stage": "指标计算", "detail": "词频、TF-IDF 与同比", "state": "run"})
    records = [row for batch in batches for row in batch]
    if use_finbert:
        _attach_finbert(records)
    _persist_text(records, Path(text_dir) if text_dir else TEXT_DIR)
    apply_corpus(records)
    frame = to_frame(records)
    paths = export_panel(frame, output_dir)
    paths["summary"] = summarize(frame)
    return paths


def _attach_finbert(records: list[dict]) -> None:
    for row in records:
        body = row.get("section_text") or ""
        if not body or row.get("market") != "US":
            continue
        scores = finbert_tone(body)
        if scores:
            row.update(scores)
            row["tone_method"] = (row.get("tone_method") or "seed_dictionary") + "+finbert"


def _persist_text(records: list[dict], text_dir: Path = TEXT_DIR) -> None:
    text_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for row in records:
        doc_id = row.get("doc_id") or "doc"
        if doc_id in seen:
            digest = hashlib.sha1(str(row.get("source_path", "")).encode("utf-8")).hexdigest()[:6]
            doc_id = f"{doc_id}_{digest}"
            row["doc_id"] = doc_id
        seen.add(doc_id)
    for row in records:
        body = row.pop("section_text", "") or ""
        if not body or not row.get("found"):
            row["text_path"] = ""
            row["text_sha1"] = ""
            continue
        dest = text_dir / f"{row['doc_id']}.txt"
        dest.write_text(body, encoding="utf-8")
        row["text_path"] = str(dest)
        row["text_sha1"] = hashlib.sha1(body.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="批量解析年报或 10-K/10-Q，导出文本特征面板")
    parser.add_argument("--input", required=True, help="原始文件目录，可含 manifest.csv")
    parser.add_argument("--output", default=str(OUTPUT_DIR), help="面板输出目录")
    parser.add_argument("--market", choices=["CN", "US", "AUTO"], default="AUTO")
    parser.add_argument("--sections", default="", help="逗号分隔，例如 mda,risk。留空则按市场使用默认章节")
    parser.add_argument("--workers", type=int, default=1, help="进程数。Windows 建议先用 1 验证，再加大")
    parser.add_argument("--lm", default="", help="Loughran-McDonald 官方 CSV/XLSX，用于覆盖英文语气词")
    parser.add_argument("--finbert", action="store_true", help="对英文章节额外计算 FinBERT-tone（需安装 transformers 并下载模型）")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)
    market = None if args.market == "AUTO" else args.market
    sections = [s.strip() for s in args.sections.split(",") if s.strip()] or None
    paths = run(
        input_dir=args.input,
        output_dir=args.output,
        market=market,
        sections=sections,
        workers=max(1, args.workers),
        lm_path=args.lm or None,
        use_finbert=args.finbert,
        limit=args.limit,
    )
    summary = paths["summary"]
    print(
        f"完成：{summary['n_found']}/{summary['n_rows']} 个章节有效，"
        f"{summary['n_firms']} 家公司，年份 {summary['years']}"
    )
    print(f"parquet  {paths['parquet']}")
    print(f"dta      {paths['dta']}")
    print(f"duckdb   {paths['duckdb']}")
    print(f"图       {paths['figure']}")


if __name__ == "__main__":
    main()
