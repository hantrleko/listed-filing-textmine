"""把多次解析结果按原文指纹合并进一个 DuckDB，版本变了才覆盖同一章节。"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


def sync_filings(frame: pd.DataFrame, store_path: str | Path) -> Path:
    path = Path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    incoming = frame.copy()
    con = duckdb.connect(str(path))
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if "filings" in tables:
            existing = con.execute("SELECT * FROM filings").df()
            merged = pd.concat([existing, incoming], ignore_index=True)
        else:
            merged = incoming
        keys = [column for column in ("source_sha1", "section", "app_version", "data_version") if column in merged.columns]
        if keys:
            merged = merged.drop_duplicates(keys, keep="last")
        con.register("merged_filings", merged)
        con.execute("CREATE OR REPLACE TABLE filings AS SELECT * FROM merged_filings")
    finally:
        con.close()
    return path
