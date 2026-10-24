"""单文件解析。放在独立模块里，便于 Windows 多进程导入。"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from filingtext import __version__
from filingtext.clean import clean_body_report, normalize
from filingtext.config import DEFAULT_SECTIONS, MIN_COMPARE_TOKENS, MIN_FOUND_CHARS
from filingtext.extract import read_filing
from filingtext.features import score_document
from filingtext.lexicon import DICTIONARY_VERSION
from filingtext.sections import CN_BARE_TITLES, leaks_sibling_heading, split_sections

log = logging.getLogger(__name__)

_FILENAME = re.compile(
    r"(?P<ticker>[A-Za-z0-9.]+?)[_-](?P<year>19\d{2}|20\d{2})(?:[_-](?P<kind>[A-Za-z0-9]+))?",
    re.I,
)


def parse_path(job: dict) -> list[dict]:
    path = Path(job["path"])
    try:
        text = normalize(read_filing(path))
        return parse_text(text, {**job, "path": str(path), "source_sha1": _sha1_file(path)})
    except Exception as exc:
        log.exception("解析失败 %s", path)
        meta = parse_filename(path)
        return [
            _base_record(
                {
                    **job,
                    "path": str(path),
                    "ticker": job.get("ticker") or meta.get("ticker") or "UNKNOWN",
                    "fiscal_year": job.get("fiscal_year") or meta.get("fiscal_year"),
                    "market": (job.get("market") or "CN"),
                },
                section=(job.get("sections") or ["mda"])[0],
                found=0,
                error=f"{type(exc).__name__}: {exc}"[:500],
            )
        ]


def parse_text(text: str, meta: dict) -> list[dict]:
    path = Path(meta.get("path") or "memory.txt")
    filename_meta = parse_filename(path)
    market = _market(text, meta.get("market"))
    year = meta.get("fiscal_year") or filename_meta.get("fiscal_year") or sniff_year(text, market)
    if year is not None:
        year = int(year)
    ticker = (meta.get("ticker") or filename_meta.get("ticker") or "UNKNOWN").strip()
    firm = meta.get("firm_name") or sniff_name(text, market)
    kind = meta.get("report_type") or filename_meta.get("kind") or ""
    form = sniff_form(text, market, str(kind))
    report_type = form if market == "US" else "annual"
    filing_date = str(meta.get("filing_date") or "")
    quarter = _fiscal_quarter(report_type)
    sections = meta.get("sections") or DEFAULT_SECTIONS[market]
    tone_override = meta.get("tone_override")
    found_sections = split_sections(text, market, form=form)
    rows = []
    for key in sections:
        section = found_sections.get(key)
        raw_body = section.text if section else ""
        body, drops, provenance = clean_body_report(
            raw_body,
            skip_lines=CN_BARE_TITLES if market == "CN" else None,
        )
        found = int(len(body) >= MIN_FOUND_CHARS)
        record = _base_record(
            {
                "path": str(path),
                "market": market,
                "ticker": ticker,
                "firm_name": firm,
                "fiscal_year": year,
                "report_type": report_type,
                "filing_date": filing_date,
                "available_date": filing_date,
                "fiscal_quarter": quarter,
                "source_url": meta.get("source_url") or "",
                "source_sha1": meta.get("source_sha1") or _sha1_file(path),
                "exchange": meta.get("exchange") or "",
                "fetched_at": meta.get("fetched_at") or "",
                "data_version": meta.get("data_version") or "",
                "cik": meta.get("cik") or "",
            },
            section=key,
            found=found,
            error="",
        )
        record["form"] = form
        record["page_start"] = provenance["page_start"]
        record["page_end"] = provenance["page_end"]
        record["n_dropped_lines"] = provenance["n_dropped_lines"]
        record["section_header"] = section.header if section else ""
        record["section_raw"] = raw_body
        record["clean_log"] = drops
        record["section_text"] = body if found else ""
        if found:
            record.update(score_document(body, market, tone_override=tone_override))
        else:
            record.update(_empty_scores())
        _apply_quality(record, raw_body, section.rank if section else 9)
        rows.append(record)
    return rows


def parse_filename(path: Path) -> dict:
    matched = _FILENAME.search(path.stem)
    if not matched:
        return {}
    return {
        "ticker": matched.group("ticker"),
        "fiscal_year": int(matched.group("year")),
        "kind": matched.group("kind") or "",
    }


def sniff_year(text: str, market: str) -> int | None:
    if market == "CN":
        matched = re.search(r"(20\d{2}|19\d{2})\s*年\s*年度报告", text[:2500])
        if matched:
            return int(matched.group(1))
    matched = re.search(r"for the fiscal year ended[\s\S]{0,80}?(20\d{2}|19\d{2})", text[:4000], re.I)
    if matched:
        return int(matched.group(1))
    matched = re.search(r"\b(20\d{2})\b", text[:800])
    return int(matched.group(1)) if matched else None


def sniff_name(text: str, market: str) -> str:
    if market == "CN":
        matched = re.search(r"([\u4e00-\u9fff]{2,30}股份有限公司)", text[:500])
        return matched.group(1) if matched else ""
    matched = re.search(
        r"\b([A-Z][A-Za-z0-9&.,' ]{2,80}?(?:INC\.|CORP\.|CORPORATION|LTD\.|LLC))\b",
        text[:1800],
    )
    return re.sub(r"\s+", " ", matched.group(1)).strip() if matched else ""


def sniff_form(text: str, market: str, hint: str) -> str:
    if market == "CN":
        return "annual"
    key = hint.upper().replace("_", "").replace("-", "")
    if "10Q" in key:
        return "10-Q"
    if "10K" in key:
        return "10-K"
    head = text[:2500].upper()
    if re.search(r"\bFORM\s+10-Q\b", head) or re.search(r"\b10-Q\b", head[:400]):
        return "10-Q"
    return "10-K"


def _market(text: str, hint: str | None) -> str:
    if hint and str(hint).upper() in {"CN", "US"}:
        return str(hint).upper()
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text[:4000]))
    return "CN" if cjk >= 20 else "US"


def filing_ids(market: str, ticker: str) -> dict[str, str]:
    """A 股代码补成 6 位字符串，避免和财务数据合并时丢掉前导零。"""
    market = market.upper()
    ticker = (ticker or "").strip()
    stkcd = ""
    cik = ""
    if market == "CN":
        digits = re.sub(r"\D", "", ticker)
        if digits:
            stkcd = digits.zfill(6)[-6:]
            ticker = stkcd
    elif market == "US" and ticker.isdigit():
        cik = str(int(ticker)).zfill(10)
    return {"ticker": ticker, "stkcd": stkcd, "cik": cik}


def _base_record(meta: dict, section: str, found: int, error: str) -> dict:
    market = str(meta.get("market") or "CN").upper()
    ids = filing_ids(market, str(meta.get("ticker") or "UNKNOWN"))
    ticker = ids["ticker"]
    year = meta.get("fiscal_year")
    year_label = str(year) if year else "NA"
    report_type = meta.get("report_type") or ("annual" if market == "CN" else "10-K")
    return {
        "doc_id": f"{market}_{ticker}_{year_label}_{report_type}_{section}",
        "market": market,
        "ticker": ticker,
        "stkcd": ids["stkcd"],
        "cik": meta.get("cik") or ids["cik"],
        "firm_name": meta.get("firm_name") or "",
        "fiscal_year": year,
        "report_type": report_type,
        "form": report_type,
        "section": section,
        "found": found,
        "is_duplicate": 0,
        "source_path": meta.get("path") or "",
        "text_path": "",
        "text_sha1": "",
        "filing_date": meta.get("filing_date") or "",
        "available_date": meta.get("available_date") or meta.get("filing_date") or "",
        "fiscal_quarter": meta.get("fiscal_quarter") if meta.get("fiscal_quarter") not in ("", None) else _fiscal_quarter(str(report_type)),
        "pit_ready": int(bool(meta.get("available_date") or meta.get("filing_date"))),
        "source_url": meta.get("source_url") or "",
        "source_sha1": meta.get("source_sha1") or "",
        "exchange": meta.get("exchange") or "",
        "fetched_at": meta.get("fetched_at") or "",
        "data_version": meta.get("data_version") or DICTIONARY_VERSION,
        "app_version": __version__,
        "error": error,
    }


_SUPPRESSED_RATIOS = (
    "fog_index",
    "avg_sentence_len",
    "complex_word_ratio",
    "tone_pos",
    "tone_neg",
    "tone_unc",
    "tone_lit",
    "tone_net",
    "esg_per_k",
    "esg_per_char_k",
    "digital_per_k",
    "digital_per_char_k",
    "geopol_per_k",
    "geopol_per_char_k",
)


def _apply_quality(record: dict, raw_body: str, rank: int) -> None:
    flags: list[str] = []
    if not record.get("found"):
        flags.append("section_missing")
    else:
        if (record.get("n_tokens") or 0) < MIN_COMPARE_TOKENS:
            flags.append("short_text")
        if record.get("page_start") in (None, ""):
            flags.append("location_missing")
        if leaks_sibling_heading(raw_body, rank):
            flags.append("boundary_suspect")
    record["quality_flags"] = "|".join(flags)
    record["comparable"] = int(bool(record.get("found")) and not any(flag in flags for flag in ("short_text", "boundary_suspect")))
    if record["comparable"]:
        return
    for key in _SUPPRESSED_RATIOS:
        record[key] = None


def _sha1_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fiscal_quarter(report_type: str) -> int | None:
    kind = (report_type or "").upper().replace("_", "-")
    if kind in {"ANNUAL", "10-K", "10K"}:
        return 4
    return None


def _empty_scores() -> dict:
    data = {
        "n_chars": 0,
        "n_tokens": 0,
        "n_sentences": 0,
        "fog_index": None,
        "avg_sentence_len": None,
        "complex_word_ratio": None,
        "fog_method": "",
        "tone_pos": None,
        "tone_neg": None,
        "tone_unc": None,
        "tone_lit": None,
        "tone_net": None,
        "tone_method": "",
        "finbert_pos": None,
        "finbert_neg": None,
        "finbert_neu": None,
        "token_counts": {},
        "term_hits": {"esg": {}, "digital": {}, "geopol": {}},
    }
    for name in ("esg", "digital", "geopol"):
        data[f"{name}_count"] = 0
        data[f"{name}_per_k"] = None
        data[f"{name}_tfidf"] = None
    data["yoy_similarity"] = None
    data["disclosure_drift"] = None
    return data
