from pathlib import Path

import pandas as pd

from filingtext.demo import write_samples
from filingtext.panel import to_factor, to_frame, write_duckdb
from filingtext.pipeline import run


def test_panel_roundtrip(tmp_path: Path):
    sample_dir = write_samples(tmp_path / "samples")
    out = tmp_path / "output"
    paths = run(input_dir=sample_dir, output_dir=out, workers=1)
    frame = pd.read_parquet(paths["parquet"])
    assert set(frame["market"]) == {"CN", "US"}
    assert frame["found"].sum() >= 7
    bank = frame[(frame["ticker"] == "000001") & (frame["section"] == "mda")].sort_values("fiscal_year")
    assert bank.loc[bank["fiscal_year"] == 2023, "digital_count"].iloc[0] > bank.loc[bank["fiscal_year"] == 2022, "digital_count"].iloc[0]
    assert bank.loc[bank["fiscal_year"] == 2023, "yoy_similarity"].notna().all()
    assert bank.loc[bank["fiscal_year"] == 2024, "disclosure_drift"].iloc[0] > 0
    us = frame[(frame["ticker"] == "NWND") & (frame["section"] == "mda")]
    assert len(us) == 2
    assert us["tone_method"].str.contains("seed").all()
    assert paths["dta"].exists()
    assert paths["factor_dta"].exists()
    factor = pd.read_stata(paths["factor_dta"], convert_categoricals=False)
    assert {"ticker", "fiscal_year", "fiscal_quarter", "available_date", "pit_ready"} <= set(factor.columns)
    assert any(str(value) == "000001" for value in factor["ticker"])
    assert paths["figure"].exists()
    loaded = pd.read_stata(paths["dta"])
    assert "digital_per_k" in loaded.columns
    assert set(frame.loc[frame["market"] == "CN", "stkcd"]) == {"000001", "600001"}
    wide = pd.read_parquet(paths["wide_parquet"])
    bank_wide = wide[wide["stkcd"] == "000001"].sort_values("fiscal_year")
    assert bank_wide["mda_digital_per_k"].iloc[1] > bank_wide["mda_digital_per_k"].iloc[0]
    wide_dta = pd.read_stata(paths["wide_dta"], convert_categoricals=False)
    assert any(str(value) == "000001" for value in wide_dta["stkcd"])
    assert write_duckdb(to_frame(frame.to_dict("records")), tmp_path / "again.duckdb") == len(frame)


def test_manifest_provenance_and_clean_log(tmp_path: Path):
    raw = tmp_path / "raw"
    raw.mkdir()
    body = (
        "第三节 管理层讨论与分析\n"
        "报告期内公司营业收入保持增长，盈利能力稳健，董事会认为经营正常，主业继续稳步推进。\n"
        "其他资产减值损失 (191) (815)\n"
        "第四节 公司治理\n"
        "治理结构稳定规范运作，这段不应进入管理层讨论正文。\n"
    )
    filing = raw / "600519_2023_annual.txt"
    filing.write_text(body, encoding="utf-8")
    pd.DataFrame(
        [
            {
                "path": filing.name,
                "market": "CN",
                "ticker": "600519",
                "firm_name": "贵州茅台",
                "fiscal_year": "2023",
                "report_type": "annual",
                "filing_date": "2024-04-02",
                "source_url": "https://static.cninfo.com.cn/finalpage/example.PDF",
                "exchange": "上交所",
                "fetched_at": "2026-10-20T00:00:00+00:00",
                "data_version": "",
            }
        ]
    ).to_csv(raw / "manifest.csv", index=False, encoding="utf-8-sig")
    paths = run(raw, tmp_path / "out", text_dir=tmp_path / "text", workers=1)
    frame = pd.read_parquet(paths["parquet"])
    row = frame[frame["section"] == "mda"].iloc[0]
    assert row["source_url"].startswith("https://static.cninfo.com.cn/")
    assert row["filing_date"] == "2024-04-02"
    assert row["exchange"] == "上交所"
    assert row["fetched_at"]
    assert row["data_version"]
    assert int(row["n_dropped_lines"]) >= 1
    assert Path(row["raw_text_path"]).read_text(encoding="utf-8").count("(191)") == 1
    assert "(191)" not in Path(row["text_path"]).read_text(encoding="utf-8")
    log = pd.read_json(row["clean_log_path"])
    assert (log["reason"] == "表格行").any()


def test_factor_key_uses_announcement_date_not_fiscal_year_end(tmp_path: Path):
    import hashlib

    body = (
        "第三节 管理层讨论与分析\n"
        "报告期内公司营业收入保持增长，盈利能力稳健，董事会认为经营正常，主业继续稳步推进。\n"
        "第四节 公司治理\n"
        "治理结构稳定规范运作，这段不应进入管理层讨论正文。\n"
    )
    filing = tmp_path / "600519_2023_annual.txt"
    filing.write_text(body, encoding="utf-8")
    from filingtext.parse_job import parse_text

    rows = parse_text(
        body,
        {
            "path": str(filing),
            "market": "CN",
            "ticker": "600519",
            "firm_name": "贵州茅台",
            "fiscal_year": 2023,
            "filing_date": "2024-04-02",
            "source_url": "https://static.cninfo.com.cn/finalpage/example.PDF",
            "sections": ["mda"],
        },
    )
    row = rows[0]
    assert row["fiscal_year"] == 2023
    assert row["available_date"] == "2024-04-02"
    assert row["available_date"] != "2023-12-31"
    assert row["fiscal_quarter"] == 4
    assert row["pit_ready"] == 1
    assert row["source_sha1"] == hashlib.sha1(filing.read_bytes()).hexdigest()
    factor = to_factor(to_frame(rows))
    assert factor.loc[0, "ticker"] == "600519"
    assert int(factor.loc[0, "fiscal_quarter"]) == 4
    assert factor.loc[0, "available_date"] == "2024-04-02"
    assert "mda_digital_per_k" in factor.columns
