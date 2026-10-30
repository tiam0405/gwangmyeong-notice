"""LH 분양임대공고 목록·상세 API.

- 목록은 시도(경기=41)까지만 거를 수 있다 → 광명 판정은 상세의 단지 주소로
- 상세는 접수중·공고중인 공고만 호출 (마감 공고까지 매번 부르지 않음)
- 공고문 첨부(lhFile.do)는 robots.txt 금지 → 내려받지 않고 링크만 보관
- key는 "lh:{PAN_ID}" → 마이홈의 LH 공고와 같은 key가 되어 main에서 합쳐진다
"""
from __future__ import annotations

import logging
import os
import re

from collectors.base import BaseCollector, parse_date
from models import Notice

log = logging.getLogger(__name__)

LIST_URL = "https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"
DETAIL_URL = "https://apis.data.go.kr/B552555/lhLeaseNoticeDtlInfo1/getLeaseNoticeDtlInfo1"
GYEONGGI = "41"
NOTICE_TYPES = ["06", "13"]  # 06 임대주택, 13 주거복지(매입·전세임대)
OPEN_STATES = {"공고중", "접수중", "정정공고중"}
PAGE_SIZE = 100
DETAIL_KEYS = ["SPL_INF_TP_CD", "CCR_CNNT_SYS_DS_CD", "PAN_ID", "UPP_AIS_TP_CD", "AIS_TP_CD"]

# 접수기간 필드는 공급유형마다 이름이 다르다 (시작, 마감)
APPLY_FIELDS = [
    ("SBSC_ACP_ST_DT", "SBSC_ACP_CLSG_DT"),
    ("UST_ACP_ST_DTTM", "UST_ACP_CLSG_DTTM"),
    ("ACP_ST_DT", "ACP_ED_DT"),
]


class LHCollector(BaseCollector):
    """LH 분양임대공고 목록·상세 API"""

    name = "lh"

    def fetch(self) -> list[Notice]:
        self.key = os.environ.get("DATA_GO_KR_KEY")
        if not self.key:
            raise RuntimeError("DATA_GO_KR_KEY 환경변수가 없습니다")
        notices = []
        rows = self.list_rows()
        self.raw_count = len(rows)
        for row in rows:
            detail = {}
            if row.get("PAN_SS") in OPEN_STATES:
                try:
                    detail = self.detail(row)
                except Exception as e:  # 상세 실패해도 목록 정보로는 저장
                    log.warning("LH 상세 실패 %s: %s", row.get("PAN_ID"), e)
            notices.append(to_notice(row, detail))
        return notices

    def list_rows(self) -> list[dict]:
        rows = []
        for tp in NOTICE_TYPES:
            page = 1
            while True:
                data = self.request("GET", LIST_URL, params={
                    "serviceKey": self.key, "PG_SZ": PAGE_SIZE, "PAGE": page,
                    "UPP_AIS_TP_CD": tp, "CNP_CD": GYEONGGI,
                }).json()
                items = parse_list(data)
                rows.extend(items)
                total = int(items[0].get("ALL_CNT") or 0) if items else 0
                if len(items) < PAGE_SIZE or page * PAGE_SIZE >= total:
                    break
                page += 1
        return rows

    def detail(self, row: dict) -> dict:
        params = {"serviceKey": self.key} | {k: row.get(k, "") for k in DETAIL_KEYS}
        return parse_detail(self.request("GET", DETAIL_URL, params=params).json())


def parse_list(data: list) -> list[dict]:
    for block in data:
        if "dsList" in block:
            return block["dsList"] or []
    return []


def parse_detail(data: list) -> dict:
    """[{"dsSch": …}, {"dsSbd": […], "dsSbdNm": […], …}] → {"dsSbd": […], …}

    "…Nm" 데이터셋은 컬럼 이름표라 버린다.
    """
    merged = {}
    for block in data:
        for name, rows in block.items():
            if name.endswith("Nm") or name in ("dsSch", "resHeader"):
                continue
            merged[name] = rows or []
    return merged


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln) or None


def complexes(detail: dict) -> list[dict]:
    result = []
    for s in detail.get("dsSbd", []):
        addr = " ".join(p for p in (s.get("LGDN_ADR"), s.get("LGDN_DTL_ADR")) if p).strip()
        addr = addr or (s.get("LCT_ARA_ADR") or "").strip()
        name = (s.get("LCC_NT_NM") or s.get("BZDT_NM") or "").strip()
        units = s.get("HSH_CNT") or s.get("SUM_TOT_HSH_CNT")
        if name or addr:
            result.append({"name": name, "address": addr, "units": units})
    return result


def region_from_address(address: str) -> tuple[str, str]:
    """'경기도 과천시 갈현동 581-1' → ('경기도 과천시 갈현동', '과천시')"""
    parts = address.split()
    signgu = next((p for p in parts[1:3] if p.endswith(("시", "군", "구"))), "")
    region = " ".join(p for p in parts[:3] if not re.search(r"\d", p))
    return region, signgu


def apply_period(detail: dict):
    for sched in detail.get("dsSplScdl", []):
        for st, ed in APPLY_FIELDS:
            start, end = parse_date(sched.get(st)), parse_date(sched.get(ed))
            if start or end:
                return start, end
    return None, None


CHANNEL = re.compile(r"인터넷|모바일|앱|App|방문|현장|우편|PC|청약플러스")


def apply_method(detail: dict) -> str | None:
    """기타안내(ETC_CTS) 중 신청 경로를 말하는 줄만 + 접수처."""
    parts = []
    for e in detail.get("dsEtcInfo", []):
        text = clean_text(e.get("ETC_CTS")) or ""
        parts += [ln for ln in text.splitlines() if CHANNEL.search(ln)]
    for p in detail.get("dsCtrtPlc", []):
        place = " ".join(x for x in (p.get("CTRT_PLC_ADR"), p.get("CTRT_PLC_DTL_ADR")) if x)
        if place:
            phone = p.get("SIL_OFC_TLNO")
            parts.append(f"접수처: {place}" + (f" ({phone})" if phone else ""))
    return "\n".join(p for p in parts if p) or None


def to_notice(row: dict, detail: dict) -> Notice:
    cx = complexes(detail)
    region, signgu = "경기도", ""
    address = None
    if len(cx) == 1 and cx[0]["address"]:
        address = cx[0]["address"]
        region, signgu = region_from_address(address)

    units = sum(int(c["units"]) for c in cx if str(c.get("units") or "").isdigit())
    summary = [row.get("AIS_TP_CD_NM")]
    if len(cx) > 1:
        summary.append(f"{len(cx)}개 단지")
    if units:
        summary.append(f"총 {units:,}세대")

    start, end = apply_period(detail)
    attachments = [
        {"name": a.get("CMN_AHFL_NM"), "url": a.get("AHFL_URL"), "kind": a.get("SL_PAN_AHFL_DS_CD_NM")}
        for a in detail.get("dsAhflInfo", []) if a.get("AHFL_URL")
    ]
    return Notice(
        source="lh",
        source_id=str(row["PAN_ID"]),
        title=(row.get("PAN_NM") or "").strip(),
        url=row.get("DTL_URL") or "",
        posted_at=parse_date(row.get("PAN_NT_ST_DT")) or parse_date(row.get("PAN_DT")),
        apply_start=start,
        apply_end=end or parse_date(row.get("CLSG_DT")),
        region=region,
        address=address,
        housing_type=row.get("AIS_TP_CD_NM") or None,
        summary=" / ".join(s for s in summary if s) or None,
        apply_method=apply_method(detail),
        institution="LH",
        attachments=attachments,
        raw={"row": row, "detail": detail, "complexes": cx, "signgu": signgu,
             "status": row.get("PAN_SS")},
    )
