"""章节质量标记：可比性、同比长度跳变。"""

from __future__ import annotations

import re
import statistics

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


def apply_yoy_quality(records: list[dict]) -> None:
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in records:
        if row.get("found") and (row.get("n_tokens") or 0) > 0:
            groups.setdefault((str(row.get("ticker")), str(row.get("section"))), []).append(row)
    for rows in groups.values():
        if len(rows) < 2:
            continue
        tokens = [float(r["n_tokens"]) for r in rows]
        med = statistics.median(tokens)
        if med <= 0:
            continue
        for row in rows:
            ratio = float(row["n_tokens"]) / med
            if 0.3 <= ratio <= 3.0:
                continue
            flags = [part for part in (row.get("quality_flags") or "").split("|") if part]
            if "yoy_length_jump" in flags:
                continue
            flags.append("yoy_length_jump")
            row["quality_flags"] = "|".join(flags)
            if row.get("comparable"):
                row["comparable"] = 0
                _suppress_ratios(row)
