"""PDF 与 HTML/TXT 披露文件转成纯文本。"""

from __future__ import annotations

import re
from pathlib import Path

from filingtext.clean import collapse_cjk_spacing, drop_repeated_lines, drop_repeated_pages, normalize


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
    import pdfplumber

    pages: list[list[str]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
            height = float(page.height or 0)
            if words:
                lines = _cluster_lines(words)
                body = []
                for line in lines:
                    if height and (line["top"] < height * 0.06 or line["bottom"] > height * 0.94):
                        continue
                    body.append(line["text"])
            else:
                body = (page.extract_text() or "").splitlines()
            pages.append(body)
    if len(pages) >= 3:
        return normalize(drop_repeated_pages(pages))
    joined = "\n".join(line for page in pages for line in page if line.strip())
    return drop_repeated_lines(normalize(joined))


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
