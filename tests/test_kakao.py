import json
from datetime import date

import pytest
import requests

import formatter
from notifiers import kakao, token_store
from notifiers.kakao import KakaoAuthError, KakaoNotifier


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.ok = 200 <= status < 300
        self.text = json.dumps(body, ensure_ascii=False)
        self.content = self.text.encode()

    def json(self):
        return self._body

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(self.status_code)


def rec(**kw):
    base = {"key": "lh:1", "source": "lh", "title": "광명시흥 A1블록 행복주택 입주자 모집공고",
            "url": "https://apply.lh.or.kr/x", "apply_start": "2026-11-10", "apply_end": "2026-11-13",
            "region": "경기도 광명시 가학동", "tags": ["고령자 해당 가능"]}
    return base | kw


def test_kakao_text():
    text = formatter.render_kakao(rec())
    assert text == ("[LH] 광명시흥 A1블록 행복주택 입주자 모집공고\n👵 고령자 해당 가능\n"
                    "⏰ 접수 11/10(화) ~ 11/13(금)\n📍 경기도 광명시 가학동")


def test_kakao_text_without_dates():
    assert "⏰ 접수기간: 공고문 확인" in formatter.render_kakao(rec(apply_start=None, apply_end=None))


def test_kakao_long_title_shortened_to_200():
    text = formatter.render_kakao(rec(title="광명 " * 120))
    assert len(text) <= 200
    assert "⏰ 접수 11/10(화) ~ 11/13(금)" in text  # 제목만 줄이고 접수기간은 남긴다


def test_kakao_reminder():
    assert formatter.render_kakao_reminder(rec(), date(2026, 11, 12)).startswith("⏰ [마감 D-1] 광명시흥")


def test_send_builds_text_template(monkeypatch):
    sent = {}

    def post(url, timeout, headers, data):
        sent.update(url=url, auth=headers["Authorization"], tpl=json.loads(data["template_object"]))
        return Resp(200, {"result_code": 0})
    monkeypatch.setattr(kakao.requests, "post", post)
    assert KakaoNotifier("ACCESS").send("hello", "https://apply.lh.or.kr/x")
    assert sent["url"].endswith("/v2/api/talk/memo/default/send") and sent["auth"] == "Bearer ACCESS"
    assert sent["tpl"] == {"object_type": "text", "text": "hello", "button_title": "공고 보기",
                           "link": {"web_url": "https://apply.lh.or.kr/x",
                                    "mobile_web_url": "https://apply.lh.or.kr/x"}}


def test_send_failure(monkeypatch):
    monkeypatch.setattr(kakao.requests, "post", lambda *a, **k: Resp(401, {"code": -401}))
    assert not KakaoNotifier("A").send("x")


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "key")
    monkeypatch.setenv("KAKAO_CLIENT_SECRET", "sec")
    monkeypatch.setenv("KAKAO_REFRESH_TOKEN", "old")


def test_refresh_without_rotation(monkeypatch, env):
    calls = []
    monkeypatch.setattr(kakao.requests, "post",
                        lambda url, data, timeout: calls.append(data) or Resp(200, {"access_token": "A"}))
    saved = []
    n = KakaoNotifier.from_env(on_new_refresh_token=saved.append)
    assert n.access_token == "A" and saved == []
    assert calls[0] == {"grant_type": "refresh_token", "client_id": "key",
                        "refresh_token": "old", "client_secret": "sec"}


def test_refresh_with_rotation_saves_new_token(monkeypatch, env):
    monkeypatch.setattr(kakao.requests, "post",
                        lambda url, data, timeout: Resp(200, {"access_token": "A", "refresh_token": "NEW"}))
    saved = []
    KakaoNotifier.from_env(on_new_refresh_token=saved.append)
    assert saved == ["NEW"]


def test_refresh_error_hides_token(monkeypatch, env):
    monkeypatch.setattr(kakao.requests, "post",
                        lambda url, data, timeout: Resp(401, {"error": "invalid_grant", "error_description": "expired"}))
    with pytest.raises(KakaoAuthError) as e:
        KakaoNotifier.from_env()
    assert "invalid_grant" in str(e.value) and "old" not in str(e.value)


def test_missing_env_returns_none(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    assert KakaoNotifier.from_env() is None


def test_save_env_file_replaces_line(tmp_path):
    p = tmp_path / ".env"
    p.write_text("DATA_GO_KR_KEY=abc\nKAKAO_REFRESH_TOKEN=old\n", encoding="utf-8")
    token_store.save_env_file(p, "new")
    assert p.read_text(encoding="utf-8") == "DATA_GO_KR_KEY=abc\nKAKAO_REFRESH_TOKEN=new\n"
    q = tmp_path / ".env2"
    q.write_text("A=1", encoding="utf-8")
    token_store.save_env_file(q, "x")
    assert q.read_text(encoding="utf-8") == "A=1\nKAKAO_REFRESH_TOKEN=x\n"


def test_save_github_secret_encrypts(monkeypatch):
    from nacl import encoding, public
    sk = public.PrivateKey.generate()
    pk = sk.public_key.encode(encoding.Base64Encoder()).decode()
    put = {}
    monkeypatch.setattr(token_store.requests, "get",
                        lambda url, headers, timeout: Resp(200, {"key": pk, "key_id": "kid"}))
    monkeypatch.setattr(token_store.requests, "put",
                        lambda url, headers, timeout, json: put.update(url=url, body=json) or Resp(201, {}))
    token_store.save_github_secret("tiam0405/gwangmyeong-notice", "ghp", "NEWTOKEN")
    assert put["url"].endswith("/repos/tiam0405/gwangmyeong-notice/actions/secrets/KAKAO_REFRESH_TOKEN")
    import base64
    plain = public.SealedBox(sk).decrypt(base64.b64decode(put["body"]["encrypted_value"]))
    assert plain == b"NEWTOKEN" and put["body"]["key_id"] == "kid"
