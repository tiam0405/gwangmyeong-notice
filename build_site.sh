#!/usr/bin/env sh
# GitHub Pages에 올릴 정적 화면 만들기: web/ + data/notices.json + 확인 시각(UTC, 화면에서 한국 시간으로 표시)
set -e
rm -rf _site
mkdir -p _site/data
cp -r web/. _site/
cp data/notices.json _site/data/
printf '{"checked_at": "%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > _site/data/status.json

# 브라우저가 예전 app.js/style.css를 계속 쓰지 않도록 배포마다 버전을 붙인다
v=$(date -u +%Y%m%d%H%M%S)
sed -i.bak -e "s|href=\"style.css\"|href=\"style.css?v=$v\"|" -e "s|src=\"app.js\"|src=\"app.js?v=$v\"|" _site/index.html
rm -f _site/index.html.bak
