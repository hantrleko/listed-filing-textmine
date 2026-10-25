"""PDF 与 HTML/TXT 披露文件转成纯文本。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from filingtext.clean import collapse_cjk_spacing, drop_repeated_lines, drop_repeated_pages, normalize
from filingtext.config import DATA_DIR

EXTRACT_CACHE_DIR = DATA_DIR / "cache" / "extract"


def read_filing(path: str | Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if suffix in {".htm", ".html"} or _looks_html(raw) or "<DOCUMENT>" in raw.upper():
        return html_to_text(raw)
    return drop_repeated_lines(normalize(raw))


def extract_pdf(path: str | Path) -> str:
    path = Path(path)
    digest = hashlib.sha1(path.read_bytes()).hexdigest()
    cache = EXTRACT_CACHE_DIR / f"{digest}.txt"
    if cache.is_file():
        return cache.read_text(encoding="utf-8")
    text = _extract_pdf_impl(path)
    EXTRACT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


def _extract_pdf_impl(path: Path) -> str:
    import pdfplumber

    pages: list[list[str]] = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
            height = float(page.height or 0)
            if words:
                lines = _cluster_lines(words)
                boxes = _table_bboxes(page)
                body = []
                for line in lines:
                    if height and (line["top"] < height * 0.06 or line["bottom"] > height * 0.94):
                        continue
                    text = line["text"]
                    if _line_in_table(line["top"], line["bottom"], text, boxes):
                        text = "[[TABLE]]" + text
                    body.append(text)
            else:
                body = (page.extract_text() or "").splitlines()
            pages.append([f"[[PAGE:{index}]]", *body])
    if len(pages) >= 3:
        return normalize(drop_repeated_pages(pages))
    joined = "\n".join(line for page in pages for line in page if line.strip())
    return drop_repeated_lines(normalize(joined))


def _table_bboxes(page) -> list[tuple[float, float, float, float]]:
    try:
        found = page.find_tables() or []
    except Exception:
        return []
    boxes = []
    for table in found:
        box = getattr(table, "bbox", None)
        if box and len(box) == 4:
            boxes.append(tuple(float(value) for value in box))
    return boxes


def _line_in_table(top: float, bottom: float, text: str, boxes: list[tuple[float, float, float, float]], pad_top: float = 16.0) -> bool:
    """行心落在表格框内就标成表格。框上方紧挨的表头也标上，完整叙述句不靠这个边缘规则删除。"""
    if not boxes:
        return False
    mid = (top + bottom) / 2.0
    prose = _cjk_count(text) >= 12 and bool(re.search(r"[。！？]", text))
    for _x0, y0, _x1, y1 in boxes:
        if y0 <= mid <= y1:
            return True
        if y0 - pad_top <= mid < y0 and not prose:
            return True
    return False


def _cjk_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _cluster_lines(words: list[dict], y_tol: float = 3.0) -> list[dict]:
    ordered = sorted(words, key=lambda w: (w["top"], w["x0"]))
    groups: list[list[dict]] = [[ordered[0]]]
    for word in ordered[1:]:
        if abs(word["top"] - groups[-1][-1]["top"]) <= y_tol:
            groups[-1].append(word)
        else:
            groups.append([word])
    lines = []
    for group in groups:
        group.sort(key=lambda w: w["x0"])
        lines.append(
            {
                "text": _join_words(group),
                "top": min(w["top"] for w in group),
                "bottom": max(w["bottom"] for w in group),
            }
        )
    return lines


def _join_words(words: list[dict]) -> str:
    parts: list[str] = []
    for word in words:
        token = str(word["text"])
        if parts and not (_cjk_char(parts[-1][-1:]) and _cjk_char(token[:1])):
            parts.append(" ")
        parts.append(token)
    return collapse_cjk_spacing("".join(parts))


def _cjk_char(ch: str) -> bool:
    return bool(ch) and "\u4e00" <= ch <= "\u9fff"


def html_to_text(raw: str) -> str:
    body = pick_sgml_body(raw)
    if _looks_html(body):
        body = _html_text(body)
    return drop_repeated_lines(normalize(body))


def pick_sgml_body(raw: str) -> str:
    docs = []
    for matched in re.finditer(r"<DOCUMENT>(.*?)</DOCUMENT>", raw, flags=re.I | re.S):
        block = matched.group(1)
        type_match = re.search(r"<TYPE>\s*([^\s<]+)", block, flags=re.I)
        text_match = re.search(r"<TEXT>(.*)</TEXT>", block, flags=re.I | re.S)
        if type_match and text_match:
            docs.append((type_match.group(1).upper(), text_match.group(1)))
    if not docs:
        return raw
    for want in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
        for kind, body in docs:
            if kind == want:
                return body
    return docs[0][1]


def _looks_html(text: str) -> bool:
    return bool(re.search(r"<(html|body|div|p|table|br|span)\b", text[:5000], flags=re.I))


def _html_text(raw: str) -> str:
    from bs4 import BeautifulSoup

    try:
        soup = BeautifulSoup(raw, "lxml")
    except Exception:
        soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n")
