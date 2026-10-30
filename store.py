"""data/notices.json 저장소.

- 같은 key("{source}:{source_id}")는 같은 공고 → 알림은 한 번만
- 임시 파일에 쓴 뒤 교체(원자적 쓰기) → 중간에 멈춰도 기존 파일이 깨지지 않음
- raw 원본은 저장하지 않음
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from models import Notice

KST = timezone(timedelta(hours=9))

# 공고 정보로 덮어쓰는 필드. 알림 상태(notified_at 등)는 덮어쓰지 않는다.
NOTICE_FIELDS = [
    "source", "source_id", "title", "url", "posted_at", "apply_start", "apply_end",
    "region", "address", "housing_type", "target", "summary", "apply_method",
    "institution", "attachments",
]
ARCHIVE_THRESHOLD = 300        # 공고가 이만큼 쌓이면 보관 처리
ARCHIVE_AFTER = timedelta(days=365)


def now_kst() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def today_kst() -> date:
    return datetime.now(KST).date()


def _to_json(value):
    if isinstance(value, date):
        return value.isoformat()
    return value


def notice_to_record(notice: Notice) -> dict:
    data = asdict(notice)
    data.pop("raw", None)
    return {k: _to_json(data[k]) for k in NOTICE_FIELDS}


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.archive_path = self.path.with_name("archive.json")
        self.updated_at: str | None = None
        self.records: dict[str, dict] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.updated_at = data.get("updated_at")
            self.records = {r["key"]: r for r in data.get("notices", [])}
        self._loaded = self._snapshot()

    def _sorted(self) -> list[dict]:
        return sorted(self.records.values(), key=lambda r: (r.get("posted_at") or "", r["key"]), reverse=True)

    def _snapshot(self) -> str:
        return json.dumps(self._sorted(), ensure_ascii=False, sort_keys=True)

    @property
    def changed(self) -> bool:
        return self._snapshot() != self._loaded

    def get(self, key: str) -> dict | None:
        return self.records.get(key)

    def upsert(self, notice: Notice, **extra) -> tuple[dict, bool]:
        """공고를 저장한다. (레코드, 신규 여부)를 돌려준다.

        extra: map_url, tags, alert 처럼 수집 후 계산한 값.
        """
        key = notice.key
        fields = notice_to_record(notice) | extra
        record = self.records.get(key)
        if record is None:
            record = {
                "key": key,
                **fields,
                "notified_at": None,
                "reminded_at": None,
                "first_seen_at": now_kst(),
            }
            self.records[key] = record
            return record, True
        record.update(fields)
        return record, False

    def mark_notified(self, key: str, seeded: bool = False) -> None:
        self.records[key]["notified_at"] = now_kst()
        if seeded:
            self.records[key]["seeded"] = True

    def mark_reminded(self, key: str) -> None:
        self.records[key]["reminded_at"] = now_kst()

    def pending_notifications(self) -> list[dict]:
        """아직 알림을 보내지 않은 공고 (alert=False인 공고는 제외)."""
        return [
            r for r in self.records.values()
            if r["notified_at"] is None and r.get("alert", True)
        ]

    def pending_reminders(self, today: date, days_before: int = 1) -> list[dict]:
        """마감 days_before일 전 ~ 마감 당일 사이이고 리마인더를 아직 안 보낸 공고.

        실행이 하루 빠져도 마감 당일에는 보내도록 범위로 판정한다.
        """
        due = []
        for r in self.records.values():
            if r["reminded_at"] or not r["notified_at"] or not r.get("alert", True):
                continue
            if not r.get("apply_end"):
                continue
            days_left = (date.fromisoformat(r["apply_end"]) - today).days
            if 0 <= days_left <= days_before:
                due.append(r)
        return due

    def archive_old(self, today: date) -> int:
        """공고가 많이 쌓이면 마감 후 1년 지난 건을 archive.json으로 옮긴다."""
        if len(self.records) < ARCHIVE_THRESHOLD:
            return 0
        old = {
            k: r for k, r in self.records.items()
            if (end := r.get("apply_end") or r.get("posted_at"))
            and today - date.fromisoformat(end) > ARCHIVE_AFTER
        }
        if not old:
            return 0
        archived = []
        if self.archive_path.exists():
            archived = json.loads(self.archive_path.read_text(encoding="utf-8"))["notices"]
        atomic_write_json(self.archive_path, {"notices": archived + list(old.values())})
        for k in old:
            del self.records[k]
        return len(old)

    def save(self) -> bool:
        """공고 내용이 바뀌었을 때만 쓴다 (매 실행마다 커밋이 생기지 않게). 썼으면 True."""
        if not self.changed and self.path.exists():
            return False
        self.updated_at = now_kst()
        atomic_write_json(self.path, {"updated_at": self.updated_at, "notices": self._sorted()})
        self._loaded = self._snapshot()
        return True
