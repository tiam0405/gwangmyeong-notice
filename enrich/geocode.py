"""주소 → 지도 링크. 도로명/지번 수준으로 구체적일 때만 만든다 (잘못된 위치 안내 방지).

    "경기도 광명시 하안로 60"            → 링크
    "경기도 과천시 갈현동 581-1"         → 링크
    "광명시 광명2동 88-14번지 일원"      → 없음 ("일원"은 범위)
    "광명시 하안동", "광명시"            → 없음
"""
from __future__ import annotations

import re
from urllib.parse import quote

ROAD = re.compile(r"[가-힣0-9]+(?:로|길)(?:\s?\d+번?길)?\s?\d+(?:-\d+)?(?![\d가-힣])")
JIBUN = re.compile(r"[가-힣0-9]+(?:동|리|가)\s?(?:산\s?)?\d+(?:-\d+)?(?:번지)?(?![\d])")
VAGUE = re.compile(r"일원|일대|인근|부근|주변|\s외(?:\s|$)|외\s*\d+\s*(?:필지|개|筆)")
NAVER = "https://map.naver.com/p/search/{q}"


def precise_address(address: str | None) -> str | None:
    """지도에 쓸 수 있는 구체적 주소 부분만 돌려준다. 모호하면 None."""
    if not address:
        return None
    address = re.sub(r"\s+", " ", address).strip()
    if VAGUE.search(address):
        return None
    m = ROAD.search(address) or JIBUN.search(address)
    if not m:
        return None
    # 번지 뒤의 건물·단지명은 검색을 흐리므로 잘라낸다
    return address[:m.end()].replace("번지", "").strip()


def map_url(address: str | None) -> str | None:
    addr = precise_address(address)
    return NAVER.format(q=quote(addr)) if addr else None
