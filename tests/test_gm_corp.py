from datetime import date
from pathlib import Path

import main
from collectors.gm_corp import is_recruitment, parse_dates, parse_detail, parse_list, to_notice
from filters import SENIOR_TAG, classify

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = main.load_config()


def html(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_list_and_recruitment_filter():
    rows = parse_list(html("gm_corp_list.html"))
    titles = {r["id"]: r["title"] for r in rows}
    assert titles["154"] == "광명제4R구역 재개발 임대주택(행복주택) 일반공급 입주자 모집"
    recruit = [r["id"] for r in rows if is_recruitment(r["title"])]
    assert "154" in recruit and "153" in recruit
    assert "158" not in recruit  # 서류제출 대상자 발표
    assert "170" not in recruit  # 추첨결과


def test_two_digit_year_dates():
    assert parse_dates("`26. 7. 6.(월) 10:00 ~ `26. 7. 8.(수) 17:00") == [date(2026, 7, 6), date(2026, 7, 8)]


def test_detail():
    d = parse_detail(html("gm_corp_detail_154.html"))
    assert d["posted_at"] == date(2026, 6, 26)
    assert (d["apply_start"], d["apply_end"]) == (date(2026, 7, 6), date(2026, 7, 8))  # 청약연습기간 아님
    assert d["address"] == "경기도 광명시 광명2동 88-14번지 일원"
    assert d["target"] == "대학생, 청년, 고령자, 주거급여수급자"
    assert d["apply_method"].startswith("신청장소: 광명도시공사 청약홈페이지(house.gmuc.co.kr)")
    assert "65세 이상" in d["apply_method"]
    assert "모집호수: 총 7호(전용면적 39.939㎡)" in d["summary"]
    assert d["files"][0] == {"name": "1-2 4R 입주자 모집공고.pdf", "kind": "gmuc",
                             "url": "https://house.gmuc.co.kr/jsp/admin/fileDownload.jsp",
                             "form": {"file_id": "100", "detail_file_id": "243"}}


def test_notice_alerts_with_senior_tag():
    row = next(r for r in parse_list(html("gm_corp_list.html")) if r["id"] == "154")
    n = to_notice(row, parse_detail(html("gm_corp_detail_154.html")))
    assert n.housing_type == "행복주택"
    v = classify(n, CONFIG, date(2026, 6, 27))
    assert v.alert and SENIOR_TAG in v.tags
