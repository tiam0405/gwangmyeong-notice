"""카카오 첫 로그인 (PC에서 한 번만 실행).

    .venv\\Scripts\\python tools\\kakao_auth.py

1. 브라우저가 열리면 카카오 로그인 → "카카오톡 메시지 전송" 동의
2. http://localhost:8765/callback 으로 돌아오면 토큰을 받아 .env에 KAKAO_REFRESH_TOKEN 저장
3. 확인 메시지를 내 카톡으로 한 번 보낸다

.env에 KAKAO_REST_API_KEY(, KAKAO_CLIENT_SECRET)가 먼저 있어야 한다.
"""
from __future__ import annotations

import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from notifiers.kakao import TOKEN_URL, KakaoNotifier  # noqa: E402
from notifiers.token_store import save_env_file  # noqa: E402

REDIRECT_URI = "http://localhost:8765/callback"


class Handler(BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        Handler.code = q.get("code", [None])[0]
        Handler.error = q.get("error_description", q.get("error", [None]))[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "완료되었습니다. 이 창을 닫고 VS Code로 돌아가세요." if Handler.code else f"실패: {Handler.error}"
        self.wfile.write(f"<h2>{msg}</h2>".encode())

    def log_message(self, *args):
        pass


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    env_path = ROOT / ".env"
    load_dotenv(env_path)
    key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    secret = os.environ.get("KAKAO_CLIENT_SECRET", "").strip()
    if not key:
        sys.exit(".env에 KAKAO_REST_API_KEY가 없습니다")

    url = "https://kauth.kakao.com/oauth/authorize?" + urlencode({
        "response_type": "code", "client_id": key, "redirect_uri": REDIRECT_URI, "scope": "talk_message",
    })
    print("브라우저에서 카카오 로그인 후 '카카오톡 메시지 전송'에 동의해 주세요.")
    print("브라우저가 안 열리면 이 주소를 직접 여세요:\n" + url)
    webbrowser.open(url)

    server = HTTPServer(("localhost", 8765), Handler)
    server.timeout = 300
    server.handle_request()  # 콜백 한 번만 받고 종료
    if not Handler.code:
        sys.exit(f"로그인 실패: {Handler.error or '시간 초과'}")

    data = {"grant_type": "authorization_code", "client_id": key,
            "redirect_uri": REDIRECT_URI, "code": Handler.code}
    if secret:
        data["client_secret"] = secret
    resp = requests.post(TOKEN_URL, data=data, timeout=30)
    body = resp.json()
    if "refresh_token" not in body:
        sys.exit(f"토큰 발급 실패: {body.get('error')} {body.get('error_description', '')}")

    save_env_file(env_path, body["refresh_token"])
    print(".env에 KAKAO_REFRESH_TOKEN을 저장했습니다.")
    ok = KakaoNotifier(body["access_token"]).send(
        "✅ 광명 임대공고 알림이 연결되었습니다.", "https://tiam0405.github.io/gwangmyeong-notice/")
    print("카톡 확인 메시지 전송:", "성공" if ok else "실패 (앱 설정의 동의항목·도메인 확인)")


if __name__ == "__main__":
    main()
