"""巨潮资讯年报与 SEC EDGAR 10-K/10-Q 抓取。

EDGAR 要求调用方设置 EDGAR_USER_AGENT，且其中包含联系邮箱。
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from filingtext.config import (
    CNINFO_QUERY_URL,
    CNINFO_SEARCH_URL,
    CNINFO_STATIC,
    SEC_ARCHIVES,
    SEC_SUBMISSIONS,
    SEC_TICKERS,
    edgar_user_agent,
)


def cninfo_column(code: str) -> str:
    code = code.strip()
    if code.startswith("6"):
        return "sse"
    if code.startswith(("4", "8", "92")):
        return "bj"
    return "szse"


def is_full_annual_title(title: str) -> bool:
    if any(bad in title for bad in ("摘要", "英文", "取消", "更正公告", "修订说明")):
        return False
    return "年度报告" in title


def cninfo_pdf_url(adjunct_url: str) -> str:
    return CNINFO_STATIC + adjunct_url.lstrip("/")


def edgar_filing_url(cik: str, accession: str, filename: str) -> str:
    return SEC_ARCHIVES.format(
        cik=str(int(str(cik).lstrip("0") or "0")),
        accession=accession.replace("-", ""),
        filename=filename,
    )


def _cninfo_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "listed-filing-textmine research",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "http://www.cninfo.com.cn",
            "Referer": "http://www.cninfo.com.cn/",
        }
    )
    return session


def _edgar_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": edgar_user_agent(),
            "Accept": "application/json, text/html, */*",
        }
    )
    return session


def search_cninfo_org(code: str, session: requests.Session | None = None) -> dict:
    session = session or _cninfo_session()
    response = session.post(
        CNINFO_SEARCH_URL,
        data={"keyWord": code, "maxNum": "10"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload if isinstance(payload, list) else payload.get("keyBoardList") or []
    target = code.zfill(6) if code.isdigit() else code
    for row in rows:
        if str(row.get("code", "")).zfill(6) == target or str(row.get("code")) == code:
            return row
    if rows:
        return rows[0]
    raise LookupError(f"巨潮资讯未找到证券代码 {code}")


def annual_announcement_window(start: int, end: int) -> str:
    """A 股年报在财政年度的次年 1–4 月披露，查询用公告日。"""
    return f"{int(start) + 1}-01-01~{int(end) + 1}-08-31"


def list_cninfo_annual(
    code: str,
    org_id: str,
    start: int,
    end: int,
    session: requests.Session | None = None,
) -> list[dict]:
    session = session or _cninfo_session()
    found: list[dict] = []
    page = 1
    while page <= 20:
        payload = {
            "pageNum": str(page),
            "pageSize": "30",
            "column": cninfo_column(code),
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{code},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": "category_ndbg_szsh;",
            "trade": "",
            "seDate": annual_announcement_window(start, end),
            "sortName": "announcementTime",
            "sortType": "desc",
            "isHLtitle": "true",
        }
        response = session.post(CNINFO_QUERY_URL, data=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        anns = data.get("announcements") or []
        found.extend(anns)
        if len(anns) < 30 or not data.get("hasMore", False):
            break
        page += 1
        time.sleep(0.4)
    return found


def _emit(on_event, stage: str, detail: str, state: str = "run") -> None:
    if on_event:
        on_event({"stage": stage, "detail": detail, "state": state})


def download_cninfo(
    codes: list[str],
    start: int,
    end: int,
    out_dir: str | Path,
    on_event=None,
) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    session = _cninfo_session()
    saved: list[Path] = []
    for code in codes:
        code = code.strip()
        if not code:
            continue
        _emit(on_event, "查找公告", code)
        try:
            org = search_cninfo_org(code, session)
            org_id = org.get("orgId") or ""
            name = org.get("zwjc") or ""
            anns = list_cninfo_annual(code, org_id, start, end, session)
        except Exception as exc:
            _emit(on_event, "查找公告", f"{code}：{exc}", "fail")
            continue
        _emit(on_event, "查找公告", f"{code} {name}，{len(anns)} 条", "ok")
        for ann in anns:
            title = str(ann.get("announcementTitle") or "")
            if not is_full_annual_title(title):
                continue
            year = _year_from_title(title) or _year_from_ms(ann.get("announcementTime"))
            if year is None or year < start or year > end:
                continue
            adjunct = ann.get("adjunctUrl") or ""
            if not adjunct:
                continue
            dest = out / f"{code}_{year}_annual.pdf"
            _emit(on_event, "下载", dest.name)
            try:
                _stream(session, cninfo_pdf_url(adjunct), dest)
            except Exception as exc:
                _emit(on_event, "下载", f"{dest.name}：{exc}", "fail")
                continue
            saved.append(dest)
            _emit(on_event, "下载", dest.name, "ok")
            _append_manifest(
                out,
                {
                    "path": dest.name,
                    "market": "CN",
                    "ticker": code,
                    "firm_name": name,
                    "fiscal_year": year,
                    "report_type": "annual",
                },
            )
            time.sleep(0.5)
    return saved


def lookup_cik(ticker: str, session: requests.Session | None = None) -> str:
    session = session or _edgar_session()
    response = session.get(SEC_TICKERS, timeout=30)
    response.raise_for_status()
    data = response.json()
    rows = data.values() if isinstance(data, dict) else data
    for row in rows:
        if str(row.get("ticker", "")).upper() == ticker.upper():
            return str(row["cik_str"]).zfill(10)
    raise LookupError(f"SEC 未找到 ticker {ticker}")


def download_edgar(
    tickers: list[str],
    ciks: list[str],
    start: int,
    end: int,
    out_dir: str | Path,
    forms: list[str] | None = None,
    include_amendments: bool = False,
    on_event=None,
) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    session = _edgar_session()
    want = {f.upper() for f in (forms or ["10-K"])}
    saved: list[Path] = []
    pairs: list[tuple[str, str]] = []
    for cik in ciks:
        if cik.strip():
            pairs.append(("", str(cik).zfill(10)))
    for ticker in tickers:
        if not ticker.strip():
            continue
        _emit(on_event, "查找公告", ticker.strip().upper())
        try:
            pairs.append((ticker.strip().upper(), lookup_cik(ticker.strip(), session)))
            _emit(on_event, "查找公告", ticker.strip().upper(), "ok")
        except Exception as exc:
            _emit(on_event, "查找公告", f"{ticker}：{exc}", "fail")
        time.sleep(0.2)
    for ticker, cik in pairs:
        url = SEC_SUBMISSIONS.format(cik=cik)
        response = session.get(url, timeout=60)
        response.raise_for_status()
        payload = response.json()
        firm = payload.get("name") or ticker or cik
        recent = payload["filings"]["recent"]
        for idx, form in enumerate(recent["form"]):
            form = str(form).upper()
            if form not in want:
                continue
            if form.endswith("/A") and not include_amendments:
                continue
            report_date = recent["reportDate"][idx] or recent["filingDate"][idx]
            year = int(str(report_date)[:4])
            if year < start or year > end:
                continue
            accession = recent["accessionNumber"][idx]
            primary = recent["primaryDocument"][idx]
            file_url = edgar_filing_url(cik, accession, primary)
            ext = Path(primary).suffix.lower() or ".htm"
            label = ticker or cik
            kind = form.replace("-", "").replace("/", "")
            dest = out / f"{label}_{year}_{kind}{ext}"
            _emit(on_event, "下载", dest.name)
            try:
                _stream(session, file_url, dest)
            except Exception as exc:
                _emit(on_event, "下载", f"{dest.name}：{exc}", "fail")
                continue
            saved.append(dest)
            _emit(on_event, "下载", dest.name, "ok")
            _append_manifest(
                out,
                {
                    "path": dest.name,
                    "market": "US",
                    "ticker": label,
                    "firm_name": firm,
                    "fiscal_year": year,
                    "report_type": form,
                },
            )
            time.sleep(0.25)
    return saved


def _year_from_title(title: str) -> int | None:
    import re

    matched = re.search(r"(20\d{2}|19\d{2})", title)
    return int(matched.group(1)) if matched else None


def _year_from_ms(value: object) -> int | None:
    if value is None:
        return None
    try:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).year
    except (TypeError, ValueError, OSError):
        return None


def _stream(session: requests.Session, url: str, dest: Path) -> None:
    with session.get(url, timeout=90, stream=True) as response:
        response.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    handle.write(chunk)


def _append_manifest(out: Path, row: dict) -> None:
    import csv

    path = out / "manifest.csv"
    fields = ["path", "market", "ticker", "firm_name", "fiscal_year", "report_type"]
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
