"""年报 / 10-K / 10-Q 章节切分。

硬边界是「第X节」和 Item 标题。目录行（点线或行末页码）不作为正文起点。
同一章节多次出现时，保留优先级更高、正文跨度更长的那一次。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

CN_TITLES: list[tuple[str, int, str]] = [
    ("mda", 0, "管理层讨论与分析"),
    ("mda", 1, "经营情况讨论与分析"),
    ("mda", 1, "讨论与分析"),
    ("mda", 2, "董事会报告"),
    ("governance", 0, "公司治理结构"),
    ("governance", 1, "公司治理"),
    ("esg", 0, "环境和社会责任"),
    ("esg", 1, "环境与社会责任"),
    ("esg", 2, "社会责任"),
    ("material", 0, "重要事项"),
    ("shares", 0, "股份变动及股东情况"),
    ("shares", 1, "股份变动和股东情况"),
    ("financials", 0, "财务报告"),
    ("financials", 1, "财务会计报告"),
    ("profile", 0, "公司简介和主要财务指标"),
    ("notice", 0, "重要提示、目录和释义"),
    ("notice", 1, "重要提示、目录及释义"),
    ("risk", 0, "公司面临的风险和应对措施"),
    ("risk", 1, "可能面对的风险"),
    ("risk", 2, "可能面临的风险"),
]

US_10K_ITEMS = {
    "1": "business",
    "1A": "risk",
    "1B": "unresolved",
    "1C": "cyber",
    "2": "properties",
    "3": "legal",
    "4": "mine",
    "5": "equity",
    "6": "reserved",
    "7": "mda",
    "7A": "market_risk",
    "8": "financials",
    "9": "accountants",
    "9A": "controls",
    "9B": "other",
    "9C": "disclosure",
    "10": "directors",
    "11": "compensation",
    "12": "ownership",
    "13": "related",
    "14": "fees",
    "15": "exhibits",
}

# 10-Q Part I 的 Item 2 才是 MD&A；Item 1A 仍是风险因素（通常在 Part II）。
US_10Q_ITEMS = {
    "1": "financials",
    "1A": "risk",
    "2": "mda",
    "3": "market_risk",
    "4": "controls",
}

_CN_TITLE_MAP = {title: (section, priority) for section, priority, title in CN_TITLES}
CN_BARE_TITLES = set(_CN_TITLE_MAP)

_CN_TOC = re.compile(
    r"^(?P<head>.*?)(?:[ \t]*[\.·．…]{2,}[ \t]*(?P<page>\d{1,4})|[ \t]{2,}(?P<page2>\d{1,4}))\s*$"
)
_CN_ENUM = re.compile(
    r"^(?:第[一二三四五六七八九十百零〇0-9]{1,3}[章节]|[（(][一二三四五六七八九十]+[)）]、|[一二三四五六七八九十]+、|\d{1,2}[、.．]|\d{1,2}\s+)\s*"
)
_CN_HARD = re.compile(r"第[一二三四五六七八九十百零〇0-9]{1,3}[章节]")
_CN_NUMBERED = re.compile(r"^\d{1,2}\s+")


def _is_hard(head: str) -> bool:
    return bool(_CN_HARD.search(head) or _CN_NUMBERED.match(head.strip()))

_US_ITEM = re.compile(
    r"^[ \t]*item[ \t]+(?P<num>1a|1b|1c|7a|9a|9b|9c|1|2|3|4|5|6|7|8|9|10|11|12|13|14|15)\b"
    r"[ \t]*[\.\:\-–—]*[ \t]*(?P<rest>.*)$",
    re.I,
)


@dataclass
class Anchor:
    section: str
    priority: int
    title: str
    start: int
    content_start: int
    header: str
    toc: bool
    hard: bool

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Section:
    key: str
    title: str
    header: str
    text: str
    start: int
    end: int

    def as_dict(self) -> dict:
        data = asdict(self)
        data["n_chars"] = len(self.text)
        return data


def split_sections(text: str, market: str, form: str | None = None) -> dict[str, Section]:
    market = market.upper()
    anchors = find_anchors(text, market, form=form)
    chosen, boundaries = _choose(anchors)
    chosen.sort(key=lambda a: a.start)
    out: dict[str, Section] = {}
    for anchor in chosen:
        end = next((pos for pos in boundaries if pos > anchor.start), len(text))
        body = text[anchor.content_start : end].strip()
        out[anchor.section] = Section(
            key=anchor.section,
            title=anchor.title,
            header=anchor.header,
            text=body,
            start=anchor.content_start,
            end=end,
        )
    return out


def diagnose_anchors(text: str, market: str, form: str | None = None) -> list[dict]:
    return [a.as_dict() for a in find_anchors(text, market, form=form)]


def find_anchors(text: str, market: str, form: str | None = None) -> list[Anchor]:
    market = market.upper()
    if market == "CN":
        return _anchors_cn(text)
    if market == "US":
        return _anchors_us(text, form=form)
    raise ValueError(f"未知市场 {market}")


def _choose(anchors: list[Anchor]) -> tuple[list[Anchor], list[int]]:
    body = [a for a in anchors if not a.toc]
    pool = body or anchors
    hard = [a for a in pool if a.hard]
    selection_points = sorted(a.start for a in (hard or pool))

    def span(anchor: Anchor) -> int:
        end = next((pos for pos in selection_points if pos > anchor.start), 10**12)
        return end - anchor.start

    grouped: dict[str, list[Anchor]] = {}
    for anchor in pool:
        grouped.setdefault(anchor.section, []).append(anchor)
    chosen: list[Anchor] = []
    for group in grouped.values():
        best = sorted(group, key=lambda a: (a.priority, 0 if a.hard else 1, -span(a)))[0]
        chosen.append(best)
    slice_points = sorted(a.start for a in hard) if hard else sorted(a.start for a in chosen)
    return chosen, slice_points


def _anchors_cn(text: str) -> list[Anchor]:
    anchors: list[Anchor] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        parsed = _parse_cn_line(line)
        if parsed is not None:
            section, priority, title, toc, hard, consumed = parsed
            anchors.append(
                Anchor(
                    section=section,
                    priority=priority,
                    title=title,
                    start=offset,
                    content_start=_content_start(line, offset, consumed),
                    header=line.strip()[:80],
                    toc=toc,
                    hard=hard,
                )
            )
        offset += len(line)
    return anchors


def _content_start(line: str, offset: int, consumed: int) -> int:
    stripped = line.strip()
    if consumed >= len(stripped):
        return offset + len(line)
    leading = len(line) - len(line.lstrip(" \t"))
    return offset + leading + consumed


def _parse_cn_line(line: str) -> tuple[str, int, str, bool, bool, int] | None:
    raw = line.replace("\u3000", " ").strip()
    if not raw:
        return None
    matched = _CN_TOC.match(raw)
    if matched and (matched.group("page") or matched.group("page2")):
        head = matched.group("head").strip()
        title = _CN_ENUM.sub("", head).strip(" ：:.")
        hit = _CN_TITLE_MAP.get(title)
        if hit is not None:
            section, priority = hit
            return section, priority, title, True, _is_hard(head), len(raw)
    if len(raw) <= 80:
        title = _CN_ENUM.sub("", raw).strip(" ：:.")
        hit = _CN_TITLE_MAP.get(title)
        if hit is not None:
            section, priority = hit
            return section, priority, title, False, _is_hard(raw), len(raw)
    return _cn_prefix(raw)


def _cn_prefix(head: str) -> tuple[str, int, str, bool, bool, int] | None:
    """标题和正文挤在同一行时，从标题之后开始算正文。短标题必须有边界，避免「社会责任」切进「社会责任感」。"""
    enum = _CN_ENUM.match(head)
    base = enum.end() if enum else 0
    tail = head[base:]
    for title in sorted(_CN_TITLE_MAP, key=len, reverse=True):
        if not tail.startswith(title):
            continue
        after = base + len(title)
        boundary = after >= len(head) or head[after] in " \t：:。，,；;、"
        if not boundary and len(title) < 6:
            continue
        while after < len(head) and head[after] in " \t：:":
            after += 1
        section, priority = _CN_TITLE_MAP[title]
        return section, priority, title, False, _is_hard(head[:after]), after
    return None


def _anchors_us(text: str, form: str | None) -> list[Anchor]:
    item_map = _us_map(form)
    anchors: list[Anchor] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        parsed = _parse_us_line(line, item_map)
        if parsed is not None:
            section, num, toc, consumed = parsed
            anchors.append(
                Anchor(
                    section=section,
                    priority=0,
                    title=num,
                    start=offset,
                    content_start=_content_start(line, offset, consumed),
                    header=line.strip()[:120],
                    toc=toc,
                    hard=True,
                )
            )
        offset += len(line)
    return anchors


def _us_map(form: str | None) -> dict[str, str]:
    key = (form or "10-K").upper().replace("_", "-")
    if key in {"10Q", "10-Q"}:
        return dict(US_10Q_ITEMS)
    return dict(US_10K_ITEMS)


def _parse_us_line(line: str, item_map: dict[str, str]) -> tuple[str, str, bool, int] | None:
    raw = line.strip()
    if not raw:
        return None
    matched = _US_ITEM.match(raw)
    if not matched:
        return None
    num = matched.group("num").upper()
    if num not in item_map:
        return None
    rest = matched.group("rest")
    toc = bool(re.search(r"[\.·…]{3,}", rest) or (re.search(r"\s\d{1,4}\s*$", rest) and len(raw) < 140))
    if toc:
        return item_map[num], num, True, len(raw)
    words = list(re.finditer(r"[A-Za-z']+", rest))
    if len(words) <= 16:
        return item_map[num], num, False, len(raw)
    small = {"of", "and", "the", "a", "to", "for", "in", "on", "or"}
    cut = len(rest)
    for index, word in enumerate(words):
        letters = word.group(0).replace("'", "")
        if letters.lower() in small:
            continue
        heading = letters.isupper() or (letters[:1].isupper() and letters[1:].islower() and index < 14)
        if heading:
            continue
        cut = word.start()
        break
    consumed = matched.start("rest") + cut
    return item_map[num], num, False, consumed
