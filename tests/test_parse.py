from filingtext.parse_job import parse_filename, parse_text
from filingtext.samples import SAMPLE_DOCS


def test_source_fields_survive_parse():
    rows = parse_text(
        "第三节 管理层讨论与分析\n报告期内公司营业收入保持增长，盈利能力稳健，董事会认为经营正常。\n第四节 公司治理\n治理结构稳定规范运作，这段不应进入管理层讨论。\n",
        {
            "path": "600519_2023_annual.pdf",
            "market": "CN",
            "ticker": "600519",
            "firm_name": "贵州茅台",
            "fiscal_year": 2023,
            "filing_date": "2024-04-02",
            "source_url": "https://static.cninfo.com.cn/finalpage/a.PDF",
            "exchange": "上交所",
            "fetched_at": "2026-10-20T00:00:00+00:00",
            "sections": ["mda"],
        },
    )
    assert rows[0]["source_url"].startswith("https://static.cninfo.com.cn/")
    assert rows[0]["filing_date"] == "2024-04-02"
    assert rows[0]["exchange"] == "上交所"
    assert rows[0]["fetched_at"]


def test_table_fragments_are_logged_and_removed():
    from filingtext.clean import clean_body_report

    raw = "营业收入保持增长，盈利能力稳健，董事会认为经营正常。\n其他资产减值损失 (191) (815)\n长8.22%\n公司继续经营。\n"
    cleaned, drops, meta = clean_body_report(raw)
    assert "(191)" not in cleaned
    assert "长8.22%" not in cleaned
    assert "营业收入保持增长" in cleaned
    assert "同比增长 8.22%，盈利能力稳健" in clean_body_report(
        "营业收入同比增长 8.22%，盈利能力稳健，董事会认为经营正常。\n"
    )[0]
    assert meta["n_dropped_lines"] >= 2
    assert any(item["reason"] == "表格行" for item in drops)
    assert any(item["reason"] == "残句" for item in drops)
    from pathlib import Path

    meta = parse_filename(Path("000001_2023_annual.pdf"))
    assert meta["ticker"] == "000001"
    assert meta["fiscal_year"] == 2023
    assert meta["kind"] == "annual"


def test_sample_sections_and_digital_trend():
    rows = []
    for doc in SAMPLE_DOCS:
        if doc["ticker"] != "000001":
            continue
        parsed = parse_text(
            doc["text"],
            {
                "path": doc["filename"],
                "market": "CN",
                "ticker": "000001",
                "fiscal_year": doc["fiscal_year"],
                "sections": ["mda"],
            },
        )
        assert len(parsed) == 1
        assert parsed[0]["found"] == 1
        assert "本段不应进入管理层讨论" not in parsed[0]["section_text"]
        rows.append(parsed[0])
    by_year = {row["fiscal_year"]: row for row in rows}
    assert by_year[2023]["digital_count"] > by_year[2022]["digital_count"]
    assert by_year[2024]["tone_net"] < by_year[2022]["tone_net"]
    assert "12.1" not in by_year[2022]["section_text"]


def test_table_row_removed_from_section():
    text = """第三节 管理层讨论与分析
报告期内公司营业收入保持增长并且盈利能力稳健良好，董事会认为经营正常，主业继续推进。
12.1 13.2 14.3 15.4 16.5 17.6
第四节 公司治理
治理结构稳定规范运作正常，这段不应进入管理层讨论正文。
"""
    row = parse_text(text, {"path": "x_2023_annual.txt", "market": "CN", "sections": ["mda"]})[0]
    assert row["found"] == 1
    assert "12.1" not in row["section_text"]
    assert "治理结构稳定" not in row["section_text"]
