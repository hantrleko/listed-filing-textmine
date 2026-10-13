"""用户自己的披露面板。和样本案例分开，避免重新计算时改掉案例里的数字。"""

from __future__ import annotations

import os
import re
from pathlib import Path

from filingtext.config import WORKSPACE_OUT, WORKSPACE_RAW, WORKSPACE_TEXT
from filingtext.pipeline import run
from filingtext.sources import download_cninfo, download_edgar

MAX_FILINGS = 8


def parse_codes(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，;\s]+", raw) if item.strip()]


def build_from_codes(
    market: str,
    codes: str,
    start: int,
    end: int,
    edgar_contact: str = "",
    forms: list[str] | None = None,
    max_filings: int = MAX_FILINGS,
) -> dict:
    market = market.upper()
    chosen = parse_codes(codes)
    if not chosen:
        raise ValueError("请填写至少一个证券代码或 ticker。")
    start, end = int(start), int(end)
    if end < start:
        raise ValueError("结束年需要大于或等于起始年。")
    form_list = forms or (["10-K"] if market == "US" else ["annual"])
    estimate = len(chosen) * (end - start + 1) * max(1, len(form_list) if market == "US" else 1)
    if estimate > max_filings:
        raise ValueError(
            f"这次大约会下载 {estimate} 份文件，单次最多 {max_filings} 份。请减少代码或缩短年份。"
        )
    WORKSPACE_RAW.mkdir(parents=True, exist_ok=True)
    if market == "CN":
        saved = download_cninfo(chosen, start, end, WORKSPACE_RAW)
    else:
        contact = edgar_contact.strip()
        if "@" not in contact:
            raise RuntimeError("访问 SEC EDGAR 需要填写联系邮箱。邮箱只留在这次会话里，不会写入文件。")
        previous = os.environ.get("EDGAR_USER_AGENT")
        os.environ["EDGAR_USER_AGENT"] = f"filingtext-research {contact}"
        try:
            saved = download_edgar(chosen, [], start, end, WORKSPACE_RAW, forms=form_list)
        finally:
            if previous is None:
                os.environ.pop("EDGAR_USER_AGENT", None)
            else:
                os.environ["EDGAR_USER_AGENT"] = previous
    if not saved:
        raise RuntimeError("没有下载到符合条件的年报或 10-K/10-Q。")
    result = refresh_workspace()
    result["downloaded"] = saved
    return result


def save_upload(filename: str, data: bytes) -> Path:
    WORKSPACE_RAW.mkdir(parents=True, exist_ok=True)
    dest = WORKSPACE_RAW / Path(filename).name
    dest.write_bytes(data)
    return dest


def refresh_workspace() -> dict:
    if not WORKSPACE_RAW.exists() or not any(WORKSPACE_RAW.iterdir()):
        raise FileNotFoundError("我的面板里还没有文件。")
    return run(WORKSPACE_RAW, WORKSPACE_OUT, text_dir=WORKSPACE_TEXT)


def reset_workspace() -> None:
    import shutil

    root = WORKSPACE_RAW.parent
    if root.exists():
        shutil.rmtree(root)
