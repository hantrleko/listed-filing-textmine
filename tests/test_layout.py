import json
from pathlib import Path

import pytest

from filingtext.clean import clean_body_report, noise_reason
from filingtext.extract import _line_in_table
from filingtext.features import _page_of_snippet
from filingtext.parse_job import parse_text

FIXTURE = Path(__file__).parent / "fixtures" / "moutai_2023_page8_labels.json"
MOUTAI = Path(r"F:\listed-filing-textmine\data\validation\raw\600519_2023_annual.pdf")


def test_labeled_lines_report_false_drop_and_miss_rates():
    """人工核对过的茅台 2023 年第 8 页句子。验收看误删和漏删，不看有没有算出指标。"""
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    false_drops = []
    misses = []
    for row in rows:
        reason = noise_reason(row["line"])
        if row["label"] == "keep" and reason:
            false_drops.append((row["line"], reason))
        if row["label"] == "drop" and reason is None:
            misses.append(row["line"])
    false_rate = len(false_drops) / sum(row["label"] == "keep" for row in rows)
    miss_rate = len(misses) / sum(row["label"] == "drop" for row in rows)
    assert false_rate == 0, false_drops
    assert miss_rate == 0, misses


def test_table_region_marker_drops_only_the_marked_line():
    raw = (
        "[[PAGE:8]]\n"
        "以501亿美元的品牌价值位列《Brand Finance 2024年全球品牌价值500强》第24位，以884.27\n"
        "[[TABLE]]营业收入 147,693,604,994.14 124,099,843,771.99 19.01\n"
    )
    cleaned, drops, meta = clean_body_report(raw)
    assert "501亿美元" in cleaned
    assert "884.27" in cleaned
    assert "147,693" not in cleaned
    assert meta["page_start"] == 8
    assert any(item["reason"] == "表格区域" and "147,693" in item["line"] for item in drops)


def test_line_above_table_box_is_not_marked_when_it_is_far():
    boxes = [(90.0, 581.8, 531.1, 736.7)]
    assert not _line_in_table(233.6, 244.1, "以501亿美元的品牌价值位列第24位，以884.27", boxes)
    assert _line_in_table(611.3, 621.8, "营业收入 147,693,604,994.14", boxes)
    assert _line_in_table(569.4, 580.0, "单位：元币种：人民币", boxes)


def test_risk_stops_before_next_heading_and_keeps_page():
    text = """[[PAGE:21]]
第三节 管理层讨论与分析
报告期内公司营业收入保持增长，盈利能力稳健，董事会认为经营正常，主业继续稳步推进。
(四)可能面对的风险
一是宏观经济风险；二是安全风险；三是舆情风险；四是环境保护风险。
(五)其他
七、公司因不适用准则规定或国家秘密、商业秘密等特殊原因，未按准则披露的情况和原因说明
第四节 公司治理
治理结构稳定规范运作，这段不应进入管理层讨论正文，董事会继续规范运作。
"""
    rows = parse_text(text, {"path": "600519_2023_annual.txt", "market": "CN", "ticker": "600519", "fiscal_year": 2023, "sections": ["mda", "risk"]})
    risk = next(row for row in rows if row["section"] == "risk")
    assert "宏观经济风险" in risk["section_text"]
    assert "(五)其他" not in risk["section_text"]
    assert "不适用准则" not in risk["section_text"]
    assert "治理结构" not in risk["section_text"]
    assert risk["page_start"] == 21
    assert risk["found"] == 1
    assert risk["comparable"] == 0
    assert "short_text" in risk["quality_flags"]
    assert risk["esg_per_k"] is None
    assert risk["fog_index"] is None
    assert risk["n_tokens"] < 80
    assert _page_of_snippet(risk["section_raw"], "一是宏观经济风险") == 21
    mda = next(row for row in rows if row["section"] == "mda")
    assert "宏观经济风险" in mda["section_text"]
    assert "(五)其他" in mda["section_raw"]


@pytest.mark.skipif(not MOUTAI.exists(), reason="本地没有贵州茅台 2023 年报")
def test_moutai_2023_keeps_brand_sentence_and_bounds_risk():
    from filingtext.extract import read_filing

    text = read_filing(MOUTAI)
    rows = parse_text(
        text,
        {"path": str(MOUTAI), "market": "CN", "ticker": "600519", "fiscal_year": 2023, "sections": ["mda", "risk"]},
    )
    mda = next(row for row in rows if row["section"] == "mda")
    risk = next(row for row in rows if row["section"] == "risk")
    assert "501亿美元" in mda["section_text"]
    assert "884.27" in mda["section_text"]
    assert "147,693,604,994.14" not in mda["section_text"]
    assert any(item["reason"] == "表格区域" and "147,693,604,994.14" in item["line"] for item in mda["clean_log"])
    assert "宏观经济风险" in risk["section_text"]
    assert "(五)其他" not in risk["section_text"]
    assert "不适用准则" not in risk["section_text"]
    assert risk["page_start"] == 21
    assert mda["comparable"] == 1
    assert risk["comparable"] == 0
    assert "short_text" in risk["quality_flags"]
    assert "location_missing" not in (risk["quality_flags"] or "")
