"""词典审计的抽样和计分。精确率只在有人工标签时计算。"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

TOPIC_LABELS = {"esg": "ESG / 绿色", "digital": "数智化", "geopol": "地缘政治"}

_NEAR_CUES = {
    "esg": re.compile(r"环境|社会|碳|排放|绿色|节能|气候|污染|生态|环保|能耗"),
    "digital": re.compile(r"数字|智能|自动|信息|网络|平台|算法|机器人|软件|线上|信息化"),
    "geopol": re.compile(r"国际|海外|出口|进口|关税|制裁|贸易|战争|冲突|地缘|管制|断供"),
}


def audit_scores(rows: list[dict]) -> dict:
    """label 取 relevant 或 irrelevant。hit 为 1 表示词典命中句，0 表示未命中句。"""
    labeled = [row for row in rows if str(row.get("label") or "").strip() in {"relevant", "irrelevant"}]
    if not labeled:
        return {"n_labeled": 0, "precision": None, "recall": None}
    tp = sum(1 for row in labeled if str(row.get("hit")) == "1" and row["label"] == "relevant")
    fp = sum(1 for row in labeled if str(row.get("hit")) == "1" and row["label"] == "irrelevant")
    fn = sum(1 for row in labeled if str(row.get("hit")) == "0" and row["label"] == "relevant")
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    tn = sum(1 for row in labeled if str(row.get("hit")) == "0" and row["label"] == "irrelevant")
    return {
        "n_labeled": len(labeled),
        "n_hit": tp + fp,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
    }


def split_audit_sentences(text: str) -> list[str]:
    """先把年报里被换行拆开的句子接回去，再按句号切开。"""
    buffer = ""
    pieces: list[str] = []
    for line in (text or "").replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            if buffer:
                pieces.append(buffer)
                buffer = ""
            continue
        buffer += line
        if re.search(r"[。！？；;]$", buffer):
            pieces.append(buffer)
            buffer = ""
    if buffer:
        pieces.append(buffer)
    sentences: list[str] = []
    for piece in pieces:
        for part in re.split(r"[。！？]+", piece):
            part = re.sub(r"\s+", "", part).strip("；;，,、")
            if len(part) >= 12:
                sentences.append(part)
    return sentences


def sentence_is_hit(sentence: str, lexicon: str) -> bool:
    from filingtext.features import _count_geopol, count_active_terms
    from filingtext.lexicon import topic_lexicons

    terms = topic_lexicons()["zh"].get(lexicon, [])
    if lexicon == "geopol":
        return sum(_count_geopol(sentence, terms, "zh").values()) > 0
    return sum(count_active_terms(sentence, terms, "zh").values()) > 0


def sample_topic_sentences(
    documents: list[dict],
    lexicon: str,
    *,
    n_hit: int = 100,
    n_near: int = 50,
    n_random: int = 50,
    seed: int = 20261110,
) -> list[dict]:
    """从已清洗的管理层讨论里抽句子。documents 每项含 ticker、fiscal_year、text。

    命中句用来看精确率。未命中句分成近邻句和随机句，用来看有没有被词典漏掉。
    """
    hits: list[dict] = []
    near: list[dict] = []
    rest: list[dict] = []
    cue = _NEAR_CUES[lexicon]
    seen: set[str] = set()
    for doc in documents:
        for sentence in split_audit_sentences(str(doc.get("text") or "")):
            if sentence in seen:
                continue
            seen.add(sentence)
            row = {
                "lexicon": lexicon,
                "ticker": str(doc.get("ticker") or ""),
                "fiscal_year": doc.get("fiscal_year") or "",
                "sentence": sentence,
                "hit": "1" if sentence_is_hit(sentence, lexicon) else "0",
                "label": "",
            }
            if row["hit"] == "1":
                hits.append(row)
            elif cue.search(sentence):
                near.append(row)
            else:
                rest.append(row)
    rng = random.Random(seed)
    rng.shuffle(hits)
    rng.shuffle(near)
    rng.shuffle(rest)
    chosen = hits[:n_hit] + near[:n_near] + rest[:n_random]
    for index, row in enumerate(chosen, start=1):
        row["sentence_id"] = f"{lexicon}-{index:03d}"
    return chosen


def summarize_labels(rows: list[dict]) -> dict:
    by_lex: dict[str, list[dict]] = {}
    for row in rows:
        by_lex.setdefault(str(row.get("lexicon") or ""), []).append(row)
    classes = {}
    for lexicon, group in by_lex.items():
        scored = audit_scores(group)
        scored["label"] = TOPIC_LABELS.get(lexicon, lexicon)
        classes[lexicon] = scored
    return {"classes": classes}


def load_audit_summary() -> dict | None:
    path = Path(__file__).with_name("lexicon_audit_summary.json")
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
