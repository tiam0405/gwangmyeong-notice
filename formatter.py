"""notices.json 레코드 → 알림 문구 (templates/*.j2)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from filters import CHECK_TAG, SENIOR_TAG, WIDE_TAG

TEMPLATES = Path(__file__).parent / "templates"
LONG_LIMIT = 4096  # 긴 메시지 상한 (웹·기록용)
KAKAO_LIMIT = 200
LMS_LIMIT_BYTES = 2000
WEEKDAYS = "월화수목금토일"
BADGES = {"lh": "LH", "gh": "GH", "gm_corp": "광명도시공사", "gm_city": "광명시청"}
TAG_ICONS = {SENIOR_TAG: "👵", CHECK_TAG: "❓", WIDE_TAG: "🌐"}


def kdate(value) -> str:
    """'2026-11-10' → '2026-11-10(화)'. 없으면 '?'."""
    if not value:
        return "?"
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return f"{d.isoformat()}({WEEKDAYS[d.weekday()]})"


def sdate(value) -> str:
    """'2026-11-10' → '11/10(화)' (카톡처럼 짧은 메시지용)"""
    if not value:
        return "?"
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return f"{d.month}/{d.day}({WEEKDAYS[d.weekday()]})"


_env = Environment(loader=FileSystemLoader(TEMPLATES), trim_blocks=True, lstrip_blocks=True,
                   keep_trailing_newline=False, autoescape=False)
_env.filters["kdate"] = kdate
_env.filters["sdate"] = sdate
_env.globals["tag_icon"] = lambda tag: TAG_ICONS.get(tag, "🏷️")


def badge(record: dict) -> str:
    return BADGES.get(record["source"]) or record.get("institution") or "공고"


def content_lines(record: dict) -> list[str]:
    lines = []
    if record.get("summary"):
        lines += [ln for ln in record["summary"].splitlines() if ln.strip()]
    elif record.get("housing_type"):
        lines.append(record["housing_type"])
    if record.get("target"):
        lines.append(f"대상: {record['target']}")
    return lines


def _fit(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_new(record: dict) -> str:
    text = _env.get_template("message.j2").render(n=record, badge=badge(record),
                                                  content=content_lines(record))
    return _fit(text.strip(), LONG_LIMIT)


def render_reminder(record: dict, today: date) -> str:
    days = (date.fromisoformat(record["apply_end"]) - today).days
    d_day = "오늘" if days == 0 else f"D-{days}"
    return _fit(_env.get_template("reminder.j2").render(n=record, d_day=d_day).strip(), LONG_LIMIT)


def render_short(record: dict) -> str:
    text = _env.get_template("message_short.j2").render(n=record, badge=badge(record)).strip()
    while len(text.encode("utf-8")) > LMS_LIMIT_BYTES:
        text = text[:-2] + "…"
    return text


def _render_short(template: str, record: dict, limit: int, **ctx) -> str:
    """limit 글자 안에 들어가도록 제목부터 줄인다."""
    title = record["title"]
    while True:
        text = _env.get_template(template).render(n=record, title=title, **ctx).strip()
        if len(text) <= limit or len(title) <= 10:
            return _fit(text, limit)
        title = title[: len(title) - (len(text) - limit) - 1].rstrip() + "…"


def render_kakao(record: dict) -> str:
    return _render_short("kakao.j2", record, KAKAO_LIMIT, badge=badge(record))


def render_kakao_reminder(record: dict, today: date) -> str:
    days = (date.fromisoformat(record["apply_end"]) - today).days
    return _render_short("kakao_reminder.j2", record, KAKAO_LIMIT,
                         d_day="오늘" if days == 0 else f"D-{days}")
