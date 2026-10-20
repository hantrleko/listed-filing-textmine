from filingtext.features import apply_corpus, count_terms, score_document


def test_longer_chinese_term_masks_shorter():
    hits = count_terms("公司持有碳排放权并推进碳中和。", ["碳排放权", "碳排放", "碳中和"], "zh")
    assert hits["碳排放权"] == 1
    assert hits["碳中和"] == 1
    assert "碳排放" not in hits


def test_english_word_boundary():
    hits = count_terms("The impairment was isolated. Losses followed.", ["impair", "impairment", "loss", "losses"], "en")
    assert hits["impairment"] == 1
    assert hits["losses"] == 1
    assert "impair" not in hits
    assert "loss" not in hits


def test_tone_and_fog_direction():
    positive = score_document(
        "Revenue growth was strong. Profitability improved and efficiency supported the result.",
        "US",
    )
    negative = score_document(
        "The company reported a loss, an impairment, and a disruption. Weakness followed the decline.",
        "US",
    )
    assert positive["tone_net"] > negative["tone_net"]
    assert positive["fog_index"] > 0
    assert positive["fog_method"] == "gunning_fog"


def test_chinese_digital_and_fog_method():
    low = score_document("报告期内公司营业收入保持增长，盈利能力稳健，信息系统运行平稳。", "CN")
    high = score_document(
        "公司推进数字化转型，试点人工智能、机器学习和工业互联网，并建设数据中台。",
        "CN",
    )
    assert high["digital_count"] > low["digital_count"]
    assert high["fog_method"] == "zh_fog_analog"
    assert high["fog_index"] > 0


def test_page_number_and_table_stay_out_of_score():
    from filingtext.clean import clean_body_report

    raw = "[[PAGE:7]]\n7 / 143\n营业收入保持增长，盈利能力稳健，董事会认为经营正常。\n12.1 13.2 14.3 15.4 16.5\n[[PAGE:8]]\n公司推进绿色转型。\n"
    cleaned, drops, meta = clean_body_report(raw)
    assert "7 / 143" not in cleaned
    assert "12.1" not in cleaned
    assert "[[PAGE:" not in cleaned
    assert "绿色转型" in cleaned
    assert meta["page_start"] == 7
    assert meta["page_end"] == 8
    assert any(item["reason"] == "页码" for item in drops)
    assert any(item["reason"] == "表格行" for item in drops)


def test_disclosure_diff_lists_new_sentence():
    from filingtext.features import disclosure_diff

    previous = "报告期内公司营业收入保持增长，盈利能力稳健，环保投入继续提升。"
    current = "报告期内公司营业收入保持增长，并试点人工智能与数字化转型，出口管制压力上升。"
    diff = disclosure_diff(previous, current, "CN")
    changed = diff["added"] + [item["after"] for item in diff["replaced"]]
    assert any("人工智能" in sentence for sentence in changed)
    assert any(item["term"] == "人工智能" and item["change"] > 0 for item in diff["topic_changes"])


def test_negation_flips_positive_word():
    plain = score_document("公司实现改善，盈利能力稳健。", "CN")
    negated = score_document("公司没有改善，盈利能力稳健。", "CN")
    assert plain["tone_net"] > negated["tone_net"]
    assert negated["tone_method"].endswith("+negation")


def test_yoy_similarity_and_drift():
    same = "公司营业收入保持增长，并推进绿色转型与节能减排。"
    changed = "需求下滑并且出现减值，出口管制和贸易战使供应链中断，盈利承压。"
    rows = []
    for year, text in ((2022, same), (2023, same), (2024, changed)):
        scored = score_document(text, "CN")
        rows.append(
            {
                "found": 1,
                "market": "CN",
                "ticker": "000001",
                "section": "mda",
                "fiscal_year": year,
                "n_chars": scored["n_chars"],
                **scored,
            }
        )
    apply_corpus(rows)
    by_year = {row["fiscal_year"]: row for row in rows}
    assert by_year[2022]["yoy_similarity"] is None
    assert by_year[2023]["yoy_similarity"] > 0.99
    assert by_year[2023]["disclosure_drift"] < 0.01
    assert by_year[2024]["disclosure_drift"] > by_year[2023]["disclosure_drift"]
    assert "token_counts" not in rows[0]
