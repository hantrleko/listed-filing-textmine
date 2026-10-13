from pathlib import Path

from filingtext.extract import extract_pdf, html_to_text
from filingtext.parse_job import parse_text
from tests.pdf_util import write_text_pdf


def test_pdf_item_split(tmp_path: Path):
    pdf = tmp_path / "NWND_2023_10K.pdf"
    write_text_pdf(
        pdf,
        [
            "ITEM 1A. RISK FACTORS",
            "Tariffs and sanctions create geopolitical risk for the firm.",
            "ITEM 7. MANAGEMENT DISCUSSION AND ANALYSIS",
            "Profitability improved after the artificial intelligence investment.",
            "ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK",
            "Interest rates may change in the next fiscal year.",
            "ITEM 8. FINANCIAL STATEMENTS",
            "Balance sheet omitted from this page.",
        ],
    )
    text = extract_pdf(pdf)
    rows = parse_text(text, {"path": str(pdf), "market": "US", "fiscal_year": 2023, "ticker": "NWND"})
    by_section = {row["section"]: row for row in rows}
    assert "artificial intelligence" in by_section["mda"]["section_text"].lower()
    assert "balance sheet" not in by_section["mda"]["section_text"].lower()
    assert "tariffs" in by_section["risk"]["section_text"].lower()
    assert "artificial intelligence" not in by_section["risk"]["section_text"].lower()


def test_html_and_sgml_strip_to_10k():
    raw = """
    <SEC-DOCUMENT>
    <DOCUMENT>
    <TYPE>EX-21
    <TEXT><html><body><p>Exhibit only.</p></body></html></TEXT>
    </DOCUMENT>
    <DOCUMENT>
    <TYPE>10-K
    <TEXT>
    <html><body>
    <p>ITEM 1A. RISK FACTORS</p>
    <p>Export controls and sanctions are the risk text.</p>
    <p>ITEM 7. MANAGEMENT DISCUSSION AND ANALYSIS</p>
    <p>Profitability improved and digital transformation continued across the firm.</p>
    <p>ITEM 8. FINANCIAL STATEMENTS</p>
    <p>Balance sheet omitted.</p>
    </body></html>
    </TEXT>
    </DOCUMENT>
    </SEC-DOCUMENT>
    """
    text = html_to_text(raw)
    assert "Exhibit only" not in text
    row = parse_text(text, {"path": "AAPL_2023_10K.htm", "market": "US", "sections": ["mda"]})[0]
    assert row["found"] == 1
    assert "digital transformation" in row["section_text"].lower()
    assert "Balance sheet" not in row["section_text"]
