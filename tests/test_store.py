import json
from datetime import date

import pytest

import store as store_mod
from models import Notice
from store import Store


def make_notice(source_id="1", **kw) -> Notice:
    base = dict(
        source="lh", source_id=source_id, title="광명 행복주택", url="https://example.com",
        posted_at=date(2026, 11, 3), apply_start=date(2026, 11, 10), apply_end=date(2026, 11, 13),
        region="광명시 하안동", raw={"big": "x" * 1000},
    )
    return Notice(**(base | kw))


def test_same_notice_notified_once(tmp_path):
    s = Store(tmp_path / "notices.json")
    _, new1 = s.upsert(make_notice())
    assert new1
    assert len(s.pending_notifications()) == 1
    s.mark_notified("lh:1")
    s.save()

    s2 = Store(tmp_path / "notices.json")
    _, new2 = s2.upsert(make_notice(title="광명 행복주택 (정정)"))
    assert not new2
    assert s2.pending_notifications() == []
    assert s2.get("lh:1")["title"] == "광명 행복주택 (정정)"
    assert s2.get("lh:1")["notified_at"] is not None


def test_raw_not_saved_and_dates_iso(tmp_path):
    s = Store(tmp_path / "notices.json")
    s.upsert(make_notice(), map_url=None, tags=["고령자 해당 가능"])
    s.save()
    rec = json.loads((tmp_path / "notices.json").read_text(encoding="utf-8"))["notices"][0]
    assert "raw" not in rec
    assert rec["apply_end"] == "2026-11-13"
    assert rec["tags"] == ["고령자 해당 가능"]
    assert rec["key"] == "lh:1"


def test_missing_apply_dates_ok(tmp_path):
    s = Store(tmp_path / "notices.json")
    s.upsert(make_notice(apply_start=None, apply_end=None))
    s.mark_notified("lh:1")
    assert s.pending_reminders(date(2026, 11, 12)) == []
    s.save()


def test_alert_false_is_stored_but_not_notified(tmp_path):
    s = Store(tmp_path / "notices.json")
    s.upsert(make_notice(), alert=False)
    assert s.pending_notifications() == []
    assert s.get("lh:1") is not None


def test_reminder_window(tmp_path):
    s = Store(tmp_path / "notices.json")
    s.upsert(make_notice())
    assert s.pending_reminders(date(2026, 11, 12)) == []  # 알림 전에는 리마인더 없음
    s.mark_notified("lh:1")
    assert s.pending_reminders(date(2026, 11, 11)) == []   # D-2
    assert len(s.pending_reminders(date(2026, 11, 12))) == 1  # D-1
    assert len(s.pending_reminders(date(2026, 11, 13))) == 1  # 당일 (하루 놓친 경우)
    assert s.pending_reminders(date(2026, 11, 14)) == []   # 마감 후
    s.mark_reminded("lh:1")
    assert s.pending_reminders(date(2026, 11, 12)) == []


def test_seed_marks_notified(tmp_path):
    s = Store(tmp_path / "notices.json")
    s.upsert(make_notice())
    s.mark_notified("lh:1", seeded=True)
    assert s.pending_notifications() == []
    assert s.get("lh:1")["seeded"] is True


def test_crash_during_save_keeps_old_file(tmp_path, monkeypatch):
    path = tmp_path / "notices.json"
    s = Store(path)
    s.upsert(make_notice("1"))
    s.save()
    before = path.read_text(encoding="utf-8")

    s.upsert(make_notice("2"))

    def boom(*a, **kw):
        raise KeyboardInterrupt  # 쓰는 도중 강제 종료
    monkeypatch.setattr(store_mod.json, "dump", boom)
    with pytest.raises(KeyboardInterrupt):
        s.save()

    assert path.read_text(encoding="utf-8") == before
    assert list(tmp_path.glob("*.tmp")) == []


def test_archive_old(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "ARCHIVE_THRESHOLD", 2)
    s = Store(tmp_path / "notices.json")
    s.upsert(make_notice("old", apply_end=date(2024, 1, 1)))
    s.upsert(make_notice("new"))
    assert s.archive_old(date(2026, 11, 1)) == 1
    assert s.get("lh:old") is None and s.get("lh:new") is not None
    archived = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))["notices"]
    assert archived[0]["key"] == "lh:old"
