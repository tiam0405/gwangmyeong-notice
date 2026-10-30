"""수집기 상태 감시 (data/health.json).

- 실행마다 소스별로 "원본 줄 수 > 0 이고 오류 없음"이면 정상, 아니면 이상
- 마지막 정상일로부터 warn_days일 이상 지나면 관리자(나)에게 경고 1회
- 다시 정상이 되면 복구 알림 1회
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from store import atomic_write_json

SOURCE_NAMES = {"myhome": "마이홈포털", "lh": "LH", "gh": "GH 청약센터",
                "gm_city": "광명시청", "gm_corp": "광명도시공사"}
ACTIONS_URL = "https://github.com/tiam0405/gwangmyeong-notice/actions"


@dataclass
class SourceStatus:
    name: str
    raw_count: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.raw_count > 0


class Health:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: dict[str, dict] = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self._loaded = json.dumps(self.data, sort_keys=True, ensure_ascii=False)

    def update(self, statuses: list[SourceStatus], today: date, warn_days: int) -> list[str]:
        """상태를 기록하고, 보내야 할 경고·복구 메시지를 돌려준다."""
        messages = []
        for st in statuses:
            h = self.data.setdefault(st.name, {"last_ok": None, "last_error": None, "warned": False})
            label = SOURCE_NAMES.get(st.name, st.name)
            if st.ok:
                if h["warned"]:
                    messages.append(f"✅ [수집 복구] {label} 수집이 다시 정상입니다.")
                h.update(last_ok=today.isoformat(), last_error=None, warned=False)
                h.pop("first_fail", None)
                continue
            h["last_error"] = (st.error or "읽은 항목 0건")[:200]
            # 한 번도 정상인 적이 없으면 처음 실패한 날부터 센다
            since = h["last_ok"] or h.setdefault("first_fail", today.isoformat())
            days = (today - date.fromisoformat(since)).days
            if days >= warn_days and not h["warned"]:
                h["warned"] = True
                messages.append(
                    f"⚠️ [수집 경고] {label} 수집이 {days}일째 실패 또는 0건입니다.\n"
                    f"사이트 구조가 바뀌었을 수 있습니다.\n마지막 오류: {h['last_error']}")
        return messages

    @property
    def changed(self) -> bool:
        return json.dumps(self.data, sort_keys=True, ensure_ascii=False) != self._loaded

    def save(self) -> bool:
        if not self.changed:
            return False
        atomic_write_json(self.path, self.data)
        self._loaded = json.dumps(self.data, sort_keys=True, ensure_ascii=False)
        return True
