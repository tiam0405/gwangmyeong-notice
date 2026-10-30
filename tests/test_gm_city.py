from datetime import date
from pathlib import Path

import main
from collectors.gm_city import is_housing_title, parse_detail, parse_list, parse_period, to_notice
from filters import SENIOR_TAG, classify

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = main.load_config()
CITY = CONFIG["sources"]["gm_city"]


def html(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_nftc_list():
    rows = parse_list(html("gm_city_nftc_list.html"), "nftc")
    r = rows[0]
    assert r["id"] == "66955" and r["title"] == "2026년 광명하안13 영구임대주택 예비입주자 모집"
    assert r["dept"] == "통합돌봄과" and r["posted_at"] == date(2026, 6, 15)


def test_bbs_list_skips_pinned():
    rows = parse_list(html("gm_city_bbs_list.html"), "bbs")
    assert all("생리용품" not in r["title"] for r in rows)
    assert rows[0]["id"] == "20260626173134491" and rows[0]["posted_at"] == date(2026, 6, 26)


def test_title_filter():
    titles = [r["title"] for r in parse_list(html("gm_city_nftc_list.html"), "nftc")]
    kept = [t for t in titles if is_housing_title(t, CITY["search_keywords"], CITY["exclude_keywords"])]
    assert "2026년 광명하안13 영구임대주택 예비입주자 모집" in kept
    assert not any("창업지원센터" in t for t in kept)  # 공용오피스 입주자 모집은 제외


def test_nftc_detail():
    d = parse_detail(html("gm_city_nftc_detail_66955.html"), "nftc")
    # "모집공고일 : 6. 29. ~ 7. 3."은 이름이 접수기간이 아니므로 추측하지 않는다
    assert d["apply_start"] is None and d["apply_end"] is None
    assert "행정복지센터" in d["apply_method"]
    assert any("600호" in s for s in d["summary"])
    assert d["contact"] == "02-2680-6790"
    assert any(f["name"].endswith(".pdf") and f["form"]["sys_file_nm"] for f in d["files"])


def test_senior_notice_alerts():
    row = parse_list(html("gm_city_nftc_list.html"), "nftc")[0]
    n = to_notice(row, parse_detail(html("gm_city_nftc_detail_66955.html"), "nftc"))
    assert n.key == "gm_city:nftc-66955" and "고령자" in n.target
    v = classify(n, CONFIG, date(2026, 6, 16))
    assert v.alert and SENIOR_TAG in v.tags


def test_bbs_detail_files():
    d = parse_detail(html("gm_city_bbs_detail.html"), "bbs")
    assert d["files"][0]["name"] == "1-2. 4R 입주자 모집공고.hwp"
    assert d["files"][0]["url"].startswith("https://www.gm.go.kr/component/file/ND_fileDownload.do")


def test_parse_period_carries_year():
    assert parse_period("2026. 7. 6.(월) 10:00 ~ 7. 8.(수) 17:00") == (date(2026, 7, 6), date(2026, 7, 8))
    assert parse_period("공고문 참조") == (None, None)
