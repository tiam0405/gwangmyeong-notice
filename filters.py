"""공고 판정: 목록에 남길지(keep), 알림을 보낼지(alert), 붙일 표시(tags).

규칙 (config.yaml filters):
1. 제목에 exclude_title_keywords → 버림 (어린이집·상가 등 주택이 아닌 모집)
2. 광명 판정: 광명 소스이거나, 제목·지역·주소·단지명에 region_keywords
   → 아니면 시군구가 비어 있는 광역 공고 중 wide_area_types(전세임대)만 남김
3. exclude_target_keywords(청년·신혼 등)만 대상인 공고 → 목록에는 남기고 알림 제외
   단, senior_keywords가 함께 있으면 알림 유지
4. senior_keywords → "고령자 해당 가능" 표시
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models import Notice

GWANGMYEONG_SOURCES = {"gm_city", "gm_corp"}
SENIOR_TAG = "고령자 해당 가능"
WIDE_TAG = "광역 공고 (광명에서 집을 구해 신청 가능)"
CHECK_TAG = "광명 포함 여부 확인 필요"

# 제목에 이 중 하나라도 있으면 "지역이 구체적으로 적힌 공고" → 광명이 없으면 광명 아님
CITY_NAMES = [
    "서울", "인천", "수원", "성남", "의정부", "안양", "부천", "평택", "동두천", "안산",
    "고양", "과천", "구리", "남양주", "오산", "시흥", "군포", "의왕", "하남", "용인",
    "파주", "이천", "안성", "김포", "화성", "광주", "양주", "포천", "여주", "연천",
    "가평", "양평",
]


@dataclass
class Verdict:
    keep: bool
    alert: bool = False
    tags: list[str] = field(default_factory=list)
    reason: str = ""


def _text(notice: Notice) -> str:
    complexes = notice.raw.get("complexes", [])
    parts = [notice.title, notice.region, notice.address or "", notice.summary or ""]
    parts += [c.get("name", "") + " " + c.get("address", "") for c in complexes]
    return " ".join(parts)


def _has_any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def is_wide_area(notice: Notice) -> bool:
    """시군구가 정해지지 않은 광역·전국 공고 (예: 청년 전세임대 수시모집)."""
    return not notice.raw.get("signgu") and notice.source not in GWANGMYEONG_SOURCES


def classify(notice: Notice, config: dict) -> Verdict:
    f = config["filters"]
    title = notice.title

    if _has_any(title, f["exclude_title_keywords"]):
        return Verdict(keep=False, reason="주택 모집 아님")

    tags = []
    in_gm = notice.source in GWANGMYEONG_SOURCES or _has_any(_text(notice), f["region_keywords"])
    if not in_gm:
        if not is_wide_area(notice):
            return Verdict(keep=False, reason="광명 아님")
        if _has_any(f"{title} {notice.housing_type or ''}", f["wide_area_types"]):
            tags.append(WIDE_TAG)
        elif _has_any(title, CITY_NAMES):
            return Verdict(keep=False, reason="광명 아님 (다른 지역 명시)")
        else:
            # "[경기남부] 매입임대"처럼 광명 포함 여부를 공고문에서만 알 수 있는 경우
            tags.append(CHECK_TAG)

    senior = _has_any(f"{title} {notice.housing_type or ''} {notice.target or ''}",
                      f["senior_keywords"])
    if senior:
        tags.insert(0, SENIOR_TAG)

    target_only = _has_any(title, f["exclude_target_keywords"]) and not senior
    if target_only:
        return Verdict(keep=True, alert=False, tags=tags, reason="청년·신혼 등 대상")

    types = f.get("housing_types") or []
    if types and not _has_any(f"{title} {notice.housing_type or ''}", types):
        return Verdict(keep=True, alert=False, tags=tags, reason="주택유형 제외")

    return Verdict(keep=True, alert=True, tags=tags)
