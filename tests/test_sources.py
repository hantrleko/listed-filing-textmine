from filingtext.sources import (
    annual_announcement_window,
    cninfo_column,
    cninfo_pdf_url,
    edgar_filing_url,
    is_full_annual_title,
)


def test_cohort_is_three_industries_and_forty_five_filings():
    from filingtext.cohort import COHORT, cohort_jobs

    industries = {row["industry"] for row in COHORT}
    assert industries == {"白酒", "银行", "医药"}
    assert len(COHORT) == 15
    assert len(cohort_jobs()) == 45


def test_audit_scores_need_human_labels():
    from filingtext.audit import audit_scores

    assert audit_scores([{"hit": "1", "label": ""}])["precision"] is None
    scored = audit_scores(
        [
            {"hit": "1", "label": "relevant"},
            {"hit": "1", "label": "irrelevant"},
            {"hit": "0", "label": "relevant"},
        ]
    )
    assert scored["precision"] == 0.5
    assert round(scored["recall"], 2) == 0.5
    from filingtext.sources import exchange_for_code, filing_date_from_ms

    assert exchange_for_code("600519") == "上交所"
    assert exchange_for_code("000001") == "深交所"
    assert exchange_for_code("AAPL", "US") == "SEC"
    assert filing_date_from_ms(1711929600000).startswith("2024-")
    assert annual_announcement_window(2023, 2023) == "2024-01-01~2024-08-31"


def test_cninfo_helpers():
    assert cninfo_column("600519") == "sse"
    assert cninfo_column("000001") == "szse"
    assert cninfo_column("430001") == "bj"
    assert cninfo_pdf_url("/finalpage/2024-01-01/abc.pdf") == "https://static.cninfo.com.cn/finalpage/2024-01-01/abc.pdf"
    assert is_full_annual_title("2023年年度报告")
    assert not is_full_annual_title("2023年年度报告摘要")
    assert not is_full_annual_title("2023年年度报告（英文版）")


def test_edgar_url():
    url = edgar_filing_url("0000320193", "0000320193-23-000106", "aapl-20230930.htm")
    assert url == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm"
