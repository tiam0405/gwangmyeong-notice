"""갱신된 카카오 리프레시 토큰 저장.

- GitHub Actions: 저장소 Secret(KAKAO_REFRESH_TOKEN)을 GitHub API로 덮어쓴다
  (GH_SECRETS_TOKEN: 이 저장소의 Secrets 쓰기 권한만 가진 fine-grained 토큰)
- 로컬: .env 파일의 해당 줄을 바꾼다
"""
from __future__ import annotations

import base64
import logging
import os
import re
from pathlib import Path

import requests

log = logging.getLogger(__name__)

SECRET_NAME = "KAKAO_REFRESH_TOKEN"
API = "https://api.github.com/repos/{repo}/actions/secrets"


def _encrypt(public_key_b64: str, value: str) -> str:
    from nacl import encoding, public
    key = public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder())
    return base64.b64encode(public.SealedBox(key).encrypt(value.encode())).decode()


def save_github_secret(repo: str, token: str, value: str, name: str = SECRET_NAME) -> None:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    key = requests.get(f"{API.format(repo=repo)}/public-key", headers=headers, timeout=30)
    key.raise_for_status()
    k = key.json()
    resp = requests.put(f"{API.format(repo=repo)}/{name}", headers=headers, timeout=30,
                        json={"encrypted_value": _encrypt(k["key"], value), "key_id": k["key_id"]})
    resp.raise_for_status()


def save_env_file(path: Path, value: str, name: str = SECRET_NAME) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    line = f"{name}={value}"
    if re.search(rf"^{name}=.*$", text, re.M):
        text = re.sub(rf"^{name}=.*$", lambda _: line, text, flags=re.M)
    else:
        text = text.rstrip("\n") + ("\n" if text else "") + line + "\n"
    path.write_text(text, encoding="utf-8")


def save_refresh_token(value: str, env_path: Path) -> None:
    os.environ[SECRET_NAME] = value
    if os.environ.get("GITHUB_ACTIONS") == "true":
        repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GH_SECRETS_TOKEN")
        if not token:
            log.error("GH_SECRETS_TOKEN이 없어 갱신된 카카오 토큰을 저장하지 못했습니다. "
                      "약 1개월 안에 tools/kakao_auth.py로 다시 로그인해야 합니다")
            return
        save_github_secret(repo, token, value)
        log.info("GitHub Secret %s 갱신 완료", SECRET_NAME)
    else:
        save_env_file(env_path, value)
        log.info(".env의 %s 갱신 완료", SECRET_NAME)
