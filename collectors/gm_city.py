"""광명시청 고시공고·공지사항 게시판.

- 목록 1페이지(최근 50건)를 받아 제목 키워드로 거른다 (페이지가 커서 키워드별 검색 대신)
- 상세는 키워드에 걸리고 최근에 올라온 글만
- 접수기간은 "접수기간/신청기간"이 명시된 줄에서만 읽는다
  (예: "모집공고일 : 6. 29. ~ 7. 3."처럼 이름과 내용이 다른 줄은 추측하지 않음)
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta

from bs4 import BeautifulSoup

from collectors.base import BaseCollector, parse_date
from models import Notice
from store import today_kst

log = logging.getLogger(__name__)

BASE = "https://www.gm.go.kr/pt/user"
ROWS = 50
DETAIL_WITHIN = timedelta(days=60)
BOARDS = {
    "nftc": {
        "list": f"{BASE}/nftcBbs/BD_selectNftcBbsList.do",
        "params": {"q_nftcBbsCode": "1001", "q_rowPerPage": ROWS, "q_currPage": 1},
        "detail": BASE + "/nftcBbs/BD_selectNftcBbsDetail.do?q_nftcBbsCode=1001&q_nftcBbsMgtno={id}",
        "name": "고시공고",
    },
    "bbs": {
        "list": f"{BASE}/bbs/BD_selectBbsList.do",
        "params": {"q_bbsCode": "2032", "q_rowPerPage": ROWS, "q_currPage": 1},
        "detail": BASE + "/bbs/BD_selectBbs.do?q_bbsCode=2032&q_bbscttSn={id}",
        "name": "공지사항",
    },
}
DATE_RE = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})")
SHORT_DATE_RE = re.compile(r"(?:(\d{4})\.\s*)?(\d{1,2})\.\s*(\d{1,2})\.")
PERIOD_LABEL = re.compile(r"(접수\s*기간|신청\s*기간|청약\s*신청\s*기간|청약\s*접수\s*기간)\s*[:：]")
METHOD_LABEL = re.compile(r"(신청\s*장소|신청\s*방법|접수\s*장소|접수\s*방법|청약\s*신청\s*장소)\s*[:：]")
SUMMARY_LABEL = re.compile(r"(모집\s*세대|모집\s*호수|공급\s*호수|공급\s*대상|모집\s*대상)\s*[:：]")


class GmCityCollector(BaseCollector):
    """광명시청 고시공고·공지사항"""

    name = "gm_city"

    def fetch(self) -> list[Notice]:
        cfg = self.config["sources"]["gm_city"]
        today = today_kst()
        notices = []
        for board, spec in BOARDS.items():
            html = self.request("GET", spec["list"], params=spec["params"]).text
            rows = parse_list(html, board)
            self.raw_count += len(rows)
            for row in rows:
                if not is_housing_title(row["title"], cfg["search_keywords"], cfg["exclude_keywords"]):
                    continue
                detail = {}
                if row["posted_at"] and today - row["posted_at"] <= DETAIL_WITHIN:
                    try:
                        detail = parse_detail(self.request("GET", detail_url(row)).text, board)
                    except Exception as e:
                        log.warning("광명시청 상세 실패 %s: %s", row["id"], e)
                notices.append(to_notice(row, detail))
        return notices


def is_housing_title(title: str, include: list[str], exclude: list[str]) -> bool:
    return any(k in title for k in include) and not any(k in title for k in exclude)


def detail_url(row: dict) -> str:
    return BOARDS[row["board"]]["detail"].format(id=row["id"])


def parse_list(html: str, board: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("tbody tr"):
        tds = tr.find_all("td")
        if not tds or tds[0].get_text(strip=True) == "공지":  # 상단 고정글
            continue
        a = tr.find("a", onclick=re.compile(r"op(Detail|View)\('"))
        if not a:
            continue
        post_id = re.search(r"op(?:Detail|View)\('(\d+)'\)", a["onclick"]).group(1)
        date_td = next((td for td in tds if re.fullmatch(r"\s*\d{4}-\d{2}-\d{2}\s*", td.get_text())), None)
        rows.append({
            "board": board,
            "id": post_id,
            "title": a.get_text(" ", strip=True),
            "dept": tds[3].get_text(strip=True) if board == "nftc" and len(tds) > 3 else
                    tds[2].get_text(strip=True) if len(tds) > 2 else "",
            "posted_at": parse_date(date_td.get_text()) if date_td else None,
        })
    return rows


def _labelled(lines: list[str], label: str) -> str | None:
    for i, ln in enumerate(lines[:-1]):
        if ln == label:
            return lines[i + 1]
    return None


def parse_period(line: str):
    """'2026. 7. 6.(월) 10:00 ~ 7. 8.(수)' → (2026-07-06, 2026-07-08). 연도는 앞 날짜에서 이어받음."""
    year, dates = None, []
    for y, m, d in SHORT_DATE_RE.findall(line):
        year = int(y) if y else year
        if year is None:
            continue
        dates.append(parse_date(f"{year}{int(m):02d}{int(d):02d}"))
    return (dates[0] if dates else None), (dates[1] if len(dates) > 1 else None)


def parse_detail(html: str, board: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    view = soup.select_one("table.bbsView") or soup
    lines = [ln.strip() for ln in view.get_text("\n", strip=True).splitlines() if ln.strip()]
    body_start = lines.index("내용") + 1 if "내용" in lines else 0
    body = lines[body_start:]

    start = end = None
    for ln in body:
        if PERIOD_LABEL.search(ln):
            start, end = parse_period(PERIOD_LABEL.split(ln)[-1])
            break
    method = [METHOD_LABEL.sub(lambda m: m.group(1) + ":", ln).lstrip("0123456789. ")
              for ln in body if METHOD_LABEL.search(ln)]
    summary = [ln.lstrip("0123456789. ") for ln in body if SUMMARY_LABEL.search(ln)]

    files = []
    if board == "nftc":  # 첨부 정보가 <script>의 fileList.push({...})에 있음
        for block in re.findall(r"fileList\.push\(\{(.*?)\}\);", html, re.S):
            f = dict(re.findall(r'"(\w+)"\s*:\s*"([^"]*)"', block))
            if f.get("fileNm"):
                files.append({"name": f["fileNm"], "kind": "eminwon",
                              "url": "https://eminwon.gm.go.kr/emwp/jsp/ofr/FileDownNew.jsp",
                              "form": {"user_file_nm": f["fileNm"], "sys_file_nm": f.get("sysFileNm", ""),
                                       "file_path": f.get("filePath", "")}})
    else:
        for a in view.select("a[href*=fileDownload]"):
            files.append({"name": a.get("title") or a.get_text(strip=True), "kind": "file",
                          "url": "https://www.gm.go.kr" + a["href"]})
    return {
        "body": "\n".join(body),
        "apply_start": start,
        "apply_end": end,
        "apply_method": "\n".join(method) or None,
        "summary": summary,
        "contact": _labelled(lines, "연락처"),
        "files": files,
    }


def to_notice(row: dict, detail: dict) -> Notice:
    body = detail.get("body", "")
    targets = [t for t in ("고령자", "장애인", "수급자", "한부모", "청년", "신혼") if t in body]
    summary = detail.get("summary") or []
    return Notice(
        source="gm_city",
        source_id=f"{row['board']}-{row['id']}",
        title=row["title"],
        url=detail_url(row),
        posted_at=row["posted_at"],
        apply_start=detail.get("apply_start"),
        apply_end=detail.get("apply_end"),
        region="경기도 광명시",
        housing_type=next((t for t in ("영구임대", "국민임대", "행복주택", "매입임대", "전세임대",
                                       "장기전세", "통합공공임대") if t in row["title"]), None),
        target=", ".join(targets) or None,
        summary="\n".join(summary[:3]) or None,
        apply_method=detail.get("apply_method"),
        institution=f"광명시청 {row['dept']}".strip(),
        attachments=detail.get("files", []),
        raw={"row": row, "body": body, "contact": detail.get("contact"), "signgu": "광명시"},
    )
