"""词典审计的抽样和计分。标注列留空，精确率只在有人工标签时计算。"""

from __future__ import annotations


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
    return {"n_labeled": len(labeled), "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall}
