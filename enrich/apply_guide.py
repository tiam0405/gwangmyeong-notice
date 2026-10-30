"""신청방법 안내.

1. 소스에 신청방법이 있으면 그대로 (LH 상세 안내문, GH 접수기간, 시청·도시공사 본문의 신청장소)
2. 없으면 기관별 고정 안내 (단계 1에서 확인한 실제 사이트)
3. 첨부 공고문이 있으면 "자세한 내용은 공고 원문에서 확인" 안내를 붙인다
   (첨부 내용을 요약하거나 추측하지 않는다)
"""
from __future__ import annotations

from models import Notice

MAX_LINES = 5
MAX_CHARS = 300

TEMPLATES = {
    "LH": "LH청약플러스(apply.lh.or.kr) 또는 LH청약플러스 앱에서 온라인 신청",
    "GH": "GH 주택청약·임대센터(apply.gh.or.kr)에서 신청",
    "광명도시공사": "광명도시공사 청약센터(house.gmuc.co.kr)에서 신청",
}
DEFAULT = "신청방법은 공고 원문에서 확인하세요"
ATTACHMENT_NOTE = "자격·임대료·일정 등 자세한 내용은 공고 원문(첨부 공고문)에서 확인하세요"


def _trim(text: str) -> str:
    lines = [ln.strip().lstrip("○●•·-* ").strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln][:MAX_LINES]
    out = "\n".join(lines)
    return out if len(out) <= MAX_CHARS else out[:MAX_CHARS].rstrip() + "…"


def template_for(notice: Notice) -> str:
    inst = notice.institution or ""
    for name, text in TEMPLATES.items():
        if inst.startswith(name):
            return text
    return DEFAULT


def build(notice: Notice) -> str:
    guide = _trim(notice.apply_method) if notice.apply_method else template_for(notice)
    if notice.attachments:
        guide += "\n" + ATTACHMENT_NOTE
    return guide
