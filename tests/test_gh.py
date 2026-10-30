from datetime import date
from pathlib import Path

import main
from collectors.gh import parse_detail, parse_list, to_notice
from filters import SENIOR_TAG, classify

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = main.load_config()


def html(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_list_rows():
    rows = parse_list(html("gh_list_all.html"), "sr7150")
    assert len(rows) == 10
    r = rows[0]
    assert r["id"] == "sr7150-839"
    assert r["title"] == "'26년 하반기 경기행복주택 예비입주자 추가모집 공고"
    assert r["region"] == "성남시"
    assert r["posted_at"] == date(2026, 10, 16) and r["end"] == date(2026, 10, 28)
    assert r["status"] == "접수마감"


def test_list_without_deadline():
    rows = parse_list(html("gh_list_maeip.html"), "sr7155")
    no_end = next(r for r in rows if r["pbanc_no"] == "812")
    assert no_end["end"] is None and no_end["region"] == "경기도"


def test_gwangmyeong_area_list():
    rows = parse_list(html("gh_list_gwangmyeong.html"), "sr7150")
    assert [r["pbanc_no"] for r in rows] == ["570", "203", "175"]
    assert all(r["region"] == "광명시" for r in rows)


def test_multi_complex_detail():
    d = parse_detail(html("gh_detail_839.html"))
    assert len(d["complexes"]) >= 20
    assert d["complexes"][0] == {"name": "안양관양 경기행복주택",
                                 "address": "경기도 안양시 동안구 관양동 1498-21 안양관양 행복주택"}
    assert d["apply_start"] == date(2026, 10, 26) and d["apply_end"] == date(2026, 10, 28)
    assert "고령자" in d["targets"] and "청년" in d["targets"]
    assert any(f.endswith(".pdf") for f in d["files"])


def test_multi_complex_without_gwangmyeong_dropped_even_if_title_vague():
    row = parse_list(html("gh_list_all.html"), "sr7150")[0]
    n = to_notice(row, parse_detail(html("gh_detail_839.html")))
    assert n.region == "경기도 (여러 지역)"
    v = classify(n, CONFIG)
    assert not v.keep and "단지" in v.reason


def test_multi_complex_with_gwangmyeong_alerts_with_senior_tag():
    row = parse_list(html("gh_list_all.html"), "sr7150")[0]
    d = parse_detail(html("gh_detail_839.html"))
    d["complexes"].append({"name": "광명소하 경기행복주택", "address": "경기도 광명시 소하동 1"})
    v = classify(to_notice(row, d), CONFIG)
    assert v.keep and v.alert and SENIOR_TAG in v.tags  # 주택형에 "고령자" 있음


def test_no_deadline_notice_goes_stale():
    row = next(r for r in parse_list(html("gh_list_maeip.html"), "sr7155") if r["pbanc_no"] == "812")
    n = to_notice(row, {})  # 2026-08-21 게시, 마감일 없음
    assert classify(n, CONFIG, date(2026, 9, 1)).alert
    v = classify(n, CONFIG, date(2026, 10, 30))
    assert v.keep and not v.alert and "마감일 없음" in v.reason


def test_maeip_region_text():
    d = parse_detail(html("gh_detail_maeip_795.html"))
    assert d["complexes"] == []
    assert "고양" in d["region_text"] and "화성" in d["region_text"]
    assert d["apply_start"] == date(2026, 6, 30) and d["apply_end"] == date(2026, 7, 3)
    assert d["notes"][0].startswith("※ 신청방법")
    row = next(r for r in parse_list(html("gh_list_maeip.html"), "sr7155") if r["pbanc_no"] == "795")
    v = classify(to_notice(row, d), CONFIG)
    assert not v.keep  # 모집지역에 광명 없음
