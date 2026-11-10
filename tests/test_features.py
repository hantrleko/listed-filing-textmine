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


def test_chinese_negation_drops_topic_hit():
    from filingtext.features import count_active_terms

    assert count_active_terms("公司不存在经济制裁敞口。", ["经济制裁", "制裁"], "zh").get("经济制裁", 0) == 0
    assert count_active_terms("公司受到经济制裁。", ["经济制裁"], "zh").get("经济制裁", 0) == 1
    low = score_document("报告期内公司营业收入保持增长，盈利能力稳健，信息系统运行平稳。", "CN")
    high = score_document(
        "公司推进数字化转型，试点人工智能、机器学习和工业互联网，并建设数据中台。",
        "CN",
    )
    assert high["digital_count"] > low["digital_count"]
    assert high["fog_method"] == "zh_fog_analog"
    assert high["fog_index"] > 0


def test_term_decisions_mark_negation_and_legal_sanction():
    from filingtext.features import term_decisions

    text = "公司不存在经济制裁敞口。公司受到经济制裁。公司避免法律制裁。公司建设制裁合规制度。公司提升制裁风险防范。"
    raw = "[[PAGE:21]]\n" + text
    rows = term_decisions(raw.replace("[[PAGE:21]]\n", ""), raw, ["经济制裁", "制裁"], "zh", geopol=True)
    by_sentence = {row["sentence"]: row for row in rows}
    negated = by_sentence["公司不存在经济制裁敞口。"]
    counted = by_sentence["公司受到经济制裁。"]
    legal = by_sentence["公司避免法律制裁。"]
    compliance = by_sentence["公司建设制裁合规制度。"]
    strengthened = by_sentence["公司提升制裁风险防范。"]
    assert negated["status"] == "排除" and negated["reason"] == "否定" and negated["page"] == 21
    assert counted["status"] == "计入" and counted["reason"] == "" and counted["term"] == "经济制裁"
    assert legal["status"] == "排除" and legal["reason"] == "法律制裁" and legal["term"] == "制裁"
    assert compliance["status"] == "排除" and compliance["reason"] == "制裁合规"
    assert strengthened["status"] == "排除" and strengthened["reason"] == "提升制裁"


def test_evidence_sentence_keeps_page():
    from filingtext.features import evidence_sentences

    raw = "[[PAGE:12]]\n公司推进绿色转型，并披露温室气体。\n[[PAGE:13]]\n出口管制扰动供应链。\n"
    cleaned = "公司推进绿色转型，并披露温室气体。\n出口管制扰动供应链。"
    rows = evidence_sentences(cleaned, raw, ["绿色转型", "出口管制"], "zh")
    by_term = {row["term"]: row for row in rows}
    assert by_term["绿色转型"]["page"] == 12
    assert by_term["出口管制"]["page"] == 13
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


def test_legal_sanction_is_not_geopolitical():
    labels = [
        ("公司经营可能面临法律制裁，需要加强合规管理。", 0),
        ("持续强化制裁合规管理，并完善反洗钱流程。", 0),
        ("提升制裁风险防范能力。", 0),
        ("推进合规文化建设，提升制裁和洗钱风险管理。", 0),
        ("美国对相关实体实施经济制裁，出口管制压力上升。", 2),
        ("出口管制与制裁压力加大。", 2),
    ]
    for text, minimum in labels:
        score = score_document(text, "CN")
        if minimum == 0:
            assert score["geopol_count"] == 0, text
        else:
            assert score["geopol_count"] >= minimum, text


def test_embedded_risk_subsection():
    from filingtext.sections import split_sections

    text = """第三节 管理层讨论与分析
报告期内公司营业收入保持增长，盈利能力稳健，董事会认为经营正常。
3.2 风险管理
出口管制和关税使部分业务承压，相关风险需要持续跟踪并披露应对措施。
第四节 公司治理
治理结构稳定规范运作，这段不应进入管理层讨论正文内容。
"""
    sections = split_sections(text, "CN")
    assert "出口管制" in sections["mda"].text
    assert "出口管制" in sections["risk"].text
    assert "治理结构稳定" not in sections["risk"].text


def test_parenthetical_risk_heading():
    from filingtext.sections import split_sections

    text = """第三节 管理层讨论与分析
报告期内公司营业收入保持增长，盈利能力稳健，董事会认为经营正常。
（二）面临的主要风险
汇率和关税变化使部分业务承压，相关风险需要持续跟踪并披露应对措施。
第四节 公司治理
治理结构稳定规范运作，这段不应进入风险小节。
"""
    sections = split_sections(text, "CN")
    assert "汇率和关税" in sections["risk"].text
    assert "治理结构稳定" not in sections["risk"].text
    assert "汇率和关税" in sections["mda"].text


def test_negation_flips_positive_word():
    plain = score_document("公司实现改善，盈利能力稳健。", "CN")
    negated = score_document("公司没有改善，盈利能力稳健。", "CN")
    assert plain["tone_net"] > negated["tone_net"]
    assert negated["tone_method"].endswith("+clause_negation")


def test_clause_negation_stops_at_the_comma():
    crossed = score_document("公司没有扩张，盈利实现改善。", "CN")
    local = score_document("公司并未实现改善。", "CN")
    plain = score_document("盈利实现改善。", "CN")
    assert plain["tone_net"] > local["tone_net"]
    assert crossed["tone_net"] > local["tone_net"]


def test_distant_topic_negation_is_still_inside_the_clause():
    assert score_document("公司不存在较大的出口管制影响。", "CN")["geopol_count"] == 0
    assert score_document("不良贷款上升，绿色信贷继续投放。", "CN")["esg_count"] >= 1


def test_formal_tone_counts_risk_but_not_risk_management():
    managed = score_document("董事会风险管理委员会听取了本季度的报告。", "CN")
    exposed = score_document("公司面临的风险上升，并且出现亏损。", "CN")
    assert managed["tone_method"].startswith("yao2021_formal")
    assert managed["tone_neg"] == 0
    assert exposed["tone_net"] < 0


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
                "section_text": text,
                **scored,
            }
        )
    apply_corpus(rows)
    by_year = {row["fiscal_year"]: row for row in rows}
    assert by_year[2022]["yoy_similarity"] is None
    assert by_year[2023]["yoy_similarity"] > 0.99
    assert by_year[2023]["disclosure_drift"] < 0.01
    assert by_year[2024]["disclosure_drift"] > by_year[2023]["disclosure_drift"]
    assert by_year[2023]["yoy_jaccard"] > 0.99
    assert by_year[2024]["yoy_jaccard"] < by_year[2023]["yoy_jaccard"]
    assert by_year[2023]["new_sentence_share"] == 0
    assert by_year[2024]["new_sentence_share"] > 0
    assert "token_counts" not in rows[0]
