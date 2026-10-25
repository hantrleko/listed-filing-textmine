"""页眉页脚、页码和报表噪点清洗。"""

from __future__ import annotations

import re
from collections import Counter

_PAGE_MARK = re.compile(r"^\[\[PAGE:(\d+)\]\]$")
_PAGE_LINE = re.compile(
    r"^(?:"
    r"\d{1,4}\s*/\s*\d{1,4}"
    r"|第?\s*\d{1,4}\s*页(?:\s*/\s*共?\s*\d+\s*页)?"
    r"|page\s+\d+(?:\s+of\s+\d+)?"
    r"|-\s*\d{1,4}\s*-"
    r")$",
    re.I,
)
_NOISE = [
    re.compile(r"^\s*\d{1,4}\s*$"),
    re.compile(r"^\s*-?\s*\d{1,4}\s*-?\s*$"),
    re.compile(r"巨潮资讯"),
    re.compile(r"www\.cninfo\.com\.cn", re.I),
    re.compile(r"^\s*[\W_]+\s*$"),
]

CLEANING_RULES = [
    "页码行（如 7 / 143、第 7 页）整行删除，不进入分词、词频分母和可读性指标。[[PAGE:n]] 只用来定位。",
    "表格按 PDF 版面框识别，行首标成 [[TABLE]] 后删除。带逗号或句号的叙述即使含有金额、名次，也不按数字个数删除。",
    "版面框没有罩住时，仍删除括号数字列、几乎没有汉字的残句，以及「营业收入 / 毛利率 / 同比」这类拆开的表头。",
    "跨页重复的短页眉页脚删除。章节标题行保留，用来切边界。",
    "PDF 顶栏 6% 和底栏 6% 在抽字时丢掉。指标只对清洗后的章节正文计算。原文和删除记录留作对照。",
]

_HEADER_BITS = (
    "营业收入",
    "营业成本",
    "毛利率",
    "同比",
    "本期数",
    "上年同期",
    "变动比例",
    "销售费用",
    "管理费用",
)


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


def is_page_mark(line: str) -> bool:
    return bool(_PAGE_MARK.match(line.strip()))


def _cjk_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def is_narrative_line(line: str) -> bool:
    """有标点的叙述句保留。不能因为一行里出现 501、884.27 就当成表格。"""
    s = line.strip()
    if s.startswith("[[TABLE]]"):
        return False
    cjk = _cjk_count(s)
    if cjk >= 8 and re.search(r"[，。；：、！？]", s):
        return True
    return cjk >= 18


def noise_reason(line: str) -> str | None:
    s = line.strip()
    if not s or is_page_mark(s):
        return None
    if s.startswith("[[TABLE]]"):
        bare = s.removeprefix("[[TABLE]]").strip()
        if is_narrative_line(bare):
            return "表格内叙述"
        return "表格区域"
    if len(s) <= 1:
        return "过短"
    if _PAGE_LINE.match(s):
        return "页码"
    if any(p.search(s) for p in _NOISE) and len(s) <= 40:
        return "页眉页脚或空行"
    if is_narrative_line(s):
        return None
    paren_numbers = re.findall(r"\(\s*-?\d[\d,]*\s*\)", s)
    cjk = _cjk_count(s)
    if len(paren_numbers) >= 2 and cjk <= 24:
        return "表格行"
    if cjk <= 2 and re.search(r"\d", s) and len(s) <= 16:
        return "残句"
    if _header_fragment(s):
        return "表头"
    if is_table_noise(s):
        return "表格行"
    return None


def _header_fragment(line: str) -> bool:
    s = line.strip()
    if len(s) > 48 or re.search(r"[。！？]", s):
        return False
    return sum(label in s for label in _HEADER_BITS) >= 2


def is_noise_line(line: str) -> bool:
    return noise_reason(line) is not None


def is_table_noise(line: str) -> bool:
    s = line.strip()
    if s.startswith("[[TABLE]]") or is_narrative_line(s):
        return False
    if len(s) < 8:
        return False
    digits = sum(ch.isdigit() for ch in s)
    numbers = re.findall(r"\d+(?:\.\d+)?", s)
    if digits / len(s) > 0.35:
        return True
    if len(numbers) >= 4 and digits / len(s) > 0.22:
        return True
    if len(numbers) >= 6 and len(s) <= 400:
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
        if is_page_mark(ln) or ln.strip().startswith("[[TABLE]]"):
            kept.append(ln.strip())
            continue
        if key and freq[key] >= min_repeat and len(key) <= max_len and not _looks_like_header(ln):
            continue
        kept.append(ln.rstrip())
    return "\n".join(kept).strip()


def drop_repeated_pages(pages: list[list[str]], rate: float = 0.4) -> str:
    """去掉跨页重复的短页眉页脚。页码和表格留到 clean_body_report，以便逐行记录删除原因。"""
    n = len(pages)
    freq: Counter[str] = Counter()
    for lines in pages:
        freq.update({_key(ln) for ln in lines if ln.strip()})
    threshold = max(3, int(rate * n + 0.999))
    kept: list[str] = []
    for lines in pages:
        for ln in lines:
            if is_page_mark(ln) or ln.strip().startswith("[[TABLE]]"):
                kept.append(ln.strip())
                continue
            key = _key(ln)
            if (
                n >= 3
                and key
                and freq[key] >= threshold
                and len(key) <= 60
                and not _looks_like_header(ln)
            ):
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
    cleaned, _drops, _meta = clean_body_report(text)
    return cleaned


def clean_body_report(text: str, skip_lines: set[str] | None = None) -> tuple[str, list[dict], dict]:
    """返回清洗后正文、删除记录，以及页码范围。

    页码行和表格行不会留下。[[PAGE:n]] 只用来定位，不进入计分文本。
    """
    skip = skip_lines or set()
    kept: list[str] = []
    drops: list[dict] = []
    page: int | None = None
    first_page: int | None = None
    last_page: int | None = None
    dropped_n = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        mark = _PAGE_MARK.match(line)
        if mark:
            page = int(mark.group(1))
            continue
        if line in skip:
            dropped_n += 1
            drops.append({"page": page, "reason": "章节标题行", "line": line[:120]})
            continue
        reason = noise_reason(line)
        if reason:
            dropped_n += 1
            shown = line.removeprefix("[[TABLE]]")
            drops.append({"page": page, "reason": reason, "line": shown[:120]})
            continue
        if first_page is None:
            first_page = page
        last_page = page
        kept.append(line)
    meta = {"page_start": first_page, "page_end": last_page, "n_dropped_lines": dropped_n}
    return "\n".join(kept).strip(), drops, meta
