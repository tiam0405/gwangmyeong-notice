from __future__ import annotations

import logging
import time

import requests

from models import Notice

log = logging.getLogger(__name__)


class BaseCollector:
    """소스별 수집기. fetch()는 해당 소스의 공고를 Notice 목록으로 돌려준다."""

    name = "base"

    def __init__(self, config: dict):
        self.config = config
        crawl = config.get("crawl", {})
        self.min_interval = crawl.get("min_interval_sec", 1.0)
        self.max_retries = crawl.get("max_retries", 3)
        self.timeout = crawl.get("timeout_sec", 30)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = crawl.get("user_agent", "gwangmyeong-notice")
        self._last_request = 0.0

    def fetch(self) -> list[Notice]:
        raise NotImplementedError

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """호출 간격 유지 + 최대 max_retries회 재시도."""
        for attempt in range(1, self.max_retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                log.warning("%s %s 실패 (%d/%d): %s", self.name, url, attempt, self.max_retries, e)
                if attempt == self.max_retries:
                    raise
                time.sleep(2 ** attempt)
        raise AssertionError("unreachable")
