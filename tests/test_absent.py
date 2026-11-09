from filingtext.parse_job import parse_text

MDA = (
    "第三节 管理层讨论与分析\n"
    "报告期内公司营业收入保持增长，盈利能力稳健，董事会认为经营正常，主业继续稳步推进。\n"
    "第四节 公司治理\n"
    "治理结构稳定规范运作，这段不应进入管理层讨论正文内容。\n"
)


def test_baiyao_2022_heading_is_found_not_absent():
    text = (
        "第三节 管理层讨论与分析\n"
        "报告期内公司营业收入保持增长，盈利能力稳健。\n"
        "（三）公司可能面临的风险和应对措施\n"
        "原材料价格波动可能影响毛利率，公司将通过集中采购和库存管理应对。政策调整、市场竞争和产品质量事件也会带来经营压力。\n"
        "（四）其他说明\n"
        "其他事项不进入风险节。\n"
        "第四节 公司治理\n"
        "治理结构稳定规范运作，这段不应进入风险正文。\n"
    )
    rows = parse_text(text, {"path": "000538_2022_annual.txt", "market": "CN", "ticker": "000538", "fiscal_year": 2022, "sections": ["risk"]})
    risk = rows[0]
    assert risk["found"] == 1
    assert risk["section_status"] == "found"
    assert risk["section_title"] == "公司可能面临的风险和应对措施"
    assert "section_absent" not in risk["quality_flags"]
    assert "原材料价格波动" in risk["section_text"]
    assert "其他事项不进入风险节" not in risk["section_text"]


def test_baiyao_years_on_the_absent_list():
    from filingtext.quality import _confirmed_absent

    assert _confirmed_absent("000538", 2022, "risk") is False
    assert _confirmed_absent("000538", 2023, "risk") is True
    assert _confirmed_absent("000538", 2024, "risk") is True
    assert _confirmed_absent("600519", 2023, "risk") is False


def test_mid_sentence_risk_phrase_is_not_a_heading():
    text = (
        "第三节 管理层讨论与分析\n"
        "将公司可能面临的风险控制在可承受的范围内。公司已制定外汇套期保值业务管理制度，并持续跟踪敞口。\n"
        "第四节 公司治理\n"
        "治理结构稳定规范运作，这段不应进入管理层讨论正文内容。\n"
    )
    rows = parse_text(text, {"path": "600036_2023_annual.txt", "market": "CN", "ticker": "600036", "fiscal_year": 2023, "sections": ["risk"]})
    risk = rows[0]
    assert risk["found"] == 0
    assert risk["section_status"] == "missing"
    assert "section_absent" not in risk["quality_flags"]


def test_yunnan_baiyao_risk_is_confirmed_absent():
    rows = parse_text(MDA, {"path": "000538_2023_annual.txt", "market": "CN", "ticker": "000538", "fiscal_year": 2023, "sections": ["mda", "risk"]})
    risk = next(row for row in rows if row["section"] == "risk")
    assert risk["found"] == 0
    assert risk["section_status"] == "absent"
    assert risk["quality_flags"] == "section_absent"
    assert risk["esg_per_k"] is None
    assert risk["geopol_count"] == 0


def test_short_risk_stays_short_text_when_the_section_exists():
    text = (
        "第三节 管理层讨论与分析\n"
        "报告期内公司营业收入保持增长，盈利能力稳健，董事会认为经营正常，主业继续稳步推进。\n"
        "三、可能面对的风险\n"
        "出口管制使部分业务承压。\n"
        "第四节 公司治理\n"
        "治理结构稳定规范运作，这段不应进入管理层讨论正文内容。\n"
    )
    rows = parse_text(text, {"path": "600519_2023_annual.txt", "market": "CN", "ticker": "600519", "fiscal_year": 2023, "sections": ["risk"]})
    risk = rows[0]
    assert risk["found"] == 1
    assert risk["section_status"] == "found"
    assert "short_text" in risk["quality_flags"]
    assert "section_absent" not in risk["quality_flags"]
