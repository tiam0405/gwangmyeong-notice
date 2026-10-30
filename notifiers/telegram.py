"""텔레그램 봇 발송.

환경변수 (GitHub Secrets):
    TELEGRAM_BOT_TOKEN       봇 토큰
    TELEGRAM_CHAT_IDS        받는 사람 chat_id (여러 명이면 쉼표로)
    TELEGRAM_ADMIN_CHAT_ID   오류 알림 받을 chat_id (없으면 첫 번째 받는 사람)
"""
from __future__ import annotations

import logging
import os
import time

import requests

from notifiers.base import BaseNotifier

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/sendMessage"
SEND_INTERVAL = 1.1  # 같은 채팅에 초당 1건 제한


class TelegramNotifier(BaseNotifier):
    name = "telegram"

    def __init__(self, token: str, chat_ids: list[str]):
        self.token = token
        self.chat_ids = chat_ids
        self._last = 0.0

    @classmethod
    def from_env(cls, admin: bool = False) -> "TelegramNotifier | None":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        ids = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]
        if admin:
            admin_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "").strip()
            ids = [admin_id] if admin_id else ids[:1]
        if not token or not ids:
            return None
        return cls(token, ids)

    def send(self, text: str) -> bool:
        """모든 받는 사람에게 보내졌을 때만 True."""
        return all(self._send_one(chat_id, text) for chat_id in self.chat_ids)

    def _send_one(self, chat_id: str, text: str) -> bool:
        for attempt in range(3):
            wait = SEND_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = requests.post(API.format(token=self.token), timeout=30, json={
                    "chat_id": chat_id, "text": text, "disable_web_page_preview": True,
                })
            except requests.RequestException as e:
                # 오류 문구에 URL(토큰 포함)이 들어갈 수 있어 가린다
                log.warning("텔레그램 전송 오류 (%d/3): %s", attempt + 1,
                            str(e).replace(self.token, "***"))
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 429:  # 너무 빠름 → 안내된 시간만큼 기다렸다가 재시도
                time.sleep(resp.json().get("parameters", {}).get("retry_after", 5))
                continue
            if resp.ok and resp.json().get("ok"):
                return True
            # 토큰은 로그에 남기지 않는다
            log.error("텔레그램 전송 실패 chat=%s status=%s: %s",
                      chat_id, resp.status_code, resp.text[:200])
            return False
        return False
