"""批量解析入口。"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from filingtext import __version__
from filingtext.clean import CLEANING_RULES
from filingtext.config import OUTPUT_DIR, TEXT_DIR
from filingtext.features import apply_corpus, finbert_tone
from filingtext.lexicon import DICTIONARY_VERSION, load_loughran_mcdonald
from filingtext.panel import export_panel, summarize, to_frame
from filingtext.parse_job import parse_path
from filingtext.quality import apply_yoy_quality

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
    by_name = {Path(key).name: row for key, row in meta.items()}
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
        info = meta.get(str(path.resolve()), {}) or by_name.get(path.name, {})
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
                "filing_date": info.get("filing_date") or "",
                "source_url": info.get("source_url") or "",
                "exchange": info.get("exchange") or "",
                "fetched_at": info.get("fetched_at") or "",
                "data_version": info.get("data_version") or "",
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
    run_id: str | None = None,
) -> dict:
    run_id = run_id or _new_run_id()
    tone_override = load_loughran_mcdonald(lm_path) if lm_path else None
    jobs = collect_jobs(input_dir, market=market, sections=sections, manifest=manifest, tone_override=tone_override, limit=limit)

    def emit(stage: str, detail: str, state: str) -> None:
        if not on_event:
            return
        on_event({"run_id": run_id, "stage": stage, "detail": detail, "state": state})

    if not jobs:
        raise FileNotFoundError(f"没有可解析的 PDF/HTML/TXT：{input_dir}")
    emit("解析", f"共 {len(jobs)} 份文件", "run")
    batches = []
    if workers <= 1:
        for job in jobs:
            name = Path(job["path"]).name
            emit("章节切分", name, "run")
            try:
                batch = parse_path(job)
            except Exception as exc:
                emit("章节切分", f"{name}：{exc}", "fail")
                continue
            found = sum(1 for row in batch if row.get("found"))
            emit("章节切分", f"{name}，有效章节 {found}", "ok" if found else "fail")
            batches.append(batch)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            batches = list(pool.map(parse_path, jobs))
    emit("指标计算", "词频、TF-IDF 与同比", "run")
    records = [row for batch in batches for row in batch]
    if use_finbert:
        _attach_finbert(records)
    emit("清洗落盘", "正文、原文与删除日志", "run")
    _persist_text(records, Path(text_dir) if text_dir else TEXT_DIR)
    apply_corpus(records)
    apply_yoy_quality(records)
    frame = to_frame(records)
    emit("导出", "parquet / dta / duckdb / 因子表", "run")
    paths = export_panel(frame, output_dir)
    paths["summary"] = summarize(frame)
    paths["run_id"] = run_id
    _write_run_manifest(Path(output_dir), run_id, records, paths, len(jobs))
    emit("完成", f"有效章节 {paths['summary']['n_found']}/{paths['summary']['n_rows']}", "ok")
    return paths


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def _write_run_manifest(output_dir: Path, run_id: str, records: list[dict], paths: dict, n_jobs: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "app_version": __version__,
        "dictionary_version": DICTIONARY_VERSION,
        "cleaning_rules": CLEANING_RULES,
        "n_jobs": n_jobs,
        "n_records": len(records),
        "outputs": {key: str(value) for key, value in paths.items() if key != "summary"},
    }
    dest = output_dir / f"run_{run_id}.json"
    dest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["run_manifest"] = str(dest)


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
        raw_body = row.pop("section_raw", "") or ""
        clean_log = row.pop("clean_log", []) or []
        body = row.pop("section_text", "") or ""
        row.pop("section_header", None)
        if not body or not row.get("found"):
            row["text_path"] = ""
            row["raw_text_path"] = ""
            row["clean_log_path"] = ""
            row["text_sha1"] = ""
            if raw_body:
                raw_dest = text_dir / f"{row['doc_id']}.raw.txt"
                raw_dest.write_text(raw_body, encoding="utf-8")
                row["raw_text_path"] = str(raw_dest)
            if clean_log:
                log_dest = text_dir / f"{row['doc_id']}.cleanlog.json"
                log_dest.write_text(json.dumps(clean_log, ensure_ascii=False), encoding="utf-8")
                row["clean_log_path"] = str(log_dest)
            continue
        dest = text_dir / f"{row['doc_id']}.txt"
        dest.write_text(body, encoding="utf-8")
        raw_dest = text_dir / f"{row['doc_id']}.raw.txt"
        raw_dest.write_text(raw_body, encoding="utf-8")
        log_dest = text_dir / f"{row['doc_id']}.cleanlog.json"
        log_dest.write_text(json.dumps(clean_log, ensure_ascii=False), encoding="utf-8")
        row["text_path"] = str(dest)
        row["raw_text_path"] = str(raw_dest)
        row["clean_log_path"] = str(log_dest)
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
