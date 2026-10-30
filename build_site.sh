#!/usr/bin/env sh
# GitHub Pages에 올릴 정적 화면 만들기: web/ + data/notices.json + 확인 시각(UTC, 화면에서 한국 시간으로 표시)
set -e
rm -rf _site
mkdir -p _site/data
cp -r web/. _site/
cp data/notices.json _site/data/
printf '{"checked_at": "%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > _site/data/status.json
