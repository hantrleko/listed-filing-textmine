from filingtext.clean import drop_repeated_pages, is_table_noise
from filingtext.samples import SAMPLE_DOCS
from filingtext.sections import split_sections


def _doc(name: str) -> str:
    return next(doc["text"] for doc in SAMPLE_DOCS if doc["filename"] == name)


def test_cn_body_not_toc_and_not_governance():
    sections = split_sections(_doc("000001_2022_annual.txt"), "CN")
    mda = sections["mda"].text
    assert "营业收入保持增长" in mda
    assert "该句应仍留在管理层讨论中" in mda
    assert "本段不应进入管理层讨论" not in mda
    assert ".......... 3" not in mda


def test_soft_title_does_not_drop_following_sentence():
    text = """第三节 管理层讨论与分析
报告期内公司营业收入保持增长，盈利能力稳健，环保投入继续提升。
社会责任
后续这句仍然属于管理层讨论，不应该被小节标题截断。
第四节 公司治理
治理结构稳定并且这段不应进入管理层讨论正文。
"""
    mda = split_sections(text, "CN")["mda"].text
    assert "不应该被小节标题截断" in mda
    assert "治理结构稳定" not in mda


def test_us_10k_items_stop_at_next_item():
    sections = split_sections(_doc("NWND_2023_10K.txt"), "US", form="10-K")
    assert "inventory impairment" in sections["mda"].text
    assert "must not enter the MD&A" not in sections["mda"].text
    assert "entity list" in sections["risk"].text
    assert "inventory impairment" not in sections["risk"].text


def test_us_10q_item2_is_mda():
    text = """FORM 10-Q
ITEM 1. FINANCIAL STATEMENTS
Balance sheet only and nothing about operations.
ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS
Revenue was strong and profitability improved in the quarter under review.
ITEM 3. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK
Interest rate risk is described here and not in the discussion.
"""
    sections = split_sections(text, "US", form="10-Q")
    assert "profitability improved" in sections["mda"].text
    assert "Balance sheet" not in sections["mda"].text
    assert "Interest rate risk" not in sections["mda"].text


def test_repeated_page_header_removed():
    pages = [
        ["示例公司年度报告", "正文一讨论营业收入增长"],
        ["示例公司年度报告", "正文二讨论节能减排"],
        ["示例公司年度报告", "正文三讨论地缘政治"],
    ]
    text = drop_repeated_pages(pages)
    assert "示例公司年度报告" not in text
    assert "正文一" in text and "正文三" in text


def test_numbered_discussion_heading():
    text = (
        "4讨论与分析 ................................................................................................ 14\n"
        "7董事会报告 ................................................................................................ 40\n"
        "4 讨论与分析\n"
        "报告期内公司营业收入保持增长，盈利能力稳健，并推进绿色金融。董事会认为经营正常。\n"
        "7 董事会报告\n"
        "治理结构稳定规范运作，这段不应进入管理层讨论正文内容。\n"
    )
    mda = split_sections(text, "CN")["mda"].text
    assert "绿色金融" in mda
    assert "治理结构稳定" not in mda
    text = (
        "第三章管理层讨论与分析 ................................................................................................ 22\n"
        "第四章公司治理 ............................................................................................................ 40\n"
        "第三章管理层讨论与分析\n"
        "报告期内公司营业收入保持增长，并推进数字化转型与绿色金融，董事会认为经营正常。\n"
        "第四章公司治理\n"
        "治理结构稳定规范运作，这段不应进入管理层讨论正文内容。\n"
    )
    mda = split_sections(text, "CN")["mda"].text
    assert "数字化转型" in mda
    assert "治理结构稳定" not in mda
    assert "...." not in mda


def test_glued_header_keeps_following_sentence():
    text = (
        "第三节管理层讨论与分析报告期内公司营业收入保持增长，盈利能力稳健良好，董事会认为经营状况正常。\n"
        "第四节 公司治理\n"
        "治理结构稳定规范运作，这段不应进入管理层讨论正文内容。\n"
    )
    mda = split_sections(text, "CN")["mda"].text
    assert "营业收入保持增长" in mda
    assert "治理结构稳定" not in mda


def test_us_header_and_body_on_one_line():
    text = (
        "ITEM 1A. RISK FACTORS  4\n"
        "ITEM 7. MANAGEMENT DISCUSSION AND ANALYSIS Revenue increased and profitability improved "
        "after the artificial intelligence investment in cloud computing systems this year.\n"
        "ITEM 8. FINANCIAL STATEMENTS\n"
        "Balance sheet omitted from the statement section.\n"
    )
    mda = split_sections(text, "US", form="10-K")["mda"].text
    assert "artificial intelligence" in mda
    assert "Balance sheet" not in mda


def test_cn_risk_subsection_stays_inside_mda():
    text = """第三节 管理层讨论与分析
报告期内公司营业收入保持增长，盈利能力稳健，环保投入继续提升，董事会认为经营正常。
三、可能面对的风险
出口管制和关税使部分业务承压，供应链中断需要持续跟踪。
第四节 公司治理
治理结构稳定规范运作，这段不应进入管理层讨论正文内容。
"""
    sections = split_sections(text, "CN")
    assert "出口管制" in sections["mda"].text
    assert "出口管制" in sections["risk"].text
    assert "治理结构稳定" not in sections["mda"].text


def test_table_noise():
    assert is_table_noise("12.1 13.2 14.3 15.4 16.5 17.6")
    assert not is_table_noise("公司营业收入保持增长，盈利能力稳健。")
