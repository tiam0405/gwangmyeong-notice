from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Notice:
    source: str            # "myhome" | "lh" | "gh" | "gm_city" | "gm_corp"
    source_id: str         # 소스 내 고유 ID (없으면 url 해시)
    title: str
    url: str
    posted_at: date
    apply_start: date | None = None
    apply_end: date | None = None
    region: str = ""                 # "광명시 하안동" 등
    address: str | None = None       # 정확한 주소 (없으면 None)
    housing_type: str | None = None  # 행복주택, 국민임대, 영구임대 ...
    target: str | None = None        # 청년, 신혼부부, 고령자 ...
    summary: str | None = None
    apply_method: str | None = None
    institution: str | None = None   # 공급기관 (LH, GH, 광명도시공사 ...)
    attachments: list[dict] = field(default_factory=list)  # [{"name", "url", "kind"}]
    raw: dict = field(default_factory=dict)  # 원본 (notices.json에는 저장하지 않음)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"
