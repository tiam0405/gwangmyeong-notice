"""마이홈포털 공공주택 모집공고 API (경기도 전체를 받아서 filters.py에서 광명 판정).

- 현재 진행 중인 공고만 돌려준다 (과거 공고 조회 불가)
- 한 공고가 단지(houseSn)별로 여러 줄 → pblancId로 묶는다
- 0건이면 resultCode "03"(NODATA_ERROR)
"""
from __future__ import annotations

import os
from collections import defaultdict
from urllib.parse import parse_qs, urlparse

from collectors.base import BaseCollector, parse_date
from models import Notice

API_URL = "https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList"
GYEONGGI = "41"
PAGE_SIZE = 100


class MyHomeCollector(BaseCollector):
    """마이홈포털 공공주택 모집공고 API"""

    name = "myhome"

    def fetch(self) -> list[Notice]:
        key = os.environ.get("DATA_GO_KR_KEY")
        if not key:
            raise RuntimeError("DATA_GO_KR_KEY 환경변수가 없습니다")
        rows, page = [], 1
        while True:
            data = self.request("GET", API_URL, params={
                "serviceKey": key, "brtcCode": GYEONGGI,
                "numOfRows": PAGE_SIZE, "pageNo": page,
            }).json()
            items, total = parse_response(data)
            rows.extend(items)
            if not items or len(rows) >= total:
                break
            page += 1
        self.raw_count = len(rows)
        return rows_to_notices(rows)


def parse_response(data: dict) -> tuple[list[dict], int]:
    resp = data.get("response", {})
    code = resp.get("header", {}).get("resultCode")
    if code == "03":  # NODATA_ERROR = 0건
        return [], 0
    if code != "00":
        raise RuntimeError(f"마이홈 API 오류: {resp.get('header')}")
    body = resp.get("body", {})
    items = body.get("item") or []
    if isinstance(items, dict):
        items = [items]
    return items, int(body.get("totalCount") or 0)


def rows_to_notices(rows: list[dict]) -> list[Notice]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row["pblancId"])].append(row)
    return [group_to_notice(pid, group) for pid, group in groups.items()]


def group_to_notice(pblanc_id: str, rows: list[dict]) -> Notice:
    first = rows[0]
    complexes = []  # 단지 목록 (단지명, 주소)
    for r in rows:
        item = ((r.get("hsmpNm") or "").strip(), (r.get("fullAdres") or "").strip())
        if any(item) and item not in complexes:
            complexes.append(item)

    signgu = (first.get("signguNm") or "").strip()
    dong = (first.get("refrnLegaldongNm") or "").strip()
    region = " ".join(p for p in (first.get("brtcNm"), signgu, dong) if p) or "지역 공고문 확인"
    # 단지가 하나일 때만 주소를 확정 (여러 단지면 지도 링크 만들지 않음)
    address = (complexes[0][1] or None) if len(complexes) == 1 else None

    units = sum(int(r.get("sumSuplyCo") or 0) for r in rows)
    summary_parts = [first.get("suplyTyNm"), first.get("houseTyNm")]
    if len(complexes) > 1:
        summary_parts.append(f"{len(complexes)}개 단지")
    if units:
        summary_parts.append(f"총 {units:,}호")

    # LH 공고는 LH 수집기와 같은 key("lh:{panId}")를 써서 main에서 하나로 합친다
    pan_id = lh_pan_id(first.get("url"))
    return Notice(
        source="lh" if pan_id else "myhome",
        source_id=pan_id or pblanc_id,
        title=(first.get("pblancNm") or "").strip(),
        url=pick_url(first),
        posted_at=parse_date(first.get("rcritPblancDe")),
        apply_start=parse_date(first.get("beginDe")),
        apply_end=parse_date(first.get("endDe")),
        region=region,
        address=address,
        housing_type=first.get("suplyTyNm") or None,
        summary=" / ".join(p for p in summary_parts if p) or None,
        institution=first.get("suplyInsttNm") or None,
        raw={
            "rows": rows,
            "complexes": [{"name": n, "address": a} for n, a in complexes],
            "pblanc_id": pblanc_id,
            "signgu": signgu,
            "contact": first.get("refrnc"),
        },
    )


def pick_url(row: dict) -> str:
    """공고별 고유 주소를 우선. 기관 홈페이지 첫 화면(쿼리 없음)이면 마이홈 상세로."""
    url = (row.get("url") or "").strip()
    if url and urlparse(url).query:
        return url
    return (row.get("pcUrl") or url).strip()


def lh_pan_id(url: str | None) -> str | None:
    if not url or "apply.lh.or.kr" not in url:
        return None
    return parse_qs(urlparse(url).query).get("panId", [None])[0]
