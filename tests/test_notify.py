from datetime import date

import pytest
import requests

import main
from models import Notice
from notifiers import telegram
from notifiers.base import BaseNotifier
from notifiers.telegram import TelegramNotifier
from store import Store

CONFIG = main.load_config()


class FakeNotifier(BaseNotifier):
    def __init__(self, ok=True):
        self.ok, self.sent = ok, []

    def send(self, text):
        self.sent.append(text)
        return self.ok


def notice(sid="1", **kw):
    return Notice(source="gm_corp", source_id=sid, title=f"광명 행복주택 {sid}단지 입주자 모집", url="u",
                  posted_at=date(2026, 11, 3), apply_start=date(2026, 11, 10),
                  apply_end=date(2026, 11, 13), region="경기도 광명시", raw={"signgu": "광명시"}, **kw)


def run(store, notifier, today, notices=()):
    main.process(list(notices), store, CONFIG, today)
    main.send_notifications(store, notifier, today, 1)


def test_new_notice_sent_once(tmp_path):
    store, fake = Store(tmp_path / "n.json"), FakeNotifier()
    run(store, fake, date(2026, 11, 4), [notice()])
    run(store, fake, date(2026, 11, 4), [notice()])  # 다음 실행에서 같은 공고
    assert len(fake.sent) == 1 and fake.sent[0].startswith("📢 [광명도시공사]")


def test_failed_send_retried_next_run(tmp_path):
    store = Store(tmp_path / "n.json")
    run(store, FakeNotifier(ok=False), date(2026, 11, 4), [notice()])
    assert store.get("gm_corp:1")["notified_at"] is None
    ok = FakeNotifier()
    run(store, ok, date(2026, 11, 4))
    assert len(ok.sent) == 1 and store.get("gm_corp:1")["notified_at"]


def test_reminder_day_before(tmp_path):
    store, fake = Store(tmp_path / "n.json"), FakeNotifier()
    run(store, fake, date(2026, 11, 4), [notice()])
    run(store, fake, date(2026, 11, 12))
    run(store, fake, date(2026, 11, 13))
    assert len(fake.sent) == 2 and fake.sent[1].startswith("⏰ [마감 D-1]")


def test_seed_sends_nothing(tmp_path):
    store = Store(tmp_path / "n.json")
    main.process([notice()], store, CONFIG, date(2026, 11, 4), seed=True)
    fake = FakeNotifier()
    main.send_notifications(store, fake, date(2026, 11, 4), 1)
    assert fake.sent == []


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, str(body)
        self.ok = status == 200

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(telegram.time, "sleep", lambda s: None)


def test_telegram_sends_to_all(monkeypatch):
    calls = []
    monkeypatch.setattr(telegram.requests, "post",
                        lambda url, json, timeout: calls.append(json) or Resp(200, {"ok": True}))
    assert TelegramNotifier("TOKEN", ["1", "2"]).send("hi")
    assert [c["chat_id"] for c in calls] == ["1", "2"]


def test_telegram_retries_after_429(monkeypatch):
    replies = iter([Resp(429, {"ok": False, "parameters": {"retry_after": 1}}), Resp(200, {"ok": True})])
    monkeypatch.setattr(telegram.requests, "post", lambda url, json, timeout: next(replies))
    assert TelegramNotifier("TOKEN", ["1"]).send("hi")


def test_telegram_error_hides_token(monkeypatch, caplog):
    def boom(url, json, timeout):
        raise requests.ConnectionError(f"failed {url}")
    monkeypatch.setattr(telegram.requests, "post", boom)
    assert not TelegramNotifier("SECRET123", ["1"]).send("hi")
    assert "SECRET123" not in caplog.text


def test_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "11, 22")
    monkeypatch.delenv("TELEGRAM_ADMIN_CHAT_ID", raising=False)
    assert TelegramNotifier.from_env().chat_ids == ["11", "22"]
    assert TelegramNotifier.from_env(admin=True).chat_ids == ["11"]
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    assert TelegramNotifier.from_env() is None
