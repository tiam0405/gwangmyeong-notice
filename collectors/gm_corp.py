"""광명도시공사 청약센터 house.gmuc.co.kr 공지사항.

- 목록·상세 모두 POST로 HTML 조각을 받는다 (공고별 고정 URL 없음)
- 목록에 날짜가 없고, 당첨결과·서류제출 같은 후속 글이 섞임 → 제목으로 모집공고만
- 본문 "○ 청약신청기간: `26. 7. 6.(월) ~ `26. 7. 8.(수)" 형식 (연도 두 자리)
- 첨부는 file_download(file_id, detail_file_id) → POST /jsp/admin/fileDownload.jsp
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from collectors.base import BaseCollector, parse_date
from models import Notice

log = logging.getLogger(__name__)

BASE = "https://house.gmuc.co.kr"
LIST_URL = f"{BASE}/jsp/guser/notice_list.jsp"
VIEW_URL = f"{BASE}/jsp/guser/notice_view.jsp"
FILE_URL = f"{BASE}/jsp/admin/fileDownload.jsp"
FOLLOW_UP = ["결과", "발표", "연기", "서류제출", "당첨", "추첨", "입주예정", "계약"]
DATE_RE = re.compile(r"[`'‘’]?(\d{4}|\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.")


class GmCorpCollector(BaseCollector):
    """광명도시공사 청약센터"""

    name = "gm_corp"

    def fetch(self) -> list[Notice]:
        html = self.request("POST", LIST_URL, data={
            "pagenum": "1", "Noticecategory": "", "Noticename": "", "Noticeuseyn": "", "Type": "",
        }).text
        notices = []
        for row in parse_list(html):
            if not is_recruitment(row["title"]):
                continue
            detail = parse_detail(self.request("POST", VIEW_URL, data={"Noticeid": row["id"]}).text)
            notices.append(to_notice(row, detail))
        return notices


def is_recruitment(title: str) -> bool:
    return "모집" in title and not any(w in title for w in FOLLOW_UP)


def parse_list(html: str) -> list[dict]:
    rows = []
    for li in BeautifulSoup(html, "html.parser").select("ul.board-list li"):
        a = li.select_one(".subject a[href*=notice_view]")
        if not a:
            continue
        rows.append({
            "id": re.search(r"notice_view\('(\d+)'\)", a["href"]).group(1),
            "title": a.get_text(" ", strip=True),
            "type": li.select_one(".type").get_text(strip=True) if li.select_one(".type") else None,
            "pinned": "notice" in (li.get("class") or []),
        })
    return rows


def parse_dates(text: str) -> list:
    out = []
    for y, m, d in DATE_RE.findall(text):
        year = int(y) + (2000 if len(y) == 2 else 0)
        if (dt := parse_date(f"{year}{int(m):02d}{int(d):02d}")):
            out.append(dt)
    return out


def _value(line: str) -> str:
    return re.split(r"[:：]", line, maxsplit=1)[-1].strip()


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]
    posted = next((parse_date(ln) for ln in lines if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", ln)), None)

    start = end = address = target = None
    method, summary = [], []
    for ln in lines:
        key = ln.lstrip("○-* ").replace(" ", "")
        if key.startswith("청약신청기간") and start is None:
            dates = parse_dates(ln)
            start, end = (dates + [None, None])[:2]
        elif key.startswith(("청약신청장소", "신청장소", "접수장소")):
            method.append("신청장소: " + _value(ln))
        elif key.startswith(("(방문접수기간)", "방문접수")) or "방문접수의 경우" in ln:
            method.append(ln.lstrip("○-* "))
        elif key.startswith("대상주택"):
            summary.append("대상주택: " + _value(ln))
            m = re.search(r"\(([^()]*광명[^()]*)\)", ln)
            address = m.group(1).strip() if m else None
        elif key.startswith("(신청대상)"):
            target = re.sub(r"^[-\s]*\(신청대상\)\s*", "", ln).removesuffix("계층").strip()
        elif key.startswith("모집호수"):
            summary.append("모집호수: " + _value(ln))

    files = [
        {"name": re.sub(r"\s*:\s*\d+$", "", a.get_text(" ", strip=True)),  # 끝의 다운로드 수 제거
         "kind": "gmuc", "url": FILE_URL,
         "form": dict(zip(("file_id", "detail_file_id"),
                          re.findall(r"'(\d+)'", a.get("onclick", ""))))}
        for a in soup.find_all(onclick=re.compile(r"file_download\("))
    ]
    method.sort(key=lambda m: not m.startswith("신청장소"))  # 신청장소를 맨 앞에
    return {"posted_at": posted, "apply_start": start, "apply_end": end, "address": address,
            "target": target, "apply_method": "\n".join(method) or None,
            "summary": summary, "files": files, "body": "\n".join(lines)}


def to_notice(row: dict, detail: dict) -> Notice:
    housing = (row.get("type") or "").split("(")[0] or None
    return Notice(
        source="gm_corp",
        source_id=row["id"],
        title=row["title"],
        # 공고별 고정 주소가 없어 청약센터 공지사항 목록으로 안내
        url=f"{BASE}/?menu=notice&Noticeid={row['id']}",
        posted_at=detail.get("posted_at"),
        apply_start=detail.get("apply_start"),
        apply_end=detail.get("apply_end"),
        region="경기도 광명시",
        address=detail.get("address"),
        housing_type=housing,
        target=detail.get("target"),
        summary="\n".join(detail.get("summary", [])) or None,
        apply_method=detail.get("apply_method"),
        institution="광명도시공사",
        attachments=detail.get("files", []),
        raw={"row": row, "body": detail.get("body"), "signgu": "광명시"},
    )
