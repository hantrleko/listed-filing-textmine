"""交互式词典验证、章节诊断和面板时序。"""

from __future__ import annotations

import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

from filingtext.clean import normalize
from filingtext.config import OUTPUT_DIR, WORKSPACE_OUT
from filingtext.extract import extract_pdf, html_to_text
from filingtext.features import EN_STOP, ZH_STOP, apply_corpus, highlight_spans, score_document, tokenize
from filingtext.lexicon import tone_lexicons, topic_lexicons
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


def main() -> None:
    st.set_page_config(page_title="年报文本特征引擎", layout="wide")
    st.title("上市公司文本特征引擎")
    st.caption("章节切分、词典命中高亮、词云和面板时序。语气词是可编辑种子词，不是 Loughran-McDonald 官方全表。")

    mode = st.sidebar.radio("开始", ["样本案例", "我的面板"], horizontal=True)
    market = "CN"
    form = "annual"
    sample_frame = None
    sample_name = ""
    panel_dir = OUTPUT_DIR
    if mode == "样本案例":
        case = st.sidebar.radio("案例", ["示例银行", "Northwind 10-K"])
        ticker = "000001" if case == "示例银行" else "NWND"
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
        raw, market, form = _workspace_page()

    lang = "zh" if market == "CN" else "en"
    selected = st.sidebar.multiselect(
        "高亮词表",
        list(LABELS),
        default=["esg", "digital", "geopol"],
        format_func=lambda key: LABELS[key],
    )
    extra_terms = _split_terms(st.sidebar.text_area("临时词", height=90, placeholder="一行一个，或用逗号分隔"), lang)

    if mode == "样本案例":
        _render_case_intro(sample_name, market, sample_frame)
    view, section_name, anchors, parsed = _prepare(raw, market, form)
    if mode == "样本案例" and raw and view:
        for note in _trap_notes(raw, view, market, section_name):
            st.success(note)

    tabs = st.tabs(["词典高亮", "词云", "章节诊断", "面板时序"])
    with tabs[0]:
        if view:
            st.caption("绿色是 ESG / 绿色转型，蓝色是数智化 / AI，橙色是地缘风险。")
            _render_highlight(view, market, lang, section_name, selected, extra_terms)
        else:
            st.info("左侧可以看样本案例。做自己的表时，用「我的面板」填写代码和年份，或上传文件。")
    with tabs[1]:
        if view:
            _render_cloud(view, lang)
        else:
            st.info("先提供一段文本。")
    with tabs[2]:
        if raw:
            st.dataframe(pd.DataFrame(anchors), use_container_width=True, height=320)
            st.dataframe(
                pd.DataFrame(
                    [
                        {"section": row["section"], "found": row["found"], "n_chars": row["n_chars"], "n_tokens": row["n_tokens"]}
                        for row in parsed
                    ]
                ),
                use_container_width=True,
            )
        else:
            st.info("先提供一段文本。")
    with tabs[3]:
        _render_panel(panel_dir)


def _case_frame(ticker: str) -> pd.DataFrame:
    panel = OUTPUT_DIR / "panel.parquet"
    if panel.exists():
        frame = pd.read_parquet(panel)
        subset = frame[frame["ticker"].astype(str) == ticker].copy()
        if not subset.empty:
            return subset
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
                    "sections": ["mda", "risk"] if doc["market"] == "US" else ["mda"],
                },
            )
        )
    apply_corpus(rows)
    for row in rows:
        row.pop("section_text", None)
    return pd.DataFrame(rows)


def _render_case_intro(name: str, market: str, frame: pd.DataFrame) -> None:
    st.subheader(name)
    st.caption("合成文本，用来看切分和指标。不是真实公司的披露。")
    if market == "CN":
        st.markdown(
            "目录里的点线和页码留在正文外面。"
            "单独一行的「社会责任」不会把管理层讨论截断。"
            "第四节公司治理整段不进入 MD&A。"
        )
    else:
        st.markdown(
            "目录里带页码的 Item 行会丢掉。"
            "10-K 的风险因素是 Item 1A，MD&A 是 Item 7。"
            "Item 8 的报表句留在这两段外面。在「查看范围」里可以改看 risk。"
        )
    if frame is None or frame.empty:
        return
    show = frame.sort_values(["fiscal_year", "section"]).copy()
    if "found" in show.columns:
        show = show[show["found"] == 1]
    columns = {
        "fiscal_year": "年份",
        "section": "章节",
        "digital_per_k": "数智化/千词",
        "esg_per_k": "ESG/千词",
        "geopol_per_k": "地缘/千词",
        "tone_net": "语气净值",
        "disclosure_drift": "披露漂移",
        "fog_index": "Fog",
    }
    table = show[list(columns)].rename(columns=columns)
    for column in table.columns:
        if column in {"年份", "章节"}:
            continue
        table[column] = pd.to_numeric(table[column], errors="coerce").round(3)
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.write(_describe_case(show))
    st.caption(
        "每千词 = 命中次数 / 内容词数 × 1000。"
        "语气净值 = (积极词 − 消极词) / 内容词数，大于 0 表示积极词更多。"
        "披露漂移 = 1 − 与上一年同一章节的相似度，第一年为空。"
        "Fog 越高，文本越难读。"
    )


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
        pieces.append(f"{label}由 {_fmt(first[column])} 到 {_fmt(last[column])}")
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


def _prepare(raw: str, market: str, form: str):
    if not raw:
        return "", "", [], []
    form_arg = None if market == "CN" else form
    sections = split_sections(raw, market, form=form_arg)
    names = ["全文"] + list(sections)
    default_index = names.index("mda") if "mda" in names else 0
    choice = st.selectbox("查看范围", names, index=default_index)
    parsed = parse_text(
        raw,
        {
            "path": "upload.txt",
            "market": market,
            "report_type": form,
            "sections": list(sections) or None,
        },
    )
    anchors = diagnose_anchors(raw, market, form=form_arg)
    if choice == "全文":
        return raw, "全文", anchors, parsed
    cleaned = next((row.get("section_text") for row in parsed if row["section"] == choice and row.get("section_text")), "")
    return cleaned or sections[choice].text, choice, anchors, parsed


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


def _render_highlight(text, market, lang, section_name, selected, extra_terms) -> None:
    scored = score_document(text, market)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("章节", section_name)
    c2.metric("内容词", f"{scored['n_tokens']}")
    c3.metric("Fog", _fmt(scored["fog_index"]))
    c4.metric("语气净值", _fmt(scored["tone_net"]))
    c5, c6, c7 = st.columns(3)
    c5.metric("ESG 每千词", _fmt(scored["esg_per_k"]))
    c6.metric("数智化每千词", _fmt(scored["digital_per_k"]))
    c7.metric("地缘每千词", _fmt(scored["geopol_per_k"]))
    spans = highlight_spans(text, _groups(lang, selected, extra_terms), lang)
    st.markdown(_html(text, spans), unsafe_allow_html=True)
    counts = Counter(label for _a, _b, label in spans)
    if counts:
        st.write({LABELS.get(key, key): int(value) for key, value in counts.items()})


def _render_cloud(text: str, lang: str) -> None:
    stop = ZH_STOP if lang == "zh" else EN_STOP
    counts = Counter(tok for tok in tokenize(text, lang) if tok not in stop and len(tok) > 1)
    if not counts:
        st.info("没有足够的词。")
        return
    top = pd.DataFrame(counts.most_common(30), columns=["词", "次数"])
    st.bar_chart(top.set_index("词"))
    try:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt
    except ImportError:
        st.dataframe(top, use_container_width=True)
        return
    cloud = WordCloud(
        font_path=_font(),
        width=980,
        height=420,
        background_color="white",
        collocations=False,
    ).generate_from_frequencies(dict(counts))
    fig, axis = plt.subplots(figsize=(10, 4.4))
    axis.imshow(cloud, interpolation="bilinear")
    axis.axis("off")
    st.pyplot(fig)
    plt.close(fig)


def _workspace_page() -> tuple[str, str, str]:
    st.subheader("我的面板")
    st.caption("代码和年份会下载原文再解析。上传的文件会进入同一张表。样本案例的数字不会被这里改掉。单次最多下载 8 份。")
    action = st.radio("加入文件", ["按代码和年份抓取", "上传已有文件"], horizontal=True)
    if action == "按代码和年份抓取":
        _fetch_form()
    else:
        _upload_form()
    if st.button("清空我的面板"):
        from filingtext.workspace import reset_workspace

        reset_workspace()
        st.session_state.pop("ws_message", None)
        st.rerun()
    message = st.session_state.get("ws_message")
    if message:
        st.info(message)
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
    if st.button("抓取并生成面板"):
        from filingtext.workspace import build_from_codes

        try:
            with st.spinner("正在下载并解析。年报 PDF 会比 HTML 慢。"):
                result = build_from_codes(
                    "US" if market.startswith("美股") else "CN",
                    codes,
                    start,
                    end,
                    edgar_contact=contact,
                    forms=forms,
                )
            summary = result["summary"]
            st.session_state["ws_message"] = (
                f"完成：下载 {len(result.get('downloaded') or [])} 份，"
                f"有效章节 {summary['n_found']} 个，公司 {summary['n_firms']} 家。"
            )
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


def _workspace_selection() -> tuple[str, str, str]:
    parquet = WORKSPACE_OUT / "panel.parquet"
    if not parquet.exists():
        return "", "CN", "annual"
    frame = pd.read_parquet(parquet)
    found = frame[frame["found"] == 1]
    if found.empty:
        st.warning("文件已经解析，但没有切出足够长的章节。可以到「章节诊断」查看标题是否被识别。")
        return "", "CN", "annual"
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
    return text, str(row["market"]), str(row.get("form") or "annual")


@st.cache_data(show_spinner=False)
def _read_cached(path_str: str, _mtime: float) -> str:
    from filingtext.extract import read_filing

    return read_filing(path_str)


def _render_panel(out_dir: Path = OUTPUT_DIR) -> None:
    parquet = out_dir / "panel.parquet"
    wide_path = out_dir / "panel_wide.parquet"
    trend_path = out_dir / "trend_by_year.csv"
    figure = out_dir / "trends.png"
    if not parquet.exists():
        st.info("还没有面板。样本案例来自 python -m filingtext.demo；自己的文件在「我的面板」生成。")
        return
    if out_dir == OUTPUT_DIR:
        st.caption("下面是同一批合成样本的公司-年度面板，和上面的案例用的是同一套数字。")
    else:
        st.caption("长表是一章一行。宽表是一行一个公司—年度，MD&A 和风险因素分成两列，A 股 stkcd 保留前导零。")
    frame = pd.read_parquet(parquet)
    st.dataframe(frame, use_container_width=True, height=280)
    _download_row(out_dir)
    if wide_path.exists():
        st.markdown("**公司—年度宽表**")
        wide = pd.read_parquet(wide_path)
        st.dataframe(wide, use_container_width=True, height=240)
    if trend_path.exists():
        trend = pd.read_csv(trend_path)
        metric = st.selectbox(
            "时序指标",
            ["digital_per_k", "esg_per_k", "geopol_per_k", "tone_net", "fog_index", "disclosure_drift"],
        )
        chart = trend.pivot(index="fiscal_year", columns="market", values=metric)
        st.line_chart(chart)
    if figure.exists():
        st.image(str(figure), caption="样本均值的时序")


def _download_row(out_dir: Path) -> None:
    columns = st.columns(4)
    files = [
        ("长表 CSV", out_dir / "panel.parquet", "panel.csv", "csv"),
        ("长表 dta", out_dir / "panel.dta", "panel.dta", "dta"),
        ("宽表 CSV", out_dir / "panel_wide.parquet", "panel_wide.csv", "csv"),
        ("宽表 dta", out_dir / "panel_wide.dta", "panel_wide.dta", "dta"),
    ]
    for column, (label, path, name, kind) in zip(columns, files):
        if not path.exists():
            continue
        if kind == "csv":
            data = pd.read_parquet(path).to_csv(index=False).encode("utf-8-sig")
            mime = "text/csv"
        else:
            data = path.read_bytes()
            mime = "application/octet-stream"
        column.download_button(label, data, file_name=name, mime=mime, key=f"dl-{out_dir.name}-{name}")


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


def _fmt(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    return f"{float(value):.3f}"


def _font() -> str | None:
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
