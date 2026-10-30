"""카카오톡 "나에게 보내기".

환경변수 (GitHub Secrets):
    KAKAO_REST_API_KEY     앱 REST API 키
    KAKAO_CLIENT_SECRET    클라이언트 시크릿 (기본 활성화)
    KAKAO_REFRESH_TOKEN    처음 한 번 로그인해서 받은 리프레시 토큰 (tools/kakao_auth.py)

- 실행할 때마다 리프레시 토큰으로 액세스 토큰(약 12시간)을 새로 받는다
- 리프레시 토큰(약 2개월)은 만료 1개월 전부터 갱신 시 새 값이 온다 → on_new_refresh_token으로 저장
- 텍스트 템플릿 본문은 최대 200자, 버튼 링크 도메인은 앱의 [제품 링크 관리]에 등록돼 있어야 열린다
"""
from __future__ import annotations

import json
import logging
import os
from typing import Callable

import requests

from notifiers.base import BaseNotifier

log = logging.getLogger(__name__)

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
TEXT_LIMIT = 200


class KakaoAuthError(RuntimeError):
    pass


def refresh_tokens(rest_key: str, secret: str | None, refresh_token: str) -> dict:
    data = {"grant_type": "refresh_token", "client_id": rest_key, "refresh_token": refresh_token}
    if secret:
        data["client_secret"] = secret
    resp = requests.post(TOKEN_URL, data=data, timeout=30)
    body = resp.json() if resp.content else {}
    if not resp.ok or "access_token" not in body:
        # 토큰 값은 남기지 않고 오류 코드만
        raise KakaoAuthError(f"카카오 토큰 갱신 실패 ({resp.status_code}): "
                             f"{body.get('error')} {body.get('error_description', '')}")
    return body


class KakaoNotifier(BaseNotifier):
    name = "kakao"

    def __init__(self, access_token: str):
        self.access_token = access_token

    @classmethod
    def from_env(cls, on_new_refresh_token: Callable[[str], None] | None = None) -> "KakaoNotifier | None":
        key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
        refresh = os.environ.get("KAKAO_REFRESH_TOKEN", "").strip()
        if not key or not refresh:
            return None
        tokens = refresh_tokens(key, os.environ.get("KAKAO_CLIENT_SECRET", "").strip() or None, refresh)
        if tokens.get("refresh_token") and on_new_refresh_token:
            log.info("카카오 리프레시 토큰이 갱신되어 저장합니다")
            on_new_refresh_token(tokens["refresh_token"])
        return cls(tokens["access_token"])

    def send(self, text: str, url: str | None = None) -> bool:
        if len(text) > TEXT_LIMIT:
            text = text[: TEXT_LIMIT - 1] + "…"
        template = {"object_type": "text", "text": text,
                    "link": {"web_url": url or "", "mobile_web_url": url or ""}}
        if url:
            template["button_title"] = "공고 보기"
        try:
            resp = requests.post(SEND_URL, timeout=30,
                                 headers={"Authorization": f"Bearer {self.access_token}"},
                                 data={"template_object": json.dumps(template, ensure_ascii=False)})
        except requests.RequestException as e:
            log.warning("카카오 전송 오류: %s", e)
            return False
        if resp.ok and resp.json().get("result_code") == 0:
            return True
        log.error("카카오 전송 실패 status=%s: %s", resp.status_code, resp.text[:200])
        return False
