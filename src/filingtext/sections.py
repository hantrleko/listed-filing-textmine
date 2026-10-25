"""年报 / 10-K / 10-Q 章节切分。

硬边界是「第X节」和 Item 标题。目录行（点线或行末页码）不作为正文起点。
软标题（如「(四)可能面对的风险」）在下一个同级或更高级标题处结束，不把「(五)其他」收进去。
同一章节多次出现时，保留优先级更高、正文跨度更长的那一次。
章节正文会补上标题之前最近的 [[PAGE:n]]，避免小节从页中切开后丢失页码。
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
    ("risk", 3, "面临的主要风险"),
    ("risk", 3, "主要风险及应对"),
    ("risk", 4, "风险管理"),
    ("risk", 4, "风险因素"),
    ("risk", 2, "公司面临的风险"),
    ("risk", 2, "未来潜在的风险和挑战"),
    ("risk", 1, "可能面对的风险及应对措施"),
    ("risk", 1, "公司可能面对的风险及应对措施"),
    ("risk", 1, "公司可能面对的风险"),
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
_CN_TOC_LEADING = re.compile(r"^(?P<page>\d{1,4})\s+(?P<head>.+)$")
_RISK_POINTER = re.compile(r"敬请投资者|详见本报告|请参阅|详见第[一二三四五六七八九十\d]+节")
_CN_ENUM = re.compile(
    r"^(?:第[一二三四五六七八九十百零〇0-9]{1,3}[章节]|[（(][一二三四五六七八九十]+[)）][、.．]?|[一二三四五六七八九十]+、|\d{1,2}(?:\.\d+)+\s*|\d{1,2}[、.．]|\d{1,2}\s+)\s*"
)
_CN_HARD = re.compile(r"第[一二三四五六七八九十百零〇0-9]{1,3}[章节]")
_CN_NUMBERED = re.compile(r"^\d{1,2}\s+")


def _is_hard(head: str) -> bool:
    return bool(_CN_HARD.search(head) or _CN_NUMBERED.match(head.strip()))


def _outline_rank(raw: str) -> int | None:
    """标题层级。数字越小越高。目录行和数字堆不是标题。"""
    s = raw.replace("\u3000", " ").strip()
    if not s or s.startswith("[[PAGE:") or s.startswith("[[TABLE]]"):
        return None
    toc = _CN_TOC.match(s)
    if toc and (toc.group("page") or toc.group("page2")):
        return None
    if _CN_HARD.match(s):
        return 0
    if re.match(r"^[一二三四五六七八九十]+、", s):
        return 1 if _titleish(s) else None
    if re.match(r"^[（(][一二三四五六七八九十]+[)）]", s):
        return 2 if _titleish(s) else None
    decimal = re.match(r"^(\d{1,2}(?:\.\d+)+)\s*\S", s)
    if decimal:
        return 3 + decimal.group(1).count(".") if _titleish(s) else None
    if re.match(r"^\d{1,2}[、.．]\s*\S", s) or re.match(r"^\d{1,2}\s+\S", s):
        return 3 if _titleish(s) else None
    return None


def _titleish(line: str) -> bool:
    tail = _CN_ENUM.sub("", line).strip(" ：:.")
    if not tail:
        return True
    cjk = len(re.findall(r"[\u4e00-\u9fff]", tail))
    digits = sum(ch.isdigit() for ch in tail)
    if cjk < 2 and digits > 0:
        return False
    if digits > cjk and cjk < 4:
        return False
    return True


def _anchor_rank(line: str, hard: bool) -> int:
    rank = _outline_rank(line.strip())
    if rank is not None:
        return rank
    return 0 if hard else 9


def _outline_points(text: str) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        rank = _outline_rank(line)
        if rank is not None:
            points.append((offset, rank))
        offset += len(line)
    return points


def _section_end(anchor: Anchor, text_len: int, boundaries: list[int], outline: list[tuple[int, int]]) -> int:
    hard_end = next((pos for pos in boundaries if pos > anchor.start), text_len)
    if anchor.hard:
        return hard_end
    sibling = next((pos for pos, rank in outline if pos > anchor.start and rank <= anchor.rank), None)
    if sibling is None:
        return hard_end
    return min(sibling, hard_end)


def _page_before(text: str, pos: int) -> int | None:
    last = None
    for matched in re.finditer(r"\[\[PAGE:(\d+)\]\]", text):
        if matched.start() <= pos:
            last = int(matched.group(1))
        else:
            break
    return last


def leaks_sibling_heading(body: str, rank: int) -> bool:
    """正文里如果还留着同级或更高级标题，边界就不可信。"""
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("[[PAGE:") or stripped.startswith("[[TABLE]]"):
            continue
        found = _outline_rank(stripped)
        if found is not None and found <= rank:
            return True
    return False

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
    rank: int = 9
    toc_page: int | None = None
    match_method: str = "body"

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
    rank: int = 9
    match_method: str = "body"

    def as_dict(self) -> dict:
        data = asdict(self)
        data["n_chars"] = len(self.text)
        return data


def split_sections(text: str, market: str, form: str | None = None) -> dict[str, Section]:
    market = market.upper()
    anchors = find_anchors(text, market, form=form)
    chosen, boundaries = _choose(anchors)
    chosen.sort(key=lambda a: a.start)
    outline = _outline_points(text)
    out: dict[str, Section] = {}
    for anchor in chosen:
        end = _section_end(anchor, len(text), boundaries, outline)
        if anchor.toc and anchor.toc_page:
            body, content_start = _body_from_toc_page(text, anchor.toc_page, end)
        else:
            content_start = anchor.content_start
            body = text[content_start:end].strip()
        page = anchor.toc_page or _page_before(text, anchor.start)
        if page and not body.startswith("[[PAGE:"):
            body = f"[[PAGE:{page}]]\n{body}" if body else f"[[PAGE:{page}]]"
        out[anchor.section] = Section(
            key=anchor.section,
            title=anchor.title,
            header=anchor.header,
            text=body,
            start=content_start,
            end=end,
            rank=anchor.rank,
            match_method=anchor.match_method,
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


def _body_from_toc_page(text: str, page: int, end: int) -> tuple[str, int]:
    marker = f"[[PAGE:{page}]]"
    pos = text.find(marker)
    if pos < 0:
        return text[:0].strip(), 0
    slice_end = min(end, len(text))
    return text[pos:slice_end].strip(), pos


def _anchor_span(anchor: Anchor, points: list[int]) -> int:
    end = next((pos for pos in points if pos > anchor.start), 10**12)
    return end - anchor.start


def _best_anchor(group: list[Anchor], points: list[int], section: str = "") -> Anchor:
    filtered = [anchor for anchor in group if not _is_weak_risk_anchor(anchor, section)]
    pool = filtered or group
    if section == "mda":
        deep = [a for a in pool if a.rank >= 3 and not a.hard and not a.toc]
        shallow = [a for a in pool if a not in deep]
        if shallow:
            pool = shallow

    def key(anchor: Anchor) -> tuple:
        return (
            anchor.priority,
            anchor.rank,
            0 if anchor.hard else 1,
            0 if not anchor.toc else 2,
            -_anchor_span(anchor, points),
        )

    return sorted(pool, key=key)[0]


def _is_weak_risk_anchor(anchor: Anchor, section: str) -> bool:
    if section != "risk":
        return False
    if anchor.priority <= 2 and not anchor.toc:
        return False
    if anchor.start > 12000:
        return False
    if anchor.priority >= 4 and anchor.start < 10000:
        return True
    return False


def _section_pool(body: list[Anchor], toc: list[Anchor], section: str) -> list[Anchor]:
    body_hits = [a for a in body if a.section == section]
    if body_hits:
        return body_hits
    toc_hits = [a for a in toc if a.section == section]
    for anchor in toc_hits:
        anchor.match_method = "toc"
    return toc_hits


def _choose(anchors: list[Anchor]) -> tuple[list[Anchor], list[int]]:
    body = [a for a in anchors if not a.toc]
    toc = [a for a in anchors if a.toc]
    for anchor in body:
        anchor.match_method = "body"
    hard = [a for a in body if a.hard]
    selection_points = sorted(a.start for a in (hard or body or toc))
    sections = sorted({a.section for a in anchors})
    grouped = {section: _section_pool(body, toc, section) for section in sections}
    chosen = [_best_anchor(group, selection_points, section=section) for section, group in grouped.items() if section != "risk"]
    slice_points = sorted(a.start for a in hard) if hard else sorted(a.start for a in chosen)
    mda = next((anchor for anchor in chosen if anchor.section == "mda"), None)
    mda_end = next((pos for pos in slice_points if mda and pos > mda.start), 10**12)
    if "risk" in grouped:
        group = grouped["risk"]
        strong = [a for a in group if a.priority <= 2 and not _risk_pointer_anchor(a)]
        inside = [anchor for anchor in (strong or group) if mda and mda.content_start <= anchor.start < mda_end]
        dedicated = [anchor for anchor in inside if anchor.priority <= 2]
        outside_dedicated = [anchor for anchor in (strong or group) if anchor.priority <= 2 and anchor not in inside]
        picked = _best_anchor(dedicated or inside or outside_dedicated or strong or group, selection_points, section="risk")
        chosen.append(picked)
        embedded = bool(mda and mda.content_start <= picked.start < mda_end and not picked.hard)
        if not embedded and not hard:
            slice_points = sorted([*slice_points, picked.start])
    return chosen, slice_points


def _risk_pointer_anchor(anchor: Anchor) -> bool:
    if anchor.priority <= 1:
        return False
    header = anchor.header or ""
    return bool(_RISK_POINTER.search(header)) and len(header) < 120


def _anchors_cn(text: str) -> list[Anchor]:
    anchors: list[Anchor] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        parsed = _parse_cn_line(line)
        if parsed is not None:
            section, priority, title, toc, hard, consumed, toc_page = parsed
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
                    rank=_anchor_rank(line, hard),
                    toc_page=toc_page,
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


def _parse_cn_line(line: str) -> tuple[str, int, str, bool, bool, int, int | None] | None:
    raw = line.replace("\u3000", " ").strip()
    if not raw:
        return None
    leading = _CN_TOC_LEADING.match(raw)
    if leading:
        head = leading.group("head").strip()
        looks_like_toc = ".." in raw or re.search(r"[\.·…]{2,}", raw) or _CN_HARD.search(head) or re.search(r"[章节]", head)
        if looks_like_toc:
            title = _CN_ENUM.sub("", head).strip(" ：:.")
            hit = _CN_TITLE_MAP.get(title)
            if hit is not None:
                section, priority = hit
                return section, priority, title, True, _is_hard(head), len(raw), int(leading.group("page"))
    matched = _CN_TOC.match(raw)
    if matched and (matched.group("page") or matched.group("page2")):
        head = matched.group("head").strip()
        title = _CN_ENUM.sub("", head).strip(" ：:.")
        hit = _CN_TITLE_MAP.get(title)
        if hit is not None:
            section, priority = hit
            page_raw = matched.group("page") or matched.group("page2")
            page = int(page_raw) if page_raw else None
            return section, priority, title, True, _is_hard(head), len(raw), page
    if len(raw) <= 80:
        title = _CN_ENUM.sub("", raw).strip(" ：:.")
        hit = _CN_TITLE_MAP.get(title)
        if hit is not None:
            section, priority = hit
            return section, priority, title, False, _is_hard(raw), len(raw), None
    parsed = _cn_prefix(raw)
    if parsed is None:
        return None
    section, priority, title, toc, hard, consumed = parsed
    return section, priority, title, toc, hard, consumed, None


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
        if section == "mda" and len(title) < 8 and not _is_hard(head[:after]):
            continue
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
                    rank=0,
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
