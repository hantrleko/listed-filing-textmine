"""交互式词典验证、章节诊断和面板时序。"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="年报文本特征引擎", layout="wide")

import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from filingtext import __version__
from filingtext.clean import CLEANING_RULES, normalize
from filingtext.config import OUTPUT_DIR, WORKSPACE_OUT
from filingtext.extract import extract_pdf, html_to_text
from filingtext.features import (
    EN_STOP,
    ZH_STOP,
    apply_corpus,
    disclosure_diff,
    term_decisions,
    highlight_spans,
    score_document,
    tokenize,
)
from filingtext.lexicon import DICTIONARY_VERSION, tone_lexicons, topic_lexicons
from filingtext.panel import regression_readiness
from filingtext.parse_job import parse_text
from filingtext.samples import SAMPLE_DOCS
from filingtext.sections import diagnose_anchors, split_sections

COLORS = {
    "esg": "#b7e4c7",
    "digital": "#a5d8ff",
    "geopol": "#ffd6a5",
    "pos": "#d8f3dc",
    "neg": "#ffc9c9",
    "unc": "#fff3bf",
    "lit": "#e5dbff",
    "custom": "#ffe066",
}
LABELS = {
    "esg": "ESG / 绿色转型",
    "digital": "数智化 / AI",
    "geopol": "地缘风险",
    "pos": "积极语气",
    "neg": "消极语气",
    "unc": "不确定",
    "lit": "诉讼监管",
    "custom": "临时词",
}


def _synthetic_banner() -> None:
    st.markdown(
        """
        <div style="position:sticky;top:3.5rem;z-index:1000;background:#7f1d1d;color:#fff;
        padding:10px 14px;border-radius:6px;font-weight:700;margin-bottom:12px;">
        合成演示数据 · 不是任何真实公司的年报或监管申报 · 截图不能当作研究结果
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("**当前是合成演示**")


def _render_source(row: dict | None) -> None:
    if not row or not row.get("source_url"):
        return
    pages = ""
    if row.get("page_start"):
        pages = f"第 {row['page_start']}–{row['page_end']} 页"
    st.markdown(
        f"**来源** {row.get('firm_name') or ''} {row.get('stkcd') or row.get('ticker') or ''} · "
        f"报告期 {row.get('fiscal_year') or ''} 年{row.get('report_type') or ''} · "
        f"公告日 {row.get('announce_date') or row.get('filing_date') or '缺失'} · "
        f"可用日 {row.get('available_date') or '缺失'} · "
        f"{row.get('exchange') or ''} · {pages}"
    )
    if row.get("source_url"):
        st.markdown(f"[打开原始申报文件]({row['source_url']})")
    st.caption(
        "回归对齐用 available_date（公告日 T+1，与因子工作台 NOTICE_DATE 一致）。不要把 fiscal_year 当成信息已公开日期。"
        f" 词典 {row.get('data_version') or DICTIONARY_VERSION} · 程序 {row.get('app_version') or __version__}"
        f" · 原文 SHA1 {str(row.get('source_sha1') or '')[:12] or '无'}"
    )


def main() -> None:
    st.title("上市公司文本特征引擎")
    st.caption(
        "章节切分、词典命中高亮、词云和面板时序。语气词是可编辑种子词，不是 Loughran-McDonald 官方全表。"
        " 源码与处理规则：[hantrleko/listed-filing-textmine](https://github.com/hantrleko/listed-filing-textmine)。"
    )

    mode = st.sidebar.radio("开始", ["样本案例", "我的面板"], horizontal=True)
    if mode == "样本案例":
        _synthetic_banner()
    market = "CN"
    form = "annual"
    sample_frame = None
    sample_name = ""
    panel_dir = OUTPUT_DIR
    if mode == "样本案例":
        case = st.sidebar.radio("案例", ["示例银行", "示例制造", "Northwind 10-K"])
        ticker = {"示例银行": "000001", "示例制造": "600001", "Northwind 10-K": "NWND"}[case]
        docs = [doc for doc in SAMPLE_DOCS if doc["ticker"] == ticker]
        years = sorted(doc["fiscal_year"] for doc in docs)
        prefer = 2023 if 2023 in years else years[-1]
        year = st.sidebar.selectbox("年份", years, index=years.index(prefer), key=f"year-{ticker}")
        chosen = next(doc for doc in docs if doc["fiscal_year"] == year)
        raw = chosen["text"]
        market = chosen["market"]
        form = "10-K" if market == "US" else "annual"
        sample_name = chosen["firm_name"]
        sample_frame = _case_frame(ticker)
    else:
        panel_dir = WORKSPACE_OUT
        raw, market, form, source_meta = _workspace_page()

    lang = "zh" if market == "CN" else "en"
    selected = st.sidebar.multiselect(
        "高亮词表",
        list(LABELS),
        default=["esg", "digital", "geopol"],
        format_func=lambda key: LABELS[key],
    )
    extra_terms = _split_terms(st.sidebar.text_area("临时词", height=90, placeholder="一行一个，或用逗号分隔"), lang)

    if mode == "样本案例":
        _render_case_intro(sample_name, market, sample_frame, int(year), docs)
        source_meta = {}
    view, section_name, anchors, parsed, row = _prepare(raw, market, form, source_meta)

    tabs = st.tabs(["原文与清洗", "词云", "方法与诊断", "面板时序"])
    with tabs[0]:
        if view:
            _render_highlight(view, market, lang, section_name, selected, extra_terms, row)
            _render_clean_compare(row, market, section_name)
        else:
            st.info("左侧可以看样本案例。做自己的表时，用「我的面板」填写代码和年份，或上传文件。")
    with tabs[1]:
        if view:
            _render_cloud(view, lang)
        else:
            st.info("先提供一段文本。")
    with tabs[2]:
        _render_method(anchors if raw else [], parsed if raw else [])
    with tabs[3]:
        _render_panel(panel_dir, fallback=sample_frame if mode == "样本案例" else None)


@st.cache_data(show_spinner=False)
def _case_frame(ticker: str) -> pd.DataFrame:
    docs = [doc for doc in SAMPLE_DOCS if doc["ticker"] == ticker]
    rows: list[dict] = []
    for doc in docs:
        rows.extend(
            parse_text(
                doc["text"],
                {
                    "path": doc["filename"],
                    "market": doc["market"],
                    "ticker": doc["ticker"],
                    "firm_name": doc["firm_name"],
                    "fiscal_year": doc["fiscal_year"],
                    "report_type": doc["report_type"],
                    "sections": ["mda", "risk"] if doc["market"] == "US" else ["mda", "risk"],
                },
            )
        )
    apply_corpus(rows)
    for row in rows:
        row.pop("section_text", None)
        row.pop("section_raw", None)
        row.pop("clean_log", None)
    return pd.DataFrame(rows)


def _render_case_intro(name: str, market: str, frame: pd.DataFrame, year: int, docs: list[dict]) -> None:
    st.subheader(f"【合成演示】{name}")
    st.caption("下面的公司和正文都是合成的。词频不是经营表现。口径见「方法与诊断」。")
    if frame is None or frame.empty:
        return
    show = frame.sort_values(["fiscal_year", "section"]).copy()
    if "found" in show.columns:
        show = show[show["found"] == 1]
    mda = show[show["section"] == "mda"]
    comparable = _comparable_rows(mda)
    if not comparable.empty and comparable["fiscal_year"].nunique() >= 2:
        from ui.charts import render_freq_tone_trends

        render_freq_tone_trends(comparable)
        summary = _describe_case(comparable)
        if summary:
            st.write(summary)
    else:
        st.caption("可比的管理层讨论不足两年，这里不写「由…到…」。")
    _render_drift(docs, year, market, "mda")


def _describe_case(frame: pd.DataFrame) -> str:
    mda = frame[frame["section"] == "mda"].sort_values("fiscal_year")
    if len(mda) < 2:
        return ""
    first, last = mda.iloc[0], mda.iloc[-1]
    y0, y1 = int(first["fiscal_year"]), int(last["fiscal_year"])
    pieces = [f"{y0}–{y1} 的 MD&A"]
    for column, label in (
        ("digital_per_k", "数智化强度"),
        ("esg_per_k", "绿色/ESG 强度"),
        ("geopol_per_k", "地缘词强度"),
        ("tone_net", "语气净值"),
    ):
        if pd.isna(first[column]) or pd.isna(last[column]):
            continue
        pieces.append(f"{label}由 {_fmt(first[column])} 到 {_fmt(last[column])}")
    if len(pieces) == 1:
        return ""
    if pd.notna(last["disclosure_drift"]):
        pieces.append(f"{y1} 年相对上一年的披露漂移是 {_fmt(last['disclosure_drift'])}")
    return "；".join(pieces) + "。"


def _trap_notes(raw: str, view: str, market: str, section_name: str) -> list[str]:
    notes = []
    if market == "CN":
        if ".........." in raw and ".........." not in view:
            notes.append("这一节已经去掉目录点线。正文从真正的「管理层讨论与分析」标题之后开始。")
        if "本段不应进入管理层讨论" in raw and "本段不应进入管理层讨论" not in view:
            notes.append("公司治理段留在外面。当前正文里没有「本段不应进入管理层讨论」。")
        if "该句应仍留在管理层讨论中" in raw and "该句应仍留在管理层讨论中" in view:
            notes.append("「社会责任」只是小节标题，它下面那句仍留在管理层讨论里。")
    else:
        if "must not enter the MD&A" in raw and "must not enter the MD&A" not in view:
            notes.append("Item 8 的报表句没有进入当前章节。")
        if section_name == "mda":
            notes.append("当前是 Item 7 MD&A。风险因素在「查看范围」的 risk。")
        if section_name == "risk":
            notes.append("当前是 Item 1A 风险因素。经营讨论在「查看范围」的 mda。")
    return notes


def _source_text() -> str:
    uploaded = st.file_uploader("上传披露文件", type=["pdf", "txt", "htm", "html"])
    pasted = st.text_area("或直接粘贴", height=160)
    if uploaded is not None:
        return _read_upload(uploaded)
    if pasted.strip():
        return normalize(pasted)
    return ""


def _prepare(raw: str, market: str, form: str, source_meta: dict | None = None):
    if not raw:
        return "", "", [], [], None
    form_arg = None if market == "CN" else form
    sections = split_sections(raw, market, form=form_arg)
    names = ["全文"] + list(sections)
    default_index = names.index("mda") if "mda" in names else 0
    choice = st.selectbox("查看范围", names, index=default_index)
    meta = {
        "path": "upload.txt",
        "market": market,
        "report_type": form,
        "sections": list(sections) or None,
    }
    meta.update({key: value for key, value in (source_meta or {}).items() if value not in (None, "")})
    parsed = parse_text(raw, meta)
    anchors = diagnose_anchors(raw, market, form=form_arg)
    if choice == "全文":
        return raw, "全文", anchors, parsed, None
    chosen_row = next((item for item in parsed if item["section"] == choice), None)
    cleaned = (chosen_row or {}).get("section_text") or ""
    return cleaned or sections[choice].text, choice, anchors, parsed, chosen_row


def _read_upload(uploaded) -> str:
    suffix = Path(uploaded.name).suffix.lower()
    data = uploaded.getvalue()
    if suffix == ".pdf":
        handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        handle.write(data)
        handle.close()
        path = Path(handle.name)
        try:
            return extract_pdf(path)
        finally:
            path.unlink(missing_ok=True)
    text = data.decode("utf-8", errors="ignore")
    if suffix in {".htm", ".html"} or "<html" in text[:800].lower() or "<DOCUMENT>" in text[:800].upper():
        return html_to_text(text)
    return normalize(text)


def _groups(lang: str, selected: list[str], extra_terms: list[str]) -> list[tuple[str, list[str]]]:
    topics = topic_lexicons()[lang]
    tones = tone_lexicons()[lang]
    groups = []
    for key in selected:
        if key in topics:
            groups.append((key, topics[key]))
        elif key in tones:
            groups.append((key, tones[key]))
    if extra_terms:
        groups.append(("custom", extra_terms))
    return groups


def _render_highlight(text, market, lang, section_name, selected, extra_terms, row) -> None:
    scored = score_document(text, market)
    st.warning(
        "词频衡量的是披露用词强度，不是真实风险或 ESG 表现。"
        "某一类为 0，只表示词典版本 "
        f"{DICTIONARY_VERSION} 没有命中，不能据此说企业没有该类风险。"
        "跨年漂移还可能来自模板或篇幅变化，不能直接读成风险升降。"
    )
    _render_source(row)
    comparable = _row_comparable(row, scored)
    if row and row.get("quality_flags"):
        st.warning(_quality_message(str(row.get("quality_flags"))))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("章节", section_name)
    c2.metric("内容词", f"{scored['n_tokens']}")
    c3.metric("中文类比可读性" if lang == "zh" else "Fog", _fmt(scored["fog_index"]) if comparable else "不适用")
    c4.metric("语气净值", _fmt(scored["tone_net"]) if comparable else "不适用")
    c5, c6, c7 = st.columns(3)
    c5.metric("ESG 词频/千词", _fmt(scored["esg_per_k"]) if comparable else "不适用")
    c6.metric("数智化词频/千词", _fmt(scored["digital_per_k"]) if comparable else "不适用")
    c7.metric("地缘词频/千词", _fmt(scored["geopol_per_k"]) if comparable else "不适用")
    if comparable:
        st.caption(
            f"同时看三列：ESG 命中 {scored['esg_count']} 次、每千词 {_fmt(scored['esg_per_k'])}、每千字 {_fmt(scored['esg_per_char_k'])}；"
            f"本章 {scored['n_chars']} 字。章节没切出来时这些值是空的，不是 0。"
            "每千词和每千字是两套分母，用来看结论会不会被篇幅算法带偏。"
        )
    else:
        st.caption(
            f"这一节 {scored['n_chars']} 字、{scored['n_tokens']} 个内容词。"
            f"ESG 命中 {scored['esg_count']} 次，数智化 {scored['digital_count']} 次，地缘 {scored['geopol_count']} 次。"
            "次数可以看，每千词和可读性不与正常章节比较。"
        )
    if row and row.get("page_start"):
        st.caption(f"章节大约在第 {row['page_start']}–{row['page_end']} 页。页码是否进入分母，以删除记录为准。")
    if row and not row.get("source_url"):
        st.caption("当前没有公告原文链接。服务器上的 source_path 不能用来回查申报。")
    picks = st.columns(3)
    choice = None
    if picks[0].button("查看 ESG 用词段落", key=f"ev-esg-{section_name}"):
        choice = "esg"
    if picks[1].button("查看数智化用词段落", key=f"ev-digital-{section_name}"):
        choice = "digital"
    if picks[2].button("查看地缘用词段落", key=f"ev-geopol-{section_name}"):
        choice = "geopol"
    if choice:
        st.session_state["focus_lex"] = choice
    focus = st.session_state.get("focus_lex")
    if focus:
        _render_evidence(text, (row or {}).get("section_raw") or text, focus, lang)
    spans = highlight_spans(text, _groups(lang, selected, extra_terms), lang)
    st.caption("绿色是 ESG 用词，蓝色是数智化用词，橙色是地缘用词。高亮的是清洗后正文。")
    st.markdown(_html(text, spans), unsafe_allow_html=True)
    counts = Counter(label for _a, _b, label in spans)
    if counts:
        st.write({LABELS.get(key, key): int(value) for key, value in counts.items()})


def _render_evidence(cleaned: str, raw: str, lexicon: str, lang: str) -> None:
    terms = topic_lexicons()[lang].get(lexicon, [])
    rows = term_decisions(cleaned, raw, terms, lang, geopol=lexicon == "geopol")
    st.markdown(f"**{LABELS.get(lexicon, lexicon)} 的命中与排除**")
    if not rows:
        st.info("当前词典在清洗后正文里没有命中。这只说明没有匹配到种子词。")
        return
    frame = pd.DataFrame(rows)
    counted = int((frame["status"] == "计入").sum())
    excluded = int((frame["status"] == "排除").sum())
    st.caption(f"计入 {counted} 处，排除 {excluded} 处。排除行不进入词频。")
    show = frame.rename(columns={"term": "词", "sentence": "原句", "page": "页码", "status": "结果", "reason": "原因"})
    show["页码"] = show["页码"].apply(lambda value: "" if value is None or (isinstance(value, float) and pd.isna(value)) else int(value))
    st.dataframe(show[["词", "原句", "页码", "结果", "原因"]], use_container_width=True, hide_index=True)


def _render_clean_compare(row, market: str, section_name: str) -> None:
    if not row:
        return
    raw = row.get("section_raw") or ""
    cleaned = row.get("section_text") or ""
    left, right = st.columns(2)
    left.markdown("**原始抽取预览**")
    left.text((raw or "没有切出这一章。")[:2500])
    right.markdown("**清洗后预览，只对这份计分**")
    right.text((cleaned or "清洗后不足 40 字，未计分。")[:2500])
    dropped = int(row.get("n_dropped_lines") or 0)
    st.caption(
        f"边界标题：{row.get('section_header') or '未识别'}。规则删除 {dropped} 行。"
        "下面只预览前 2500 字。删除数为 0 表示规则没有删行，不表示正文里一定没有表格碎片。"
    )
    log = row.get("clean_log") or []
    left_col, right_col = st.columns(2)
    if raw:
        left_col.download_button("下载本节原始抽取", raw.encode("utf-8"), file_name="section_raw.txt", key="dl-raw")
    if cleaned:
        right_col.download_button("下载清洗后正文", cleaned.encode("utf-8"), file_name="section_clean.txt", key="dl-clean")
    if log:
        st.download_button(
            "下载逐行删除记录",
            __import__("json").dumps(log, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="clean_log.json",
            key="dl-log",
        )
        preview = log[:40]
        if len(log) > len(preview):
            st.caption(f"删除记录共 {len(log)} 行，下面只显示前 40 行。完整记录在下载文件里。")
        log_frame = pd.DataFrame(preview).rename(columns={"page": "页码", "reason": "原因", "line": "原行"})
        st.dataframe(log_frame, use_container_width=True, height=220)
    prior = _prior_workspace_text(row)
    if prior:
        _show_diff(prior, cleaned, market, int(row["fiscal_year"]))
    elif row.get("text_path") and row.get("fiscal_year"):
        st.info(f"{int(row['fiscal_year'])} 年没有找到上一年同一章节。披露漂移为空，这不是趋势。")


def _render_drift(docs: list[dict], year: int, market: str, section: str) -> None:
    years = sorted(doc["fiscal_year"] for doc in docs)
    st.session_state["sample_years"] = years
    previous = next((doc for doc in docs if doc["fiscal_year"] == year - 1), None)
    current = next((doc for doc in docs if doc["fiscal_year"] == year), None)
    if current is None or previous is None:
        return
    before = _section_body(previous, section)
    after = _section_body(current, section)
    if not before.strip() or not after.strip():
        return
    _show_diff(before, after, market, year)


def _section_body(doc: dict, section: str) -> str:
    rows = parse_text(
        doc["text"],
        {
            "path": doc["filename"],
            "market": doc["market"],
            "ticker": doc["ticker"],
            "fiscal_year": doc["fiscal_year"],
            "report_type": doc["report_type"],
            "sections": [section],
        },
    )
    return rows[0].get("section_text") or ""


def _zh_topic_changes(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if "lexicon" in frame.columns:
        frame["lexicon"] = frame["lexicon"].map(lambda key: LABELS.get(key, key))
    return frame.rename(columns={"lexicon": "词表", "term": "词", "change": "变化"})


def _show_diff(before: str, after: str, market: str, year: int) -> None:
    diff = disclosure_diff(before, after, market)
    with st.expander(f"相对 {year - 1} 年的段落变化", expanded=True):
        if diff["topic_changes"]:
            st.write("主题词次数变化（本年 − 上年）")
            st.dataframe(_zh_topic_changes(diff["topic_changes"]), hide_index=True, use_container_width=True)
        if diff["added"]:
            st.markdown("**本年多出来的句子**")
            for sentence in diff["added"]:
                st.write(sentence)
        if diff["removed"]:
            st.markdown("**上年有、本年没有的句子**")
            for sentence in diff["removed"]:
                st.write(sentence)
        if diff["replaced"]:
            st.markdown("**改写最大的句子**")
            replaced = pd.DataFrame(diff["replaced"]).rename(columns={"before": "上年句子", "after": "本年句子"})
            st.dataframe(replaced, hide_index=True, use_container_width=True)
        if not any(diff[key] for key in ("added", "removed", "replaced", "topic_changes")):
            st.write("两年句子几乎相同。")


def _prior_workspace_text(row: dict) -> str:
    if not row or not row.get("fiscal_year") or not row.get("text_path"):
        return ""
    current = Path(str(row["text_path"]))
    previous = Path(str(current).replace(str(int(row["fiscal_year"])), str(int(row["fiscal_year"]) - 1)))
    if previous.exists() and previous != current:
        return previous.read_text(encoding="utf-8")
    return ""


def _render_lexicon_audit() -> None:
    from filingtext.audit import TOPIC_LABELS, load_audit_summary

    summary = load_audit_summary()
    st.markdown("**主题种子词的第一轮标注**")
    if not summary or not summary.get("classes"):
        st.caption("还没有标注结果。精确率和召回率只在人工标签齐了之后计算。")
        return
    rows = []
    for key, scored in summary["classes"].items():
        precision = scored.get("precision")
        recall = scored.get("recall")
        rows.append(
            {
                "词表": TOPIC_LABELS.get(key, scored.get("label") or key),
                "标注句数": scored.get("n_labeled"),
                "命中句": scored.get("n_hit"),
                "精确率": None if precision is None else f"{precision:.1%}",
                "召回率": None if recall is None else f"{recall:.1%}",
                "命中且相关": scored.get("tp"),
                "命中但无关": scored.get("fp"),
                "未命中但相关": scored.get("fn"),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(summary.get("note") or "")


def _render_section_diagnostics() -> None:
    path = ROOT / "data" / "validation" / "validation_report.csv"
    st.markdown("**验收集的章节切分**")
    if not path.exists():
        st.caption("没有 validation_report.csv，这里不显示切分成功率。")
        return
    from filingtext.diagnostics import section_success_table

    report = pd.read_csv(path)
    st.dataframe(section_success_table(report), hide_index=True, use_container_width=True)
    st.caption(
        "这是白酒、银行、医药各 5 家、2022–2024 年的验收集，按年份和交易所汇总，不是全 A 股。"
        "「风险已核对缺失」表示年报里没有这一节；「风险没切到」才是标题没有落到。"
        "全市场要用同一张表的脚本，对更大的解析结果再跑一遍。"
    )


def _render_method(anchors: list[dict], parsed: list[dict]) -> None:
    st.markdown(
        f"**词典版本** {DICTIONARY_VERSION}。"
        "三类主题仍是可编辑种子词。中文积极和消极词用姚加权、冯绪、王赞钧、纪荣嵘、张维（2021）"
        "《管理科学学报》的正式用语词表，按整词计入，不含股吧口语词。"
        "英文语气仍是种子词，不是 Loughran-McDonald 官方全表。"
    )
    _render_lexicon_audit()
    _render_section_diagnostics()
    st.markdown(
        "强度分母是清洗后的内容词数。命中删除规则的页码行和表格行不进入分词、分母和可读性指标。"
        "中文主题词用 jieba，长词优先，所以「碳排放权」不会再拆出「碳排放」。"
        "语气词按分词后的整词匹配，「风险管理」不会因为含有「风险」就多计一次。"
        "英文按词边界匹配，loss 不会算进 losses。"
        "不同词表可以同时命中同一个词，高亮时只标更长的那一次。"
    )
    st.markdown(
        "否定按分句判断：看命中词所在分句里、该词前面有没有否定。"
        "逗号会把句子切开，所以前半句的「没有」不会把后半句的「改善」翻成消极。"
        "顿号不断句。「没有改善」计为消极，不再计为积极。"
    )
    st.markdown(
        "语气净值 = (积极词数 − 消极词数) / 内容词数。大于 0 表示积极词更多。"
        "正式用语词表把「风险」「亏损」「下降」计为消极。不确定和诉讼仍用种子词，不进这个净值。"
    )
    st.markdown(
        "章节没有切出来时 found 为 0，宽表里对应格子是空的，不能把空值当成强度 0，也不能当成没有风险披露。"
        "内容词少于 40 的章节会标成 short_text，每千词和可读性留空，不与正常章节放在一起比较。"
        "risk 会再找 MD&A 里面的风险小节。标题没对上是 section_missing；核对年报后确认没有这一节是 section_absent。两种空值都不是强度 0。"
        "管理层讨论结束之后的「风险管理」「风险因素」是专章，不算风险小节。"
        "同一公司的风险标题换了，会标 title_shift。这只说明标题变了，不把该年从比较里拿掉。"
        "「法律制裁」「制裁合规」「提升制裁风险防范」这类合规表述不计入地缘词；「经济制裁」「出口管制」仍计入。"
        "正文变长或变短会同时改变分子和分母，每千词升降不一定是同一类话变多。"
        "跨年相似度有两个数：余弦是词频加权后的方向是否接近，Jaccard 是内容词集合重叠多少。"
        "披露漂移 = 1 − 余弦。新增句占比是本年句子里对不上上年的比例，风险节和讨论节都算。"
        "模板句、目录残留或篇幅变化都会让漂移变大，不能直接解读为风险上升或下降。"
        "语气净值和披露漂移是接到因子工作台的第 9、第 10 个因子：按 available_date 对到月末，做市值和行业中性化，最后 12 个月留作保留样本，并扣除佣金、点差、冲击和借券。"
        "方向事先写死，不用跑出来的数再改。当月不足 12 只股票，或有效月份不够训练窗时，只报告覆盖，不给收益结论。"
    )
    st.markdown(
        "中文类比可读性：0.4 ×（词数/句数 + 100 × 四字及以上词占比）。"
        "它不是英文 Gunning Fog，不能与英文 Fog 直接比高低。"
    )
    for rule in CLEANING_RULES:
        st.write(rule)
    if anchors:
        st.markdown("**章节边界**")
        st.dataframe(
            pd.DataFrame(anchors).rename(
                columns={
                    "section": "章节",
                    "priority": "优先级",
                    "title": "标题",
                    "start": "起始位置",
                    "content_start": "正文起点",
                    "header": "标题行",
                    "toc": "目录",
                    "hard": "硬边界",
                    "rank": "层级",
                    "toc_page": "目录页",
                    "match_method": "匹配方式",
                }
            ),
            use_container_width=True,
            height=240,
        )
    if parsed:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "章节": item["section"],
                        "是否切到": item["found"],
                        "起始页": item.get("page_start"),
                        "结束页": item.get("page_end"),
                        "删行数": item.get("n_dropped_lines"),
                        "内容词数": item.get("n_tokens"),
                        "质量标记": item.get("quality_flags"),
                        "章节状态": item.get("section_status"),
                        "可否比较": item.get("comparable"),
                    }
                    for item in parsed
                ]
            ),
            use_container_width=True,
        )


def _render_cloud(text: str, lang: str) -> None:
    stop = ZH_STOP if lang == "zh" else EN_STOP
    counts = Counter(tok for tok in tokenize(text, lang) if tok not in stop and len(tok) > 1)
    if not counts:
        st.info("没有足够的词。")
        return
    top = pd.DataFrame(counts.most_common(30), columns=["词", "次数"])
    font = _font()
    _barh(top, font)
    try:
        from wordcloud import WordCloud
    except ImportError:
        st.dataframe(top, use_container_width=True)
        return
    if lang == "zh" and font is None:
        st.warning("没有找到中文字体，词云无法显示汉字。")
        st.dataframe(top, use_container_width=True)
        return
    cloud = WordCloud(
        font_path=font,
        width=980,
        height=420,
        background_color="white",
        collocations=False,
        max_words=80,
        min_font_size=14,
    ).generate_from_frequencies({str(word): int(count) for word, count in counts.items()})
    st.image(cloud.to_image(), use_container_width=True)


def _barh(top: pd.DataFrame, font: str | None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties

    prop = FontProperties(fname=font) if font else None
    fig, axis = plt.subplots(figsize=(10, 6))
    plot = top.iloc[::-1]
    axis.barh(plot["词"], plot["次数"], color="#1d4e89")
    if prop is not None:
        for label in axis.get_yticklabels():
            label.set_fontproperties(prop)
        axis.set_xlabel("次数", fontproperties=prop)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def _render_job_status() -> None:
    from filingtext.jobs import latest_job, read_events, read_job

    job_id = st.session_state.get("ws_job")
    job = None
    if job_id:
        try:
            job = read_job(job_id)
        except (OSError, ValueError):
            job = None
    if job is None:
        job = latest_job()
    if not job:
        return
    status = {"queued": "排队", "running": "进行中", "done": "完成", "failed": "失败"}.get(job.get("status"), job.get("status"))
    st.caption(f"最近一次抓取：{status}")
    if job.get("error"):
        st.error(str(job["error"]))
    summary = job.get("summary") or {}
    if job.get("status") == "done" and summary:
        st.session_state["ws_message"] = (
            f"完成：下载 {summary.get('downloaded', 0)} 份，"
            f"有效章节 {summary.get('n_found')} 个，公司 {summary.get('n_firms')} 家。"
            "失败的文件可再次提交，已成功的会保留。"
        )
    events = read_events(job["id"])
    if events:
        st.dataframe(
            pd.DataFrame(events).rename(columns={"stage": "阶段", "detail": "说明", "state": "状态"}),
            hide_index=True,
            use_container_width=True,
            height=180,
        )
    if job.get("status") in {"queued", "running"} and st.button("刷新进度"):
        st.rerun()


def _workspace_page() -> tuple[str, str, str, dict]:
    st.subheader("我的面板")
    st.caption("代码和年份会放进后台任务再解析。上传的文件会进入同一张表。样本案例的数字不会被这里改掉。任务状态写在本机，刷新页面还能看到。单次网页任务超过 24 份需要确认，超过 200 份改用 scripts/build_factor_panel.py。已下载过的原文按 SHA1 缓存，同一地址不再重复请求。")
    action = st.radio("加入文件", ["按代码和年份抓取", "上传已有文件"], horizontal=True)
    if action == "按代码和年份抓取":
        _fetch_form()
    else:
        _upload_form()
    if st.button("清空我的面板"):
        from filingtext.workspace import reset_workspace

        reset_workspace()
        st.session_state.pop("ws_message", None)
        st.session_state.pop("ws_job", None)
        st.rerun()
    _render_job_status()
    message = st.session_state.get("ws_message")
    if message:
        st.info(message)
    events = st.session_state.get("ws_events") or []
    if events:
        st.dataframe(
            pd.DataFrame(events).rename(columns={"stage": "阶段", "detail": "说明", "state": "状态"}),
            hide_index=True,
            use_container_width=True,
            height=180,
        )
    return _workspace_selection()


def _fetch_form() -> None:
    market = st.radio("市场", ["A 股 / 巨潮", "美股 / EDGAR"], horizontal=True, key="fetch_market")
    codes = st.text_input("代码", placeholder="000001,600519 或 AAPL,MSFT")
    left, right = st.columns(2)
    start = int(left.number_input("起始年", min_value=2005, max_value=2026, value=2023, step=1))
    end = int(right.number_input("结束年", min_value=2005, max_value=2026, value=2023, step=1))
    contact = ""
    forms = ["10-K"]
    if market.startswith("美股"):
        contact = st.text_input("EDGAR 联系邮箱", placeholder="name@university.edu")
        choice = st.selectbox("表格", ["10-K", "10-Q"])
        forms = [choice]
    st.checkbox("下载超过 24 份时，我确认这次的数量", key="confirm_large")
    if st.button("抓取并生成面板"):
        from filingtext.jobs import create_job, latest_job, spawn
        from filingtext.workspace import LARGE_BATCH, parse_codes

        chosen = parse_codes(codes)
        forms_n = 1
        estimate = len(chosen) * (end - start + 1) * forms_n
        running = latest_job()
        if running and running.get("status") in {"queued", "running"}:
            st.warning("已有抓取任务在跑。等它结束，或点下面的刷新查看进度。")
            return
        if estimate > LARGE_BATCH and not st.session_state.get("confirm_large"):
            st.warning(f"这次大约 {estimate} 份。勾选确认后再提交。")
            return
        try:
            job_id = create_job(
                {
                    "market": "US" if market.startswith("美股") else "CN",
                    "codes": codes,
                    "start": start,
                    "end": end,
                    "forms": forms,
                    "confirm_large": bool(st.session_state.get("confirm_large")),
                }
            )
            spawn(job_id, edgar_contact=contact)
            st.session_state["ws_job"] = job_id
            st.session_state["ws_message"] = "抓取已转到后台。进度写在本机，刷新后还在。"
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _upload_form() -> None:
    uploads = st.file_uploader(
        "PDF、HTML 或 TXT，可多选",
        type=["pdf", "txt", "htm", "html"],
        accept_multiple_files=True,
    )
    if st.button("解析并加入面板"):
        from filingtext.workspace import refresh_workspace, save_upload

        if not uploads:
            st.warning("请先选择文件。文件名最好是 000001_2023_annual.pdf 这种形式。")
            return
        try:
            for item in uploads:
                save_upload(item.name, item.getvalue())
            with st.spinner("正在解析并重算整张面板。"):
                result = refresh_workspace()
            summary = result["summary"]
            st.session_state["ws_message"] = (
                f"已加入 {len(uploads)} 个文件。有效章节 {summary['n_found']} 个，公司 {summary['n_firms']} 家。"
            )
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _workspace_selection() -> tuple[str, str, str, dict]:
    parquet = WORKSPACE_OUT / "panel.parquet"
    if not parquet.exists():
        return "", "CN", "annual", {}
    frame = pd.read_parquet(parquet)
    found = frame[frame["found"] == 1]
    if found.empty:
        st.warning("文件已经解析，但没有切出足够长的章节。可以到「章节诊断」查看标题是否被识别。")
        return "", "CN", "annual", {}
    found = found.sort_values(["ticker", "fiscal_year", "section"])
    labels = [
        f"{row.ticker} {int(row.fiscal_year)} {row.section}"
        for row in found.itertuples()
    ]
    choice = st.selectbox("查看已入库章节", labels)
    row = found.iloc[labels.index(choice)]
    source = Path(str(row.get("source_path") or ""))
    if source.exists():
        text = _read_cached(str(source), source.stat().st_mtime)
    else:
        saved = Path(str(row.get("text_path") or ""))
        text = saved.read_text(encoding="utf-8") if saved.exists() else ""
    year = row.get("fiscal_year")
    meta = {
        "path": str(source) if source.exists() else "upload.txt",
        "market": str(row["market"]),
        "ticker": str(row.get("ticker") or ""),
        "firm_name": str(row.get("firm_name") or ""),
        "fiscal_year": int(year) if pd.notna(year) else None,
        "report_type": str(row.get("report_type") or ""),
        "filing_date": str(row.get("filing_date") or ""),
        "source_url": str(row.get("source_url") or ""),
        "exchange": str(row.get("exchange") or ""),
        "fetched_at": str(row.get("fetched_at") or ""),
        "data_version": str(row.get("data_version") or ""),
        "cik": str(row.get("cik") or ""),
    }
    return text, str(row["market"]), str(row.get("form") or "annual"), meta


@st.cache_data(show_spinner=False)
def _read_cached(path_str: str, _mtime: float) -> str:
    from filingtext.extract import read_filing

    return read_filing(path_str)


def _render_memory_panel(frame: pd.DataFrame) -> None:
    found = frame[frame["found"] == 1] if "found" in frame.columns else frame
    show = found
    if "section_status" in frame.columns:
        absent = frame[frame["section_status"] == "absent"]
        if not absent.empty:
            show = pd.concat([found, absent], ignore_index=True)
    mda = found[found["section"] == "mda"] if "section" in found.columns else found
    chart_mda = _comparable_rows(mda)
    if not chart_mda.empty and chart_mda["fiscal_year"].nunique() >= 2:
        from ui.charts import render_freq_tone_trends

        render_freq_tone_trends(chart_mda)
        if chart_mda["disclosure_drift"].notna().any() and chart_mda["fiscal_year"].nunique() >= 2:
            st.caption("披露漂移")
            from ui.charts import render_drift_trend

            render_drift_trend(chart_mda)
        if len(chart_mda) < len(mda):
            st.caption("文本过短或边界可疑的年份没有画进图里，避免和正常章节比每千词。")
        if mda["disclosure_drift"].isna().any():
            st.caption("披露漂移为空的年份没有上一年，不能把那一年读成变化。")
    if "section_status" in frame.columns and (frame["section_status"] == "absent").any():
        st.caption("标成 absent 的行已核对，年报里没有这一节。它们不进入图，每千词留空，不是强度 0。")
    st.dataframe(show, use_container_width=True, height=280)


def _render_panel(out_dir: Path = OUTPUT_DIR, fallback: pd.DataFrame | None = None) -> None:
    parquet = out_dir / "panel.parquet"
    wide_path = out_dir / "panel_wide.parquet"
    trend_path = out_dir / "trend_by_year.csv"
    figure = out_dir / "trends.png"
    if not parquet.exists():
        if fallback is not None and not fallback.empty:
            _render_memory_panel(fallback)
            return
        st.info("我的面板还没有文件。左侧选「样本案例」可以直接看多年结果。")
        return
    if out_dir == OUTPUT_DIR:
        st.caption("下面是同一批合成样本的公司-年度面板，和上面的案例用的是同一套数字。")
    else:
        st.caption("长表是一章一行。宽表是一行一个公司—年度。因子表主键 ticker、fiscal_year、fiscal_quarter、available_date；available_date 为公告日 T+1。")
    frame = pd.read_parquet(parquet)
    st.dataframe(frame, use_container_width=True, height=280)
    _download_row(out_dir)
    if wide_path.exists():
        st.markdown("**公司—年度宽表**")
        wide = pd.read_parquet(wide_path)
        st.dataframe(wide, use_container_width=True, height=240)
    ready_path = out_dir / "regression_readiness.csv"
    ready = pd.read_csv(ready_path, dtype=str) if ready_path.exists() else regression_readiness(frame)
    st.markdown("**能不能进回归**")
    st.caption(
        "主键与因子表相同：ticker、fiscal_year、fiscal_quarter、available_date。"
        "risk_regression_ready 为 1，才表示这年的风险节可以和其他年份比每千词。"
        "核对后没有这一节、没切到、过短、章外风险管理都是 0。换标题只记在质量标记里。"
    )
    st.dataframe(ready, use_container_width=True, height=240)
    if trend_path.exists():
        trend = pd.read_csv(trend_path)
        from ui.charts import METRIC_LABELS, render_market_trend

        metric = st.selectbox("时序指标", list(METRIC_LABELS), format_func=lambda key: METRIC_LABELS[key])
        render_market_trend(trend, metric)
    if figure.exists():
        st.image(str(figure), caption="样本均值的时序")


def _download_row(out_dir: Path) -> None:
    columns = st.columns(3)
    files = [
        ("长表 CSV", out_dir / "panel.parquet", "panel.csv", "csv"),
        ("长表 dta", out_dir / "panel.dta", "panel.dta", "dta"),
        ("宽表 CSV", out_dir / "panel_wide.parquet", "panel_wide.csv", "csv"),
        ("宽表 dta", out_dir / "panel_wide.dta", "panel_wide.dta", "dta"),
        ("因子表 CSV", out_dir / "panel_factor.parquet", "panel_factor.csv", "csv"),
        ("因子表 dta", out_dir / "panel_factor.dta", "panel_factor.dta", "dta"),
        ("回归对照", out_dir / "regression_readiness.csv", "regression_readiness.csv", "file"),
    ]
    for index, (label, path, name, kind) in enumerate(files):
        column = columns[index % 3]
        if not path.exists():
            continue
        if kind == "csv":
            data = pd.read_parquet(path).to_csv(index=False).encode("utf-8-sig")
            mime = "text/csv"
        elif kind == "file":
            data = path.read_bytes()
            mime = "text/csv"
        else:
            data = path.read_bytes()
            mime = "application/octet-stream"
        column.download_button(label, data, file_name=name, mime=mime, key=f"dl-{out_dir.name}-{name}")
    st.caption("因子表也可以用本机只读接口取出：`python -m filingtext.panel_api --root` 指向这个输出目录。接口只提供因子表、回归对照和检验摘要，不提供章节正文。当前这台 Streamlit 没有单独的 agent 开关。")
    _download_evidence_zip(out_dir)


def _download_evidence_zip(out_dir: Path) -> None:
    import io
    import zipfile

    names = [
        "panel.parquet",
        "panel_factor.parquet",
        "panel_factor.dta",
    ]
    runs = sorted(out_dir.glob("run_*.json"))
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            path = out_dir / name
            if path.exists():
                archive.write(path, arcname=name)
        if runs:
            archive.write(runs[-1], arcname=runs[-1].name)
    if payload.tell() == 0:
        return
    st.download_button(
        "下载本次运行证据包",
        payload.getvalue(),
        file_name="filingtext_evidence.zip",
        mime="application/zip",
        key=f"dl-zip-{out_dir.name}",
    )


def _html(text: str, spans: list[tuple[int, int, str]]) -> str:
    import html

    parts = []
    last = 0
    for start, end, label in spans:
        parts.append(html.escape(text[last:start]))
        color = COLORS.get(label, "#eee")
        parts.append(
            f"<mark style='background:{color};padding:0 2px' title='{html.escape(label)}'>"
            f"{html.escape(text[start:end])}</mark>"
        )
        last = end
    parts.append(html.escape(text[last:]))
    body = "".join(parts)
    return (
        "<div style='max-height:480px;overflow:auto;line-height:1.75;white-space:pre-wrap;"
        "border:1px solid #e5e7eb;border-radius:8px;padding:12px'>"
        f"{body}</div>"
    )


def _split_terms(raw: str, lang: str) -> list[str]:
    chunks = raw.replace("，", ",").replace("、", ",").replace("\n", ",").split(",")
    terms = []
    for chunk in chunks:
        term = chunk.strip()
        if term:
            terms.append(term.lower() if lang == "en" else term)
    return terms


def _row_comparable(row, scored: dict) -> bool:
    if row is None:
        return (scored.get("n_tokens") or 0) >= 40
    if "comparable" in row:
        return bool(int(row.get("comparable") or 0))
    return "short_text" not in str(row.get("quality_flags") or "")


def _quality_message(flags: str) -> str:
    labels = {
        "short_text": "文本过短，每千词、语气比率和可读性不与正常章节比较",
        "boundary_suspect": "章节边界可疑，后面的标题可能被收了进来",
        "location_missing": "这一节没有页码，句子暂时不能回到原页",
        "section_absent": "已确认年报里没有这一节。空值不是强度 0，也不是没切到",
        "section_missing": "这一节没有切出来。空值不是强度 0",
        "title_shift": "这年的风险标题和该公司其他年份不一样。先看标题，再读词数变化",
    }
    parts = [labels.get(flag, flag) for flag in flags.split("|") if flag]
    return "质量状态：" + "；".join(parts) + "。"


def _comparable_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or "comparable" not in frame.columns:
        return frame
    return frame[pd.to_numeric(frame["comparable"], errors="coerce").fillna(1).astype(int) == 1]


def _fmt(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    return f"{float(value):.3f}"


def _font() -> str | None:
    bundled = Path(__file__).resolve().parent / "fonts" / "SourceHanSansCN-Regular.otf"
    if bundled.exists():
        return str(bundled)
    for path in (
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simsun.ttc",
    ):
        if Path(path).exists():
            return path
    return None


if __name__ == "__main__":
    main()
