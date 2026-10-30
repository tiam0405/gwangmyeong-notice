import copy
import json
from datetime import date
from pathlib import Path

import main
from collectors.myhome import parse_response, rows_to_notices
from filters import CHECK_TAG, SENIOR_TAG, classify

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = main.load_config()


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def gyeonggi_rows():
    items, total = parse_response(load("myhome_gyeonggi.json"))
    assert total == len(items) == 17
    return items


def test_nodata_is_empty():
    assert parse_response(load("myhome_gwangmyeong.json")) == ([], 0)


def test_rows_grouped_by_pblanc_id():
    notices = rows_to_notices(gyeonggi_rows())
    titles = [n.title for n in notices]
    assert len([t for t in titles if "동탄지역 행복주택" in t]) == 1  # 8줄 → 1건
    gwacheon = next(n for n in notices if n.raw["pblanc_id"] == "21483")
    assert gwacheon.key == "lh:2015122300020960"  # LH 공고는 LH 수집기와 같은 key
    assert gwacheon.posted_at == date(2026, 10, 28)
    assert gwacheon.apply_start == date(2026, 11, 10)
    assert gwacheon.apply_end == date(2026, 11, 12)
    assert gwacheon.region == "경기도 과천시 갈현동"
    assert gwacheon.address == "경기도 과천시 갈현동 579-5"
    assert gwacheon.institution == "LH"
    assert "총 1,424호" in gwacheon.summary


def test_non_gwangmyeong_dropped_and_wide_jeonse_kept():
    verdicts = {n.title: classify(n, CONFIG) for n in rows_to_notices(gyeonggi_rows())}
    kept = {t: v for t, v in verdicts.items() if v.keep}
    # 경기도 17줄 중 광명 공고는 없음 → 광역 전세임대 수시모집만 남는다
    assert all("전세임대" in t for t in kept)
    assert len(kept) == 4
    # 청년·신혼·다자녀 대상이라 알림은 모두 제외
    assert not any(v.alert for v in kept.values())
    assert verdicts["과천지식정보타운 S12블록 행복주택 입주자 모집공고"].keep is False


def _gm_row(**kw):
    row = copy.deepcopy(gyeonggi_rows()[0])
    row.update(pblancId="99999", signguNm="광명시", refrnLegaldongNm="하안동",
               fullAdres="경기도 광명시 하안동 1", hsmpNm="광명하안 A단지", **kw)
    return row


def test_gwangmyeong_notice_alerts():
    n = rows_to_notices([_gm_row(pblancNm="광명하안 영구임대주택 예비입주자 모집", suplyTyNm="영구임대")])[0]
    v = classify(n, CONFIG)
    assert v.keep and v.alert
    assert SENIOR_TAG in v.tags


def test_gwangmyeong_newlywed_only_not_alerted():
    n = rows_to_notices([_gm_row(pblancNm="광명 신혼희망타운 행복주택 입주자 모집")])[0]
    v = classify(n, CONFIG)
    assert v.keep and not v.alert


def test_youth_and_senior_together_alerts():
    n = rows_to_notices([_gm_row(pblancNm="광명 청년·고령자 매입임대 입주자 모집", suplyTyNm="매입임대")])[0]
    assert classify(n, CONFIG).alert


def test_daycare_excluded():
    n = rows_to_notices([_gm_row(pblancNm="광명하안 가정어린이집 운영예정자 모집공고")])[0]
    assert not classify(n, CONFIG).keep


def _wide_row(title, suply="매입임대"):
    row = _gm_row(pblancNm=title, suplyTyNm=suply)
    row.update(signguNm="", refrnLegaldongNm="", fullAdres="", hsmpNm="")
    return row


def test_regional_without_city_asks_to_check():
    n = rows_to_notices([_wide_row("[경기남부] 일반 매입임대주택 입주자 모집 공고")])[0]
    v = classify(n, CONFIG)
    assert v.keep and v.alert
    assert CHECK_TAG in v.tags


def test_regional_naming_other_cities_dropped():
    n = rows_to_notices([_wide_row("[인천지역본부] 일반 매입임대주택 입주자 모집 공고(인천,부천)")])[0]
    assert not classify(n, CONFIG).keep


def test_regional_naming_gwangmyeong_is_confirmed():
    n = rows_to_notices([_wide_row("[경기남부] 매입임대 입주자 모집(안양,광명)")])[0]
    v = classify(n, CONFIG)
    assert v.alert and CHECK_TAG not in v.tags


def test_bucheon_okgil_not_gwangmyeong():
    row = _gm_row(pblancNm="부천옥길 행복주택 입주자 모집")
    row.update(signguNm="부천시", refrnLegaldongNm="옥길동", fullAdres="경기도 부천시 옥길동 1", hsmpNm="부천옥길")
    assert not classify(rows_to_notices([row])[0], CONFIG).keep
