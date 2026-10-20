"""可读性、词典强度、语气和跨年相似度。"""

from __future__ import annotations

import math
import re
from collections import Counter

from filingtext.lexicon import register_jieba, tone_lexicons, topic_lexicons

ZH_STOP = {
    "的", "了", "和", "与", "及", "或", "在", "对", "为", "是", "公司", "本公司", "我们",
    "其", "并", "等", "以及", "通过", "进行", "实现", "相关", "主要", "报告期内", "本集团",
    "一个", "没有", "已", "将", "被", "把", "从", "到", "中", "上", "下", "及", "等",
    "本", "该", "这", "那", "及", "或", "而", "但", "并", "以", "对", "于", "也", "都",
    "年", "月", "日", "元", "万元", "亿元",
}
EN_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "as", "by",
    "at", "from", "that", "this", "these", "those", "is", "are", "was", "were", "be",
    "been", "being", "it", "its", "we", "our", "company", "year", "fiscal", "ended",
    "not", "no", "than", "which", "into", "over", "under", "such", "other", "may",
    "would", "could", "should", "has", "have", "had", "their", "they", "our",
}

_SENT_ZH = re.compile(r"[。！？!?；;]")
_WORD_EN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def language_for_market(market: str) -> str:
    return "zh" if market.upper() == "CN" else "en"


def tokenize(text: str, lang: str) -> list[str]:
    register_jieba()
    if lang == "zh":
        import jieba

        out = []
        for token in jieba.lcut(text, cut_all=False):
            token = token.strip()
            if re.search(r"[\u4e00-\u9fffA-Za-z]", token):
                out.append(token.lower() if token.isascii() else token)
        return out
    return _WORD_EN.findall(text.lower())


def find_spans(text: str, terms: list[str], lang: str) -> list[tuple[int, int, str]]:
    terms = [t for t in terms if t]
    if not text or not terms:
        return []
    if lang == "en":
        inner = "|".join(re.escape(t) for t in sorted(set(terms), key=len, reverse=True))
        pattern = re.compile(rf"(?<![A-Za-z])(?:{inner})(?![A-Za-z])", re.I)
        return [(m.start(), m.end(), m.group(0).lower()) for m in pattern.finditer(text)]
    inner = "|".join(re.escape(t) for t in sorted(set(terms), key=len, reverse=True))
    pattern = re.compile(inner)
    return [(m.start(), m.end(), m.group(0)) for m in pattern.finditer(text)]


def count_terms(text: str, terms: list[str], lang: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for _, _, term in find_spans(text, terms, lang):
        counts[term] += 1
    return dict(counts)


def highlight_spans(text: str, groups: list[tuple[str, list[str]]], lang: str) -> list[tuple[int, int, str]]:
    """跨词表去重叠，长词优先。返回 (start, end, label)。"""
    candidates: list[tuple[int, int, str]] = []
    for label, terms in groups:
        for start, end, _term in find_spans(text, terms, lang):
            candidates.append((start, end, label))
    candidates.sort(key=lambda item: (-(item[1] - item[0]), item[0]))
    occupied = [False] * len(text)
    chosen: list[tuple[int, int, str]] = []
    for start, end, label in candidates:
        if any(occupied[start:end]):
            continue
        for pos in range(start, end):
            occupied[pos] = True
        chosen.append((start, end, label))
    chosen.sort(key=lambda item: item[0])
    return chosen


def _syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1:
        n -= 1
    return max(1, n)


def readability(text: str, tokens: list[str], lang: str) -> dict:
    if lang == "en":
        words = _WORD_EN.findall(text)
        sentences = [s for s in re.split(r"[.!?]+", text) if re.search(r"[A-Za-z]", s)]
        n_sent = max(1, len(sentences))
        n_word = max(1, len(words))
        complex_n = sum(1 for w in words if _syllables(w) >= 3)
        fog = 0.4 * ((len(words) / n_sent) + 100.0 * complex_n / n_word)
        return {
            "fog_index": fog,
            "avg_sentence_len": len(words) / n_sent,
            "complex_word_ratio": complex_n / n_word,
            "fog_method": "gunning_fog",
            "n_sentences": len(sentences),
        }
    sentences = [s for s in _SENT_ZH.split(text) if s.strip()]
    n_sent = max(1, len(sentences))
    words = [t for t in tokens if re.search(r"[\u4e00-\u9fff]", t)]
    n_word = max(1, len(words))
    complex_n = sum(1 for w in words if len(w) >= 4)
    fog = 0.4 * ((len(words) / n_sent) + 100.0 * complex_n / n_word)
    chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    return {
        "fog_index": fog,
        "avg_sentence_len": chars / n_sent,
        "complex_word_ratio": complex_n / n_word,
        "fog_method": "zh_fog_analog",
        "n_sentences": len(sentences),
    }


_ZH_NEGATION = re.compile(r"(没有|并非|难以|尚未|未|不|没)$")
_EN_NEGATION = re.compile(r"\b(?:no|not|never|without|neither|nor)\b\W*$", re.I)


def _negated(text: str, start: int, lang: str) -> bool:
    if lang == "zh":
        return bool(_ZH_NEGATION.search(text[max(0, start - 4) : start]))
    return bool(_EN_NEGATION.search(text[max(0, start - 24) : start]))


def _tone_counts(text: str, tones: dict[str, list[str]], lang: str) -> dict[str, int]:
    """近距离否定会翻转积极/消极。`没有改善` 不再计为积极。"""
    pos = neg = 0
    for start, _end, _term in find_spans(text, tones.get("pos", []), lang):
        if _negated(text, start, lang):
            neg += 1
        else:
            pos += 1
    for start, _end, _term in find_spans(text, tones.get("neg", []), lang):
        if _negated(text, start, lang):
            pos += 1
        else:
            neg += 1
    return {
        "pos": pos,
        "neg": neg,
        "unc": sum(count_terms(text, tones.get("unc", []), lang).values()),
        "lit": sum(count_terms(text, tones.get("lit", []), lang).values()),
    }


def _per_k(count: int, n_tokens: int) -> float | None:
    if n_tokens <= 0:
        return None
    return 1000.0 * count / n_tokens


def _share(count: int, n_tokens: int) -> float | None:
    if n_tokens <= 0:
        return None
    return count / n_tokens


def score_document(
    text: str,
    market: str,
    tone_override: dict[str, list[str]] | None = None,
) -> dict:
    lang = language_for_market(market)
    tokens = tokenize(text, lang)
    n_tokens = len(tokens)
    topics = topic_lexicons()[lang]
    tones = tone_override if tone_override is not None else tone_lexicons()[lang]
    term_hits: dict[str, dict[str, int]] = {}
    metrics: dict = {
        "n_chars": len(text),
        "n_tokens": n_tokens,
        "token_counts": dict(Counter(tokens)),
    }
    metrics.update(readability(text, tokens, lang))
    for name in ("esg", "digital", "geopol"):
        hits = count_terms(text, topics[name], lang)
        term_hits[name] = hits
        total = sum(hits.values())
        metrics[f"{name}_count"] = total
        metrics[f"{name}_per_k"] = _per_k(total, n_tokens)
        metrics[f"{name}_tfidf"] = None
    tone_counts = _tone_counts(text, tones, lang)
    metrics["tone_pos"] = _share(tone_counts["pos"], n_tokens)
    metrics["tone_neg"] = _share(tone_counts["neg"], n_tokens)
    metrics["tone_unc"] = _share(tone_counts["unc"], n_tokens)
    metrics["tone_lit"] = _share(tone_counts["lit"], n_tokens)
    if n_tokens:
        metrics["tone_net"] = (tone_counts["pos"] - tone_counts["neg"]) / n_tokens
    else:
        metrics["tone_net"] = None
    base_method = "seed_dictionary" if tone_override is None else "loughran_mcdonald"
    metrics["tone_method"] = base_method + "+negation"
    metrics["finbert_pos"] = None
    metrics["finbert_neg"] = None
    metrics["finbert_neu"] = None
    metrics["term_hits"] = term_hits
    return metrics


def apply_corpus(records: list[dict]) -> list[dict]:
    """在全样本上补 TF-IDF 和上一年度相似度。会删掉 token_counts / term_hits。"""
    scored = [r for r in records if r.get("found") and r.get("token_counts")]
    identifiable = [r for r in scored if r.get("ticker") and r.get("fiscal_year")]
    _mark_duplicates(identifiable)
    unique = [r for r in identifiable if not r.get("is_duplicate")]
    population = unique or scored
    n_docs = len(population)
    df: Counter[str] = Counter()
    for row in population:
        df.update(row["token_counts"].keys())
    idf = {term: math.log((n_docs + 1) / (freq + 1)) + 1 for term, freq in df.items()} if n_docs else {}

    for lex in ("esg", "digital", "geopol"):
        lex_df: Counter[str] = Counter()
        for row in population:
            for term, count in row.get("term_hits", {}).get(lex, {}).items():
                if count:
                    lex_df[term] += 1
        for row in scored:
            if row.get("is_duplicate"):
                row[f"{lex}_tfidf"] = None
                continue
            n_tokens = row.get("n_tokens") or 0
            if n_tokens <= 0 or n_docs == 0:
                row[f"{lex}_tfidf"] = None
                continue
            score = 0.0
            for term, count in row.get("term_hits", {}).get(lex, {}).items():
                tf = count / n_tokens
                score += tf * (math.log((n_docs + 1) / (lex_df[term] + 1)) + 1)
            row[f"{lex}_tfidf"] = score

    index = {
        (r["market"], r["ticker"], r["section"], int(r["fiscal_year"])): r
        for r in unique
    }
    for row in unique:
        prev = index.get((row["market"], row["ticker"], row["section"], int(row["fiscal_year"]) - 1))
        if prev is None:
            row["yoy_similarity"] = None
            row["disclosure_drift"] = None
            continue
        sim = cosine_tfidf(row["token_counts"], prev["token_counts"], idf, language_for_market(row["market"]))
        row["yoy_similarity"] = sim
        row["disclosure_drift"] = None if sim is None else 1.0 - sim

    for row in records:
        row.pop("token_counts", None)
        row.pop("term_hits", None)
        row.setdefault("yoy_similarity", None)
        row.setdefault("disclosure_drift", None)
        row.setdefault("is_duplicate", 0)
        for lex in ("esg", "digital", "geopol"):
            row.setdefault(f"{lex}_tfidf", None)
    return records


def _mark_duplicates(rows: list[dict]) -> None:
    best: dict[tuple, dict] = {}
    for row in rows:
        key = (row.get("market"), row.get("ticker"), row.get("section"), row.get("fiscal_year"))
        row["is_duplicate"] = 0
        current = best.get(key)
        if current is None or (row.get("n_chars") or 0) > (current.get("n_chars") or 0):
            if current is not None:
                current["is_duplicate"] = 1
            best[key] = row
        else:
            row["is_duplicate"] = 1


def cosine_tfidf(c1: dict, c2: dict, idf: dict[str, float], lang: str) -> float | None:
    stop = ZH_STOP if lang == "zh" else EN_STOP
    keys = set(c1) | set(c2)
    dot = n1 = n2 = 0.0
    for term in keys:
        if term in stop or len(term) <= 1:
            continue
        weight = idf.get(term, 0.0)
        a = c1.get(term, 0) * weight
        b = c2.get(term, 0) * weight
        dot += a * b
        n1 += a * a
        n2 += b * b
    if n1 <= 0 or n2 <= 0:
        return None
    return dot / math.sqrt(n1 * n2)


def _sentences(text: str, lang: str) -> list[str]:
    if lang == "zh":
        parts = re.split(r"[。！？\n]+", text)
    else:
        parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if len(part.strip()) >= 12]


def disclosure_diff(previous: str, current: str, market: str, limit: int = 6) -> dict:
    """比较两年同一章节。只有一年时调用方应直接说明没有基期，不要把单年分数写成趋势。"""
    import difflib

    lang = language_for_market(market)
    old = _sentences(previous or "", lang)
    new = _sentences(current or "", lang)
    added: list[str] = []
    removed: list[str] = []
    replaced: list[dict] = []
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added.extend(new[j1:j2])
        elif tag == "delete":
            removed.extend(old[i1:i2])
        elif tag == "replace":
            for left, right in zip(old[i1:i2], new[j1:j2]):
                replaced.append({"before": left, "after": right})
            if i2 - i1 > j2 - j1:
                removed.extend(old[i1 + (j2 - j1) : i2])
            elif j2 - j1 > i2 - i1:
                added.extend(new[j1 + (i2 - i1) : j2])
    topics = topic_lexicons()[lang]
    deltas = []
    for name, terms in topics.items():
        before = count_terms(previous or "", terms, lang)
        after = count_terms(current or "", terms, lang)
        for term in set(before) | set(after):
            change = after.get(term, 0) - before.get(term, 0)
            if change:
                deltas.append({"lexicon": name, "term": term, "change": change})
    deltas.sort(key=lambda item: abs(item["change"]), reverse=True)
    return {
        "added": added[:limit],
        "removed": removed[:limit],
        "replaced": replaced[:limit],
        "topic_changes": deltas[:limit],
    }


def finbert_tone(text: str, model_name: str = "yiyanghkust/finbert-tone", max_chars: int = 8000) -> dict | None:
    """分块调用 FinBERT-tone，返回正/负/中性概率均值。模型不可用时返回 None。"""
    try:
        from transformers import pipeline
    except ImportError:
        return None
    snippet = text[:max_chars]
    if not snippet.strip():
        return None
    chunks = [snippet[i : i + 800] for i in range(0, len(snippet), 800)] or [snippet]
    clf = pipeline("sentiment-analysis", model=model_name, truncation=True)
    acc = {"Positive": 0.0, "Negative": 0.0, "Neutral": 0.0}
    used = 0
    for chunk in chunks:
        if not chunk.strip():
            continue
        pred = clf(chunk[:1200])[0]
        label = str(pred.get("label", ""))
        score = float(pred.get("score", 0.0))
        if label not in acc:
            continue
        acc[label] += score
        used += 1
    if used == 0:
        return None
    return {
        "finbert_pos": acc["Positive"] / used,
        "finbert_neg": acc["Negative"] / used,
        "finbert_neu": acc["Neutral"] / used,
    }
