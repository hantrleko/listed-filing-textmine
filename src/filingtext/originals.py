"""按 SHA1 保存已抓到的原文。同一地址再次出现时直接拷贝，不再请求网站。"""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path

from filingtext.config import DATA_DIR

ORIGINAL_DIR = DATA_DIR / "cache" / "originals"
_LOCK = threading.Lock()


def remember_original(path: str | Path, url: str = "") -> str:
    path = Path(path)
    blob = path.read_bytes()
    digest = hashlib.sha1(blob).hexdigest()
    suffix = path.suffix.lower() or ".bin"
    ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
    dest = ORIGINAL_DIR / f"{digest}{suffix}"
    if not dest.exists():
        dest.write_bytes(blob)
    if url:
        _remember_url(url, digest, suffix)
    return digest


def restore_original(url: str, dest: str | Path) -> bool:
    item = _lookup(url)
    if not item:
        return False
    src = ORIGINAL_DIR / f"{item['sha1']}{item['suffix']}"
    if not src.is_file():
        return False
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.resolve() != src.resolve():
        shutil.copyfile(src, dest)
    return True


def _index_path() -> Path:
    return ORIGINAL_DIR / "index.json"


def _read_index() -> dict:
    path = _index_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _lookup(url: str) -> dict | None:
    with _LOCK:
        item = _read_index().get(url)
    if not isinstance(item, dict) or "sha1" not in item or "suffix" not in item:
        return None
    return item


def _remember_url(url: str, digest: str, suffix: str) -> None:
    with _LOCK:
        data = _read_index()
        data[url] = {"sha1": digest, "suffix": suffix}
        ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
        _index_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
