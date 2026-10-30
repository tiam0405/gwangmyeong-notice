from datetime import date

import formatter
from filters import CHECK_TAG, SENIOR_TAG


def rec(**kw):
    base = {
        "key": "gm_corp:1", "source": "gm_corp", "title": "광명 행복주택 입주자 모집",
        "url": "https://example.com/1", "posted_at": "2026-11-03", "apply_start": "2026-11-10",
        "apply_end": "2026-11-13", "region": "경기도 광명시 하안동", "address": None,
        "map_url": None, "housing_type": "행복주택", "target": None, "summary": None,
        "apply_method": "광명도시공사 청약센터(house.gmuc.co.kr)에서 신청", "institution": "광명도시공사",
        "tags": [],
    }
    return base | kw


def test_full_message():
    text = formatter.render_new(rec(map_url="https://map.naver.com/p/search/x", tags=[SENIOR_TAG],
                                    summary="총 120세대", target="고령자"))
    assert text.startswith("📢 [광명도시공사] 광명 행복주택 입주자 모집\n👵 고령자 해당 가능")
    assert "🗺️ 지도: https://map.naver.com/p/search/x" in text
    assert "🏠 내용: 총 120세대\n   대상: 고령자" in text
    assert "📅 공고일: 2026-11-03(화)" in text
    assert "⏰ 접수: 2026-11-10(화) ~ 2026-11-13(금)" in text
    assert "- 광명도시공사 청약센터(house.gmuc.co.kr)에서 신청" in text
    assert text.endswith("🔗 공고 원문: https://example.com/1")


def test_missing_values_omit_lines():
    text = formatter.render_new(rec(apply_start=None, apply_end=None, apply_method=None,
                                    housing_type=None, posted_at=None))
    assert "⏰ 접수: 공고문 확인" in text
    for absent in ("🗺️", "🏠", "📅", "📝", "None", "?"):
        assert absent not in text


def test_check_tag_icon():
    assert f"❓ {CHECK_TAG}" in formatter.render_new(rec(tags=[CHECK_TAG]))


def test_badge_for_lh_and_city():
    assert formatter.render_new(rec(source="lh")).startswith("📢 [LH]")
    assert formatter.render_new(rec(source="gm_city", institution="광명시청 주택과")).startswith("📢 [광명시청]")


def test_reminder():
    text = formatter.render_reminder(rec(), date(2026, 11, 12))
    assert text.startswith("⏰ [마감 D-1] 광명 행복주택 입주자 모집")
    assert "접수 마감: 2026-11-13(금)" in text
    assert formatter.render_reminder(rec(), date(2026, 11, 13)).startswith("⏰ [마감 오늘]")


def test_long_limit():
    text = formatter.render_new(rec(apply_method="가" * 5000))
    assert len(text) <= formatter.LONG_LIMIT


def test_short_version_fits_lms():
    text = formatter.render_short(rec(title="광" * 1500))
    assert len(text.encode("utf-8")) <= formatter.LMS_LIMIT_BYTES
    assert formatter.render_short(rec()).splitlines()[1] == "접수 2026-11-10(화)~2026-11-13(금)"
