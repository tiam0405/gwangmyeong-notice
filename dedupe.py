"""기관 간 중복 공고 판정.

광명시청은 LH·GH·광명도시공사 공고를 "…모집 공고 알림"처럼 다시 올리고,
마이홈은 광명도시공사 공고를 그대로 싣는다. 제목에서 기관명·연도·"공고/알림" 같은
말을 지우고 비교해서, 게시일이 가까운 비슷한 공고는 같은 공고로 본다.

- 다른 소스끼리만 비교한다 (같은 소스는 "I/Ⅱ"처럼 한 글자 다른 별개 공고가 많음)
- 같은 소스에서는 [정정공고]만 원공고와 같은 공고로 본다
- 원 기관 공고가 먼저 알림을 받도록 소스 우선순위대로 처리한다
"""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher

from filters import is_correction, normalize_title

SOURCE_PRIORITY = {"lh": 0, "gh": 0, "gm_corp": 0, "myhome": 1, "gm_city": 2}
WINDOW_DAYS = 21
SIMILARITY = 0.85
NOISE = [
    "광명도시공사", "한국토지주택공사", "경기주택도시공사", "광명시", "LH", "GH",
    "[정정공고]", "공고", "알림", "안내", "입주자", "모집", "의",
]


def core_title(title: str) -> str:
    t = re.sub(r"(20\d{2}|[`'‘’]?\d{2})년", "", title)
    for w in NOISE:
        t = t.replace(w, "")
    return re.sub(r"[\s_·.,()\[\]「」『』'\"`‘’-]+", "", t)


def _codes(core: str) -> set[str]:
    """구역·단지·차수 같은 숫자/영문/로마숫자 토큰 (예: 4R, 13, A1, Ⅱ)."""
    return set(re.findall(r"[0-9A-Za-zⅠ-Ⅻ]+", core))


def similar(a: str, b: str) -> bool:
    ca, cb = core_title(a), core_title(b)
    if not ca or not cb:
        return False
    if _codes(ca) != _codes(cb):  # "제1R구역"과 "제4R구역"은 다른 공고
        return False
    if ca in cb or cb in ca:
        return min(len(ca), len(cb)) >= 8
    return SequenceMatcher(None, ca, cb).ratio() >= SIMILARITY


def _close(d1: str | date | None, d2: str | date | None) -> bool:
    if not d1 or not d2:
        return True
    d1 = date.fromisoformat(d1) if isinstance(d1, str) else d1
    d2 = date.fromisoformat(d2) if isinstance(d2, str) else d2
    return abs((d1 - d2).days) <= WINDOW_DAYS


def find_duplicate(notice, seen: list[dict]) -> str | None:
    """seen: [{"key", "source", "title", "posted_at"}] 이미 처리한 공고. 같은 공고의 key를 돌려준다."""
    for s in seen:
        if s["key"] == notice.key or not _close(s["posted_at"], notice.posted_at):
            continue
        if s["source"] == notice.source:
            if is_correction(notice.title) and normalize_title(notice.title) == normalize_title(s["title"]):
                return s["key"]
            continue
        if similar(notice.title, s["title"]):
            return s["key"]
    return None


def by_priority(notices: list) -> list:
    return sorted(notices, key=lambda n: SOURCE_PRIORITY.get(n.source, 9))
