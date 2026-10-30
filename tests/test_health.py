from datetime import date, timedelta

from health import Health, SourceStatus

D0 = date(2026, 11, 1)


def ok(name="gh"):
    return SourceStatus(name, raw_count=10)


def bad(name="gh", error=None):
    return SourceStatus(name, raw_count=0, error=error)


def test_warn_once_after_days_then_recover(tmp_path):
    h = Health(tmp_path / "health.json")
    assert h.update([ok()], D0, 3) == []
    for i in (1, 2, 3):  # 3일 연속 0건 → 3일째(마지막 정상 후 3일)만 경고
        msgs = h.update([bad()], D0 + timedelta(days=i), 3)
        assert (len(msgs) == 1) == (i == 3)
    assert "GH 청약센터" in msgs[0] and "3일째" in msgs[0]
    assert h.update([bad()], D0 + timedelta(days=4), 3) == []  # 같은 문제로 반복 경고하지 않음
    msgs = h.update([ok()], D0 + timedelta(days=5), 3)
    assert msgs == ["✅ [수집 복구] GH 청약센터 수집이 다시 정상입니다."]


def test_error_message_kept(tmp_path):
    h = Health(tmp_path / "health.json")
    h.update([bad(error="ConnectionError: timeout")], D0, 0)
    assert h.data["gh"]["last_error"] == "ConnectionError: timeout"


def test_never_ok_counts_from_first_failure(tmp_path):
    h = Health(tmp_path / "health.json")
    assert h.update([bad()], D0, 2) == []
    assert h.update([bad()], D0 + timedelta(days=1), 2) == []
    assert len(h.update([bad()], D0 + timedelta(days=2), 2)) == 1


def test_one_source_failing_does_not_affect_others(tmp_path):
    h = Health(tmp_path / "health.json")
    h.update([ok("gh"), ok("lh")], D0, 1)
    msgs = h.update([bad("gh"), ok("lh")], D0 + timedelta(days=1), 1)
    assert len(msgs) == 1 and "GH" in msgs[0]
    assert h.data["lh"]["last_ok"] == (D0 + timedelta(days=1)).isoformat()


def test_save_persists_and_skips_when_unchanged(tmp_path):
    p = tmp_path / "health.json"
    h = Health(p)
    h.update([ok()], D0, 3)
    assert h.save() is True
    h2 = Health(p)
    h2.update([ok()], D0, 3)
    assert h2.save() is False  # 같은 날 다시 정상 → 변경 없음
    assert h2.data["gh"]["last_ok"] == D0.isoformat()
