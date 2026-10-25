"""PIT 日期：公告日与因子工作台对齐的可用日。"""

from __future__ import annotations

from datetime import datetime, timedelta


def pit_dates(announce_date: str) -> tuple[str, str]:
    """返回 (announce_date, available_date)。available_date 为公告日次日，与东财 NOTICE_DATE 口径一致。"""
    raw = (announce_date or "").strip()
    if not raw:
        return "", ""
    try:
        day = datetime.strptime(raw[:10], "%Y-%m-%d")
    except ValueError:
        return raw[:10], raw[:10]
    return raw[:10], (day + timedelta(days=1)).strftime("%Y-%m-%d")
