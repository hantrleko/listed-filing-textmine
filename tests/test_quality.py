from filingtext.quality import apply_yoy_quality


def test_yoy_flags_only_the_short_year():
    rows = [
        {"ticker": "601398", "section": "mda", "found": 1, "n_tokens": 379, "quality_flags": "", "comparable": 1, "tone_net": 0.1},
        {"ticker": "601398", "section": "mda", "found": 1, "n_tokens": 2207, "quality_flags": "", "comparable": 1, "tone_net": 0.1},
        {"ticker": "601398", "section": "mda", "found": 1, "n_tokens": 8586, "quality_flags": "", "comparable": 1, "tone_net": 0.1},
    ]
    apply_yoy_quality(rows)
    assert "yoy_length_jump" in rows[0]["quality_flags"]
    assert rows[0]["comparable"] == 0
    assert rows[1]["comparable"] == 1
    assert rows[2]["comparable"] == 1
    assert "yoy_length_jump" not in rows[2]["quality_flags"]
