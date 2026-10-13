"""页眉页脚、页码和报表噪点清洗。"""

from __future__ import annotations

import re
from collections import Counter

_NOISE = [
    re.compile(r"^\s*\d{1,4}\s*$"),
    re.compile(r"^\s*-?\s*\d{1,4}\s*-?\s*$"),
    re.compile(r"^\s*第?\s*\d{1,4}\s*页(\s*/\s*共?\s*\d+\s*页)?\s*$"),
    re.compile(r"巨潮资讯"),
    re.compile(r"www\.cninfo\.com\.cn", re.I),
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.I),
    re.compile(r"^\s*[\W_]+\s*$"),
]


def normalize(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\ufeff", "").replace("\u3000", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = re.sub(r"(?<=[A-Za-z])-\n(?=[a-z])", "", text)
    lines = [collapse_cjk_spacing(ln.rstrip()) for ln in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def collapse_cjk_spacing(line: str) -> str:
    """部分 PDF 会把每个汉字拆开。只在连续单字空格时合并。"""
    if re.search(r"(?:[\u4e00-\u9fff]\s+){4,}", line):
        return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", line)
    return line


def is_noise_line(line: str) -> bool:
    s = line.strip()
    if len(s) <= 1:
        return True
    if any(p.search(s) for p in _NOISE) and len(s) <= 40:
        return True
    if is_table_noise(s):
        return True
    return False


def is_table_noise(line: str) -> bool:
    s = line.strip()
    if len(s) < 8:
        return False
    digits = sum(ch.isdigit() for ch in s)
    if digits / len(s) > 0.45:
        return True
    if len(re.findall(r"\d+(?:\.\d+)?", s)) >= 5 and len(s) < 160:
        return True
    return False


def _key(line: str) -> str:
    return re.sub(r"\s+", "", line).lower()


def drop_repeated_lines(text: str, min_repeat: int = 4, max_len: int = 60) -> str:
    lines = text.splitlines()
    freq = Counter(_key(ln) for ln in lines if ln.strip())
    kept: list[str] = []
    for ln in lines:
        key = _key(ln)
        if key and freq[key] >= min_repeat and len(key) <= max_len and not _looks_like_header(ln):
            continue
        if ln.strip() and is_noise_line(ln):
            continue
        kept.append(ln.rstrip())
    return "\n".join(kept).strip()


def drop_repeated_pages(pages: list[list[str]], rate: float = 0.4) -> str:
    """去掉跨页重复的短行（页眉页脚），并丢掉表格噪点。"""
    n = len(pages)
    freq: Counter[str] = Counter()
    for lines in pages:
        freq.update({_key(ln) for ln in lines if ln.strip()})
    threshold = max(3, int(rate * n + 0.999))
    kept: list[str] = []
    for lines in pages:
        for ln in lines:
            key = _key(ln)
            if (
                n >= 3
                and key
                and freq[key] >= threshold
                and len(key) <= 60
                and not _looks_like_header(ln)
            ):
                continue
            if ln.strip() and is_noise_line(ln):
                continue
            if ln.strip():
                kept.append(ln.strip())
    return "\n".join(kept).strip()


def _looks_like_header(line: str) -> bool:
    return bool(
        re.search(r"第[一二三四五六七八九十百零〇0-9]{1,3}[章节]", line)
        or re.search(r"(?i)\bitem\s+\d", line)
    )


def clean_body(text: str) -> str:
    kept = []
    for ln in text.splitlines():
        if not ln.strip():
            continue
        if is_noise_line(ln):
            continue
        kept.append(ln.strip())
    return "\n".join(kept).strip()
