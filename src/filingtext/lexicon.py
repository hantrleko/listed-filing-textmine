"""词表加载。官方 Loughran-McDonald 主词典可从外部 CSV/XLSX 覆盖英文语气词。"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

from filingtext.config import LEXICON_DIR

log = logging.getLogger(__name__)

DICTIONARY_VERSION = "topics-seed-2026-11+yao2021-formal"

TOPIC_NAMES = ("esg", "digital", "geopol")
TONE_NAMES = ("pos", "neg", "unc", "lit")

_JIEBA_READY = False


def _read_terms(path: Path) -> list[str]:
    if not path.exists():
        return []
    terms: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line)
    return terms


def load_term_file(path: Path, *, lower: bool) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for term in _read_terms(path):
        key = term.lower() if lower else term
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


@lru_cache(maxsize=1)
def topic_lexicons() -> dict[str, dict[str, list[str]]]:
    """返回 {zh|en: {esg|digital|geopol: [terms]}}。"""
    data: dict[str, dict[str, list[str]]] = {"zh": {}, "en": {}}
    for name in TOPIC_NAMES:
        data["zh"][name] = load_term_file(LEXICON_DIR / f"{name}_zh.txt", lower=False)
        data["en"][name] = load_term_file(LEXICON_DIR / f"{name}_en.txt", lower=True)
    return data


def formal_tone_available() -> bool:
    return (LEXICON_DIR / "yao2021_formal_pos.txt").exists() and (LEXICON_DIR / "yao2021_formal_neg.txt").exists()


@lru_cache(maxsize=1)
def tone_lexicons() -> dict[str, dict[str, list[str]]]:
    """中文积极/消极词用姚加权等（2021）正式用语词表。不确定和诉讼仍是种子词。

    正式词表只用于年报语调。社交媒体词表不读入。英文语气仍是种子词，可用 Loughran-McDonald 覆盖。
    """
    data: dict[str, dict[str, list[str]]] = {"zh": {}, "en": {}}
    for name in TONE_NAMES:
        data["zh"][name] = load_term_file(LEXICON_DIR / f"tone_{name}_zh.txt", lower=False)
        data["en"][name] = load_term_file(LEXICON_DIR / f"tone_{name}_en.txt", lower=True)
    if formal_tone_available():
        data["zh"]["pos"] = load_term_file(LEXICON_DIR / "yao2021_formal_pos.txt", lower=False)
        data["zh"]["neg"] = load_term_file(LEXICON_DIR / "yao2021_formal_neg.txt", lower=False)
        covered = set(data["zh"]["pos"]) | set(data["zh"]["neg"])
        data["zh"]["pos"] = [term for term in data["zh"]["pos"] if term not in set(data["zh"]["neg"])]
        for name in ("unc", "lit"):
            data["zh"][name] = [term for term in data["zh"][name] if term not in covered]
    return data


def load_loughran_mcdonald(path: str | Path) -> dict[str, list[str]]:
    """读取官方主词典 CSV 或 XLSX，列名需含 Word 以及情感类别列。

    类别列取 Positive / Negative / Uncertainty / Litigious。
    单元格为非零即计入。返回英文小写词表，供 tone_method=loughran_mcdonald。
    """
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        import pandas as pd

        frame = pd.read_excel(path)
    else:
        import pandas as pd

        frame = pd.read_csv(path)
    columns = {c.lower().strip(): c for c in frame.columns}
    word_col = columns.get("word")
    if word_col is None:
        raise ValueError(f"{path} 缺少 Word 列")
    mapping = {
        "pos": "positive",
        "neg": "negative",
        "unc": "uncertainty",
        "lit": "litigious",
    }
    out: dict[str, list[str]] = {k: [] for k in mapping}
    for key, col_name in mapping.items():
        src = columns.get(col_name)
        if src is None:
            continue
        for word, flag in zip(frame[word_col], frame[src]):
            if _flag_on(flag) and isinstance(word, str) and word.strip():
                out[key].append(word.strip().lower())
    return out


def _flag_on(value: object) -> bool:
    if value is None:
        return False
    try:
        return float(value) != 0.0
    except (TypeError, ValueError):
        return str(value).strip().lower() in {"true", "yes", "y"}


def register_jieba(extra: list[str] | None = None) -> None:
    """把中文领域词加入 jieba，避免被切碎。"""
    global _JIEBA_READY
    if _JIEBA_READY and not extra:
        return
    import jieba

    jieba.setLogLevel(logging.WARNING)
    terms = list(extra or [])
    zh = topic_lexicons()["zh"]
    tone = tone_lexicons()["zh"]
    # 正式用语词表有几千条，不塞进分词器，避免把「风险管理」切成「风险」。
    for group in list(zh.values()) + [tone.get("unc", []), tone.get("lit", [])]:
        terms.extend(group)
    for term in terms:
        if re.search(r"[\u4e00-\u9fff]", term) and len(term) >= 2:
            jieba.add_word(term, freq=2_000_000)
    _JIEBA_READY = True


def jieba_ready() -> bool:
    return _JIEBA_READY
