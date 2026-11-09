from filingtext.parse_job import parse_text
from filingtext.quality import apply_title_shift, apply_yoy_quality


def test_yoy_flags_only_the_short_year():
    rows = [
        {"ticker": "601398", "section": "mda", "found": 1, "n_tokens": 379, "quality_flags": "", "comparable": 1, "tone_net": 0.1},
        {"ticker": "601398", "section": "mda", "found": 1, "n_tokens": 2207, "quality_flags": "", "comparable": 1, "tone_net": 0.1},
        {"ticker": "601398", "section": "mda", "found": 1, "n_tokens": 8586, "quality_flags": "", "comparable": 1, "tone_net": 0.1},
    ]
    apply_yoy_quality(rows)
    assert "yoy_length_jump" in rows[0]["quality_flags"]
    assert rows[0]["comparable"] == 0
    assert rows[1]["comparable"] == 1
    assert rows[2]["comparable"] == 1
    assert "yoy_length_jump" not in rows[2]["quality_flags"]


def test_title_shift_flags_only_the_different_year():
    rows = [
        {"ticker": "600000", "section": "risk", "found": 1, "section_status": "found", "section_title": "公司可能面对的风险", "quality_flags": "", "comparable": 1},
        {"ticker": "600000", "section": "risk", "found": 1, "section_status": "found", "section_title": "公司可能面对的风险", "quality_flags": "", "comparable": 1},
        {"ticker": "600000", "section": "risk", "found": 1, "section_status": "found", "section_title": "风险管理", "quality_flags": "", "comparable": 1},
    ]
    apply_title_shift(rows)
    assert "title_shift" not in rows[0]["quality_flags"]
    assert "title_shift" not in rows[1]["quality_flags"]
    assert rows[2]["quality_flags"] == "title_shift"
    assert rows[2]["comparable"] == 1


def test_same_risk_title_and_absent_year_are_not_flagged():
    rows = [
        {"ticker": "600519", "section": "risk", "found": 1, "section_status": "found", "section_title": "可能面对的风险", "quality_flags": "short_text", "comparable": 0},
        {"ticker": "600519", "section": "risk", "found": 1, "section_status": "found", "section_title": "可能面对的风险", "quality_flags": "short_text", "comparable": 0},
        {"ticker": "000538", "section": "risk", "found": 1, "section_status": "found", "section_title": "公司可能面临的风险和应对措施", "quality_flags": "", "comparable": 1},
        {"ticker": "000538", "section": "risk", "found": 0, "section_status": "absent", "section_title": "", "quality_flags": "section_absent", "comparable": 0},
    ]
    apply_title_shift(rows)
    assert all("title_shift" not in row["quality_flags"] for row in rows)


def test_outside_risk_management_keeps_ratios_empty():
    text = (
        "第三节 管理层讨论与分析\n"
        "报告期内公司营业收入保持增长，盈利能力稳健，董事会认为经营正常。\n"
        "第四节 公司治理\n"
        "治理结构稳定规范运作，这段不应进入管理层讨论正文内容。\n"
        "风险管理\n"
        "信用风险、市场风险和操作风险由专门委员会按季监测，并形成书面报告提交董事会。\n"
    )
    rows = parse_text(text, {"path": "601398_2022_annual.txt", "market": "CN", "ticker": "601398", "fiscal_year": 2022, "sections": ["risk"]})
    risk = rows[0]
    assert risk["found"] == 0
    assert risk["section_status"] == "missing"
    assert risk["esg_per_k"] is None
