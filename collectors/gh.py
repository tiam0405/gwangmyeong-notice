"""GH 청약센터 apply.gh.or.kr 임대주택·매입임대 공고.

- www.gh.or.kr은 robots.txt 전체 금지 → 청약센터(apply.gh.or.kr, Allow: /*)만 사용
- 목록의 지역 칸은 대표 지역 하나뿐 → 상세의 단지 소재지 / "■ 모집지역"으로 광명 판정
- 상세는 마감 전이고 최근에 올라온 공고만 호출
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

BASE = "https://apply.gh.or.kr/sb/sr"
BOARDS = {"sr7150": "임대주택", "sr7155": "매입임대"}
GWANGMYEONG_AREA = "4121"
LIST_PAGES = 2                    # 최신 20건씩
DETAIL_WITHIN = timedelta(days=90)
DATE_RE = re.compile(r"(\d{4})[.-]\s*(\d{1,2})[.-]\s*(\d{1,2})")
LABELS = {"지구명", "소재지", "전화번호", "접수처 운영기간", "지도보기", "전용면적(m²)", "모집호수"}


class GHCollector(BaseCollector):
    """GH 청약센터 apply.gh.or.kr 임대 목록"""

    name = "gh"

    def fetch(self) -> list[Notice]:
        rows: dict[str, dict] = {}
        for board in BOARDS:
            for page in range(1, LIST_PAGES + 1):
                for row in parse_list(self.get_list(board, pageIndex=page), board):
                    rows.setdefault(row["id"], row)
        for row in parse_list(self.get_list("sr7150", searchArea=GWANGMYEONG_AREA), "sr7150"):
            rows.setdefault(row["id"], row)

        self.raw_count = len(rows)
        today = today_kst()
        notices = []
        for row in rows.values():
            detail = {}
            recent = row["posted_at"] and today - row["posted_at"] <= DETAIL_WITHIN
            if row["status"] != "접수마감" and recent:
                try:
                    html = self.request("GET", detail_url(row)).text
                    detail = parse_detail(html)
                except Exception as e:
                    log.warning("GH 상세 실패 %s: %s", row["id"], e)
            notices.append(to_notice(row, detail))
        return notices

    def get_list(self, board: str, **params) -> str:
        return self.request("GET", f"{BASE}/{board}/selectPbancRentHouseList.do", params=params).text


def find_dates(text: str) -> list:
    """'2026.6.30.(화) ~ 2026.7.03' → [date(2026,6,30), date(2026,7,3)] (한 자리 월·일 허용)"""
    return [d for y, m, dd in DATE_RE.findall(text) if (d := parse_date(f"{y}{int(m):02d}{int(dd):02d}"))]


def detail_url(row: dict) -> str:
    return (f"{BASE}/{row['board']}/selectPbancDetailView.do"
            f"?pbancNo={row['pbanc_no']}&pbancKndCd={row['knd']}&previewYn={row['preview']}")


def parse_list(html: str, board: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for a in soup.select("a[data-pbancno]"):
        tr = a.find_parent("tr")
        text = tr.get_text(" ", strip=True) if tr else ""
        dates = find_dates(text)
        cells = tr.find_all("td") if tr else []
        region = cells[3].find(string=True, recursive=False).strip() if len(cells) > 3 else ""
        status = next((s for s in ("접수마감", "접수중", "공고중", "접수예정") if s in text), "")
        rows.append({
            "id": f"{board}-{a['data-pbancno']}",
            "board": board,
            "pbanc_no": a["data-pbancno"],
            "knd": a.get("data-pbanckndcd", "01"),
            "preview": a.get("data-previewyn", "N"),
            "type": a.get("data-biztynm") or BOARDS[board],
            "title": a.get_text(" ", strip=True),
            "region": region,
            "posted_at": dates[0] if dates else None,
            "end": dates[1] if len(dates) > 1 else None,
            "status": status,
        })
    return rows


def _lines(html: str) -> list[str]:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    start = text.find("청약공고 상세정보")
    end = text.find("목록으로", start)
    body = text[start:end if end > 0 else None]
    return [ln.strip() for ln in body.splitlines() if ln.strip()]


def _after(lines: list[str], label: str) -> list[str]:
    """label 바로 다음 줄들 (다음 줄이 다른 라벨이면 값 없음)."""
    out = []
    for i, ln in enumerate(lines[:-1]):
        nxt = lines[i + 1]
        if ln.rstrip(" :") == label and nxt not in LABELS:
            out.append(nxt)
    return out


def _period(line: str):
    dates = find_dates(line)
    return (dates[0] if dates else None), (dates[1] if len(dates) > 1 else None)


def parse_detail(html: str) -> dict:
    lines = _lines(html)
    # "지구명" 다음의 첫 "소재지"만 단지 주소 (그 뒤 접수처 "소재지"는 단지가 아님)
    complexes, name = [], None
    for i, ln in enumerate(lines[:-1]):
        nxt = lines[i + 1]
        if ln == "지구명" and nxt not in LABELS:
            name = nxt
        elif ln == "소재지" and name and nxt not in LABELS:
            complexes.append({"name": name, "address": nxt})
            name = None
    online = _after(lines, "온라인접수기간")
    onsite = _after(lines, "현장접수기간")
    notes = []
    region_text = None
    for ln in lines:
        if ln.startswith("■ 모집지역"):
            region_text = ln.split(":", 1)[-1].strip()
        if ln.startswith("■ 접수기간") and not online:
            online = [ln.split(":", 1)[-1].strip()]
    # 모집지역이 여러 줄에 걸친 경우 이어 붙이기
    if region_text is not None:
        i = next(i for i, ln in enumerate(lines) if ln.startswith("■ 모집지역"))
        for ln in lines[i + 1:]:
            if ln.startswith(("■", "※", "*")):
                break
            region_text += " " + ln
    # 매입임대 본문의 신청방법 (※ 신청방법 ~ 다음 ■ 전까지)
    if any(ln.startswith("※ 신청방법") for ln in lines):
        i = next(i for i, ln in enumerate(lines) if ln.startswith("※ 신청방법"))
        for ln in lines[i:]:
            if ln.startswith("■"):
                break
            notes.append(ln)
    # 주택형 줄에서 공급 대상 (예: "36C 고령자" → 고령자)
    targets = []
    for ln in lines:
        m = re.match(r"^\d{2,3}[A-Z,]*\s+(.+)$", ln)
        if m and not re.search(r"\d", m.group(1)) and m.group(1) not in targets:
            targets.append(m.group(1))
    files = [re.sub(r"\s*\(\d+ Byte\)$", "", ln) for ln in lines if ln.endswith("Byte)")]
    start, end = _period(online[0]) if online else (None, None)
    return {
        "complexes": complexes,
        "apply_start": start,
        "apply_end": end,
        "online": online[0] if online else None,
        "onsite": onsite[0] if onsite else None,
        "region_text": region_text,
        "notes": notes,
        "targets": targets,
        "files": files,
    }


def apply_method(detail: dict) -> str | None:
    if detail.get("notes"):
        return "\n".join(detail["notes"])
    parts = []
    if detail.get("online"):
        parts.append(f"온라인 접수: {detail['online']} (GH청약센터 apply.gh.or.kr)")
    if detail.get("onsite") and detail["onsite"].strip("~ "):
        parts.append(f"현장 접수: {detail['onsite']}")
    return "\n".join(parts) or None


def to_notice(row: dict, detail: dict) -> Notice:
    cx = detail.get("complexes", [])
    region, signgu, address = row["region"] or "경기도", row["region"], None
    if len(cx) == 1:
        address = cx[0]["address"]
        parts = address.split()
        region = " ".join(p for p in parts[:3] if not re.search(r"\d", p))
        signgu = next((p for p in parts[1:3] if p.endswith(("시", "군"))), signgu)
    elif len(cx) > 1 or row["region"] in ("", "경기도") or detail.get("region_text"):
        region, signgu = "경기도 (여러 지역)", ""

    summary = [row["type"]]
    if len(cx) > 1:
        summary.append(f"{len(cx)}개 단지")
    if detail.get("region_text"):
        summary.append(f"모집지역: {detail['region_text']}")
    targets = detail.get("targets") or []
    return Notice(
        source="gh",
        source_id=row["id"],
        title=row["title"],
        url=detail_url(row),
        posted_at=row["posted_at"],
        apply_start=detail.get("apply_start"),
        apply_end=detail.get("apply_end") or row["end"],
        region=region,
        address=address,
        housing_type=row["type"],
        target=", ".join(targets) or None,
        summary=" / ".join(summary),
        apply_method=apply_method(detail),
        institution="GH",
        attachments=[{"name": f, "url": detail_url(row), "kind": "공고문"} for f in detail.get("files", [])],
        raw={"row": row, "complexes": cx, "signgu": signgu,
             "region_text": detail.get("region_text"), "status": row["status"]},
    )
