import hashlib
import json
import threading
import urllib.request

import numpy as np
import pandas as pd
import pytest

from filingtext import jobs
from filingtext.factor_eval import _neutralize, _trade_cost, attach_text, evaluate_text_factors
from filingtext.originals import remember_original, restore_original
from filingtext.panel_api import serve
from filingtext.workspace import build_from_codes


def _monthly(n_months: int, n_names: int = 16) -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2018-01-31", periods=n_months, freq="ME")
    for i, day in enumerate(dates):
        for j in range(n_names):
            tone = (j - 8) / 8 + (i % 5) * 0.02
            rows.append(
                {
                    "date": day,
                    "ticker": f"{j + 1:06d}",
                    "mktcap": 1e9 * (j + 1),
                    "industry": f"ind{j % 4}",
                    "fwd_ret": 0.01 * tone + 0.002 * ((i + j) % 5 - 2),
                    "mda_tone_net": tone,
                    "mda_disclosure_drift": 0.2 + (j % 3) * 0.1,
                }
            )
    return pd.DataFrame(rows)


def test_asof_uses_only_filings_already_available():
    monthly = pd.DataFrame(
        {
            "date": ["2023-06-30", "2024-06-30"],
            "ticker": ["000001", "000001"],
            "fwd_ret": [0.01, 0.01],
            "mktcap": [1e9, 1e9],
            "industry": ["白酒", "白酒"],
        }
    )
    text = pd.DataFrame(
        {
            "ticker": ["1", "1"],
            "available_date": ["2023-04-30", "2024-04-30"],
            "mda_tone_net": [0.1, 0.9],
            "mda_disclosure_drift": [0.2, 0.8],
            "mda_comparable": [1, 1],
        }
    )
    out = attach_text(monthly, text, ["mda_tone_net", "mda_disclosure_drift"])
    assert out.loc[0, "mda_tone_net"] == pytest.approx(0.1)
    assert out.loc[1, "mda_tone_net"] == pytest.approx(0.9)


def test_stale_filing_is_left_blank():
    monthly = pd.DataFrame(
        {"date": ["2024-06-30"], "ticker": ["000001"], "fwd_ret": [0.01], "mktcap": [1e9], "industry": ["白酒"]}
    )
    text = pd.DataFrame(
        {
            "ticker": ["000001"],
            "available_date": ["2020-01-15"],
            "mda_tone_net": [0.4],
            "mda_disclosure_drift": [0.2],
            "mda_comparable": [1],
        }
    )
    out = attach_text(monthly, text, ["mda_tone_net", "mda_disclosure_drift"])
    assert np.isnan(out.loc[0, "mda_tone_net"])


def test_neutralize_is_orthogonal_to_size():
    rng = np.random.default_rng(7)
    values = rng.normal(size=20)
    mktcap = rng.uniform(1e8, 1e10, size=20)
    industry = np.array(["a"] * 10 + ["b"] * 10)
    resid = _neutralize(values, mktcap, industry)
    weight = np.sqrt(mktcap)
    assert abs(float(np.sum(weight * resid))) < 1e-6


def test_full_cost_charges_both_sides_and_borrow():
    assert _trade_cost(1.0) == pytest.approx(2 * 0.0018 + 0.003)


def test_short_sample_does_not_report_a_return():
    result = evaluate_text_factors(_monthly(10))
    tone = result["factors"]["mda_tone_net"]
    assert tone["status"] == "too_few_months"
    assert "dev_ic" not in tone
    assert "oos_net_ann" not in tone


def test_long_sample_runs_the_same_windows():
    result = evaluate_text_factors(_monthly(48))
    tone = result["factors"]["mda_tone_net"]
    assert result["status"] == "ok"
    assert tone["status"] == "ok"
    assert tone["n_months"] == 48
    assert tone["direction"] == 1
    assert np.isfinite(tone["dev_ic"])
    assert np.isfinite(tone["oos_net_ann"])
    assert np.isfinite(tone["holdout_net_ann"])


def test_original_is_restored_without_the_network(tmp_path, monkeypatch):
    import filingtext.originals as originals

    monkeypatch.setattr(originals, "ORIGINAL_DIR", tmp_path / "cache")
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF-1.4 test")
    digest = remember_original(source, "https://example.test/a.pdf")
    dest = tmp_path / "again.pdf"
    assert restore_original("https://example.test/a.pdf", dest)
    assert dest.read_bytes() == b"%PDF-1.4 test"
    assert digest == hashlib.sha1(b"%PDF-1.4 test").hexdigest()


def test_nine_filings_pass_the_old_web_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("filingtext.workspace.WORKSPACE_RAW", tmp_path)
    monkeypatch.setattr("filingtext.workspace.download_cninfo", lambda *args, **kwargs: [])
    with pytest.raises(RuntimeError, match="没有下载"):
        build_from_codes("CN", "000001,600519,600276", 2022, 2024)


def test_large_web_batch_needs_confirmation_and_stops_at_200():
    codes = ",".join(f"{i:06d}" for i in range(1, 11))
    with pytest.raises(ValueError, match="确认"):
        build_from_codes("CN", codes, 2020, 2024)
    wide = ",".join(f"{i:06d}" for i in range(1, 51))
    with pytest.raises(ValueError, match="200"):
        build_from_codes("CN", wide, 2020, 2024, confirm_large=True)


def test_job_record_omits_contact_and_finishes(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "JOB_DIR", tmp_path)

    def fake_build(*args, **kwargs):
        assert kwargs["confirm_large"] is True
        assert kwargs["edgar_contact"] == ""
        return {"downloaded": ["a.pdf"], "summary": {"n_found": 2, "n_firms": 1}}

    monkeypatch.setattr("filingtext.workspace.build_from_codes", fake_build)
    job_id = jobs.create_job(
        {"market": "CN", "codes": "000001", "start": 2023, "end": 2023, "confirm_large": True, "edgar_contact": "a@b.edu"}
    )
    done = jobs.execute(job_id)
    assert done["status"] == "done"
    assert done["summary"]["downloaded"] == 1
    assert "edgar_contact" not in json.dumps(done)


def test_panel_api_hides_section_text(tmp_path):
    frame = pd.DataFrame(
        {
            "ticker": ["000001"],
            "mda_tone_net": [0.2],
            "mda_new_sentence_share": [0.3],
            "source_sha1": ["deadbeef"],
            "section_text": ["不应出现的正文"],
        }
    )
    frame.to_parquet(tmp_path / "panel_factor.parquet")
    server = serve(tmp_path, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/panel/factor.json") as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
    row = payload["rows"][0]
    assert row["ticker"] == "000001"
    assert row["mda_new_sentence_share"] == pytest.approx(0.3)
    assert "section_text" not in row
    assert "source_sha1" not in row
    body = json.dumps(payload, ensure_ascii=False)
    assert "不应出现" not in body
    assert "deadbeef" not in body
