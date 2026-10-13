from pathlib import Path

import pandas as pd

from filingtext.demo import write_samples
from filingtext.panel import to_frame, write_duckdb
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
