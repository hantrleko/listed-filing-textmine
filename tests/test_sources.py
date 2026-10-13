from filingtext.sources import (
    annual_announcement_window,
    cninfo_column,
    cninfo_pdf_url,
    edgar_filing_url,
    is_full_annual_title,
)


def test_annual_window_is_the_following_year():
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
