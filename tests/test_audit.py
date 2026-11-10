import pandas as pd

from filingtext.audit import audit_scores, load_audit_summary, sample_topic_sentences
from filingtext.diagnostics import section_success_table


def test_sample_keeps_hits_and_near_misses_apart():
    documents = [
        {
            "ticker": "600519",
            "fiscal_year": 2023,
            "text": "公司推进绿色转型，并披露温室气体排放强度。报告期内经营环境复杂，但公司主业保持稳定。公司加快数字化转型。出口管制压力上升。",
        },
        {
            "ticker": "000001",
            "fiscal_year": 2022,
            "text": "利息净收入仍是主要来源。信息系统运行平稳。关税调整影响了部分结算。",
        },
    ]
    rows = sample_topic_sentences(documents, "esg", n_hit=10, n_near=10, n_random=10, seed=1)
    assert rows
    assert all(row["lexicon"] == "esg" for row in rows)
    assert any(row["hit"] == "1" and "绿色转型" in row["sentence"] for row in rows)
    assert any(row["hit"] == "0" and "经营环境" in row["sentence"] for row in rows)
    assert audit_scores([{**row, "label": "relevant"} for row in rows if row["hit"] == "1"])["precision"] == 1


def test_section_success_separates_absent_and_missing():
    report = pd.DataFrame(
        [
            {"fiscal_year": 2023, "exchange": "上交所", "mda_found": 1, "risk_found": 0, "section_status_risk": "missing"},
            {"fiscal_year": 2023, "exchange": "上交所", "mda_found": 1, "risk_found": 0, "section_status_risk": "absent"},
            {"fiscal_year": 2024, "exchange": "深交所", "mda_found": 1, "risk_found": 1, "section_status_risk": "found"},
        ]
    )
    table = section_success_table(report).set_index(["会计年度", "交易所"])
    assert table.loc[("2023", "上交所"), "讨论切出"] == "2/2"
    assert table.loc[("2023", "上交所"), "风险没切到"] == "1/2"
    assert table.loc[("2023", "上交所"), "风险已核对缺失"] == "1/2"
    assert table.loc[("2024", "深交所"), "风险切出"] == "1/1"


def test_shipped_audit_summary_matches_its_counts():
    summary = load_audit_summary()
    assert summary and set(summary["classes"]) == {"esg", "digital", "geopol"}
    assert "抽样" in summary["note"]
    for scored in summary["classes"].values():
        tp, fp, fn = scored["tp"], scored["fp"], scored["fn"]
        assert scored["n_hit"] == tp + fp
        assert scored["precision"] == tp / (tp + fp)
        assert scored["recall"] == (tp / (tp + fn) if tp + fn else None)
