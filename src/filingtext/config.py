"""路径与数据源常量。不在此处存放任何密钥。"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
TEXT_DIR = DATA_DIR / "text"
OUTPUT_DIR = DATA_DIR / "output"
SAMPLE_DIR = DATA_DIR / "samples"
WORKSPACE_DIR = DATA_DIR / "workspace"
WORKSPACE_RAW = WORKSPACE_DIR / "raw"
WORKSPACE_TEXT = WORKSPACE_DIR / "text"
WORKSPACE_OUT = WORKSPACE_DIR / "output"
LEXICON_DIR = PACKAGE_DIR / "lexicons"

CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_SEARCH_URL = "http://www.cninfo.com.cn/new/information/topSearch/query"
CNINFO_STATIC = "https://static.cninfo.com.cn/"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}"

DEFAULT_SECTIONS = {
    "CN": ["mda", "risk"],
    "US": ["mda", "risk"],
}

PANEL_COLUMNS = [
    "doc_id",
    "market",
    "ticker",
    "stkcd",
    "cik",
    "firm_name",
    "fiscal_year",
    "report_type",
    "form",
    "section",
    "found",
    "is_duplicate",
    "source_path",
    "text_path",
    "text_sha1",
    "n_chars",
    "n_tokens",
    "n_sentences",
    "page_start",
    "page_end",
    "n_dropped_lines",
    "fog_index",
    "avg_sentence_len",
    "complex_word_ratio",
    "fog_method",
    "tone_pos",
    "tone_neg",
    "tone_unc",
    "tone_lit",
    "tone_net",
    "tone_method",
    "finbert_pos",
    "finbert_neg",
    "finbert_neu",
    "esg_count",
    "esg_per_k",
    "esg_tfidf",
    "digital_count",
    "digital_per_k",
    "digital_tfidf",
    "geopol_count",
    "geopol_per_k",
    "geopol_tfidf",
    "yoy_similarity",
    "disclosure_drift",
    "error",
]


def edgar_user_agent() -> str:
    ua = os.environ.get("EDGAR_USER_AGENT", "").strip()
    if "@" not in ua:
        raise RuntimeError(
            "访问 SEC EDGAR 需要环境变量 EDGAR_USER_AGENT，"
            "格式示例：YourName your.email@university.edu"
        )
    return ua
