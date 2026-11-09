"""章节质量标记：可比性、同比长度跳变。"""

from __future__ import annotations

import csv
import re
import statistics
from pathlib import Path

from filingtext.config import MIN_COMPARE_TOKENS
from filingtext.sections import leaks_sibling_heading

_POINTER = re.compile(r"敬请投资者|详见本报告|请参阅|详见第[一二三四五六七八九十\d]+节")

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


def _suppress_ratios(record: dict) -> None:
    for key in _SUPPRESSED_RATIOS:
        record[key] = None


def apply_record_quality(record: dict, raw_body: str, rank: int, cleaned_body: str = "") -> None:
    flags: list[str] = []
    body = cleaned_body or raw_body
    if not record.get("found"):
        flags.append("section_missing")
    else:
        if (record.get("n_tokens") or 0) < MIN_COMPARE_TOKENS:
            flags.append("short_text")
        if record.get("page_start") in (None, ""):
            flags.append("location_missing")
        if leaks_sibling_heading(raw_body, rank):
            flags.append("boundary_suspect")
        head = body[:600]
        if _POINTER.search(head) and (record.get("n_tokens") or 0) < 120:
            flags.append("pointer_text")
    record["quality_flags"] = "|".join(flags)
    bad = {"short_text", "boundary_suspect", "pointer_text", "yoy_length_jump"}
    record["comparable"] = int(bool(record.get("found")) and not any(flag in flags for flag in bad))
    if not record["comparable"]:
        _suppress_ratios(record)
    apply_section_status(record)


def apply_section_status(record: dict) -> None:
    """已确认没有这一节的年报写成 absent，空值仍然不是强度 0。"""
    if record.get("found"):
        record["section_status"] = "found"
        return
    if _confirmed_absent(record.get("ticker"), record.get("fiscal_year"), record.get("section")):
        record["section_status"] = "absent"
        flags = [part for part in (record.get("quality_flags") or "").split("|") if part and part != "section_missing"]
        if "section_absent" not in flags:
            flags.append("section_absent")
        record["quality_flags"] = "|".join(flags)
        record["comparable"] = 0
        _suppress_ratios(record)
        return
    record["section_status"] = "missing"


def _confirmed_absent(ticker, fiscal_year, section) -> bool:
    if fiscal_year in ("", None) or section in ("", None):
        return False
    key = (str(ticker).zfill(6)[-6:], int(fiscal_year), str(section))
    return key in _ABSENT


def _load_absent() -> set[tuple[str, int, str]]:
    path = Path(__file__).with_name("confirmed_absent.csv")
    if not path.exists():
        return set()
    found = set()
    for row in csv.DictReader(path.open(encoding="utf-8-sig")):
        if row.get("status") != "absent":
            continue
        found.add((str(row["ticker"]).zfill(6), int(row["fiscal_year"]), row["section"]))
    return found


_ABSENT = _load_absent()


def apply_yoy_quality(records: list[dict]) -> None:
    """只把明显过短的年份标成跳变。正常的长章节不因为同组里有一年残缺而被丢掉。"""
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in records:
        if row.get("found") and (row.get("n_tokens") or 0) > 0:
            groups.setdefault((str(row.get("ticker")), str(row.get("section"))), []).append(row)
    for rows in groups.values():
        if len(rows) < 2:
            continue
        long = [float(r["n_tokens"]) for r in rows if float(r["n_tokens"]) >= 1000]
        if not long:
            continue
        base = statistics.median(long)
        for row in rows:
            tokens = float(row["n_tokens"])
            if tokens >= 1000 or tokens / base >= 0.25:
                continue
            flags = [part for part in (row.get("quality_flags") or "").split("|") if part]
            if "yoy_length_jump" not in flags:
                flags.append("yoy_length_jump")
            row["quality_flags"] = "|".join(flags)
            if row.get("comparable"):
                row["comparable"] = 0
                _suppress_ratios(row)


def apply_title_shift(records: list[dict]) -> None:
    """同一公司已找到的风险标题不一致时，标出偏离多数标题的年份。

    没切到和已确认缺失的年份不参加比较。标记只说明标题换了，不改可比性。
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in records:
        if str(row.get("section")) != "risk" or not row.get("found"):
            continue
        if row.get("section_status") == "absent":
            continue
        title = str(row.get("section_title") or "").strip()
        if not title:
            continue
        groups.setdefault((str(row.get("ticker")), "risk"), []).append(row)
    for rows in groups.values():
        titles = [str(row.get("section_title") or "").strip() for row in rows]
        if len(set(titles)) < 2:
            continue
        counts: dict[str, int] = {}
        for title in titles:
            counts[title] = counts.get(title, 0) + 1
        top = max(counts.values())
        modes = {title for title, count in counts.items() if count == top}
        for row, title in zip(rows, titles):
            if len(modes) == 1 and title in modes:
                continue
            _append_flag(row, "title_shift")


def _append_flag(row: dict, flag: str) -> None:
    flags = [part for part in (row.get("quality_flags") or "").split("|") if part]
    if flag not in flags:
        flags.append(flag)
    row["quality_flags"] = "|".join(flags)
