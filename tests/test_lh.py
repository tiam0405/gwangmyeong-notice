import json
from datetime import date
from pathlib import Path

import main
from collectors.lh import parse_detail, parse_list, region_from_address, to_notice
from collectors.myhome import parse_response, rows_to_notices
from filters import classify

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = main.load_config()


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def gwacheon():
    rows = parse_list(load("lh_list_gyeonggi.json"))
    row = next(r for r in rows if r["PAN_ID"] == "2015122300020960")
    return to_notice(row, parse_detail(load("lh_detail_sample.json")))


def test_list_parsed():
    rows = parse_list(load("lh_list_gyeonggi.json"))
    assert len(rows) == 19
    assert {"PAN_ID", "PAN_NM", "DTL_URL", "SPL_INF_TP_CD"} <= rows[0].keys()


def test_detail_drops_label_datasets():
    detail = parse_detail(load("lh_detail_sample.json"))
    assert "dsSbd" in detail and "dsSbdNm" not in detail and "dsSch" not in detail


def test_notice_from_detail():
    n = gwacheon()
    assert n.key == "lh:2015122300020960"
    assert n.apply_start == date(2026, 11, 10)
    assert n.apply_end == date(2026, 11, 12)
    assert n.address == "경기도 과천시 갈현동 581-1"
    assert n.region == "경기도 과천시 갈현동"
    assert n.raw["signgu"] == "과천시"
    assert "LH청약플러스" in n.apply_method
    assert "불이익" not in n.apply_method and "견본주택" not in n.apply_method
    assert "총 1,424세대" in n.summary
    assert any(a["kind"] == "공고문(PDF)" for a in n.attachments)


def test_list_only_notice_without_detail():
    row = parse_list(load("lh_list_gyeonggi.json"))[5]  # 접수마감 공고
    n = to_notice(row, {})
    assert n.apply_start is None and n.apply_end is not None
    assert n.region == "경기도" and n.address is None


def test_region_from_address():
    assert region_from_address("경기도 광명시 하안동 1-2") == ("경기도 광명시 하안동", "광명시")


def test_myhome_and_lh_merged_into_one():
    myhome = rows_to_notices(parse_response(load("myhome_gyeonggi.json"))[0])
    lh = gwacheon()
    merged = main.merge_notices(myhome + [lh])
    same = [n for n in merged if n.key == lh.key]
    assert len(same) == 1
    n = same[0]
    assert n.raw["pblanc_id"] == "21483"            # 마이홈 정보 유지
    assert "LH청약플러스" in n.apply_method          # 비어 있던 신청방법은 LH로 채움
    assert n.attachments


def test_north_gyeonggi_is_not_gwangmyeong():
    n = to_notice(parse_list(load("lh_list_gyeonggi.json"))[0], {})
    n.title = "[경기북부] 2026년 하반기 일반 매입임대주택 입주자 모집공고"
    assert not classify(n, CONFIG).keep


def test_correction_title_normalized():
    from filters import is_correction, normalize_title
    a = "[경기남부] 든든전세 매입임대주택 예비입주자 모집공고(비분양전환)"
    b = "[정정공고][경기남부] 든든전세 매입임대주택 예비입주자 모집공고(비분양전환)"
    assert is_correction(b) and not is_correction(a)
    assert normalize_title(a) == normalize_title(b)


def test_closed_notice_not_alerted():
    n = gwacheon()
    n.title = "광명하안 행복주택 고령자 입주자 모집"
    assert classify(n, CONFIG, date(2026, 11, 1)).alert
    v = classify(n, CONFIG, date(2026, 11, 13))
    assert v.keep and not v.alert and v.reason == "접수 마감"
