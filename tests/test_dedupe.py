from datetime import date

import main
from dedupe import similar
from models import Notice
from store import Store

CONFIG = main.load_config()


def n(source, sid, title, posted=date(2026, 6, 26), **kw):
    return Notice(source=source, source_id=sid, title=title, url="u", posted_at=posted,
                  region="경기도 광명시", raw={"signgu": "광명시"}, **kw)


def test_similar_titles():
    assert similar("광명제4R구역 재개발 임대주택(행복주택) 일반공급 입주자 모집",
                   "광명도시공사 광명제4R구역 재개발 임대주택(행복주택) 일반공급 입주자 모집 공고")
    # 1R과 4R은 다른 공고
    assert not similar("광명제4R구역 재개발 임대주택(행복주택) 일반공급 입주자 모집",
                       "광명도시공사 광명제1R구역 재개발 임대주택(행복주택) 일반공급 입주자 모집 공고")


def test_city_repost_not_alerted_original_is(tmp_path):
    store = Store(tmp_path / "notices.json")
    city = n("gm_city", "bbs-1", "광명도시공사 광명제4R구역 재개발 임대주택(행복주택) 일반공급 입주자 모집 공고")
    corp = n("gm_corp", "154", "광명제4R구역 재개발 임대주택(행복주택) 일반공급 입주자 모집")
    main.process([city, corp], store, CONFIG, date(2026, 6, 27))  # 시청 글이 먼저 들어와도
    assert store.get("gm_corp:154")["alert"] is True
    rec = store.get("gm_city:bbs-1")
    assert rec["alert"] is False and rec["duplicate_of"] == "gm_corp:154"


def test_repost_of_already_stored_notice(tmp_path):
    store = Store(tmp_path / "notices.json")
    main.process([n("gm_corp", "154", "광명제4R구역 재개발 임대주택(행복주택) 일반공급 입주자 모집")],
                 store, CONFIG, date(2026, 6, 26))
    store.mark_notified("gm_corp:154")
    city = n("gm_city", "bbs-1", "광명도시공사 광명제4R구역 재개발 임대주택(행복주택) 일반공급 입주자 모집 공고",
             posted=date(2026, 6, 30))
    main.process([city], store, CONFIG, date(2026, 6, 30))
    assert store.pending_notifications() == []


def test_map_url_saved_only_for_precise_address(tmp_path):
    store = Store(tmp_path / "notices.json")
    a = n("gm_corp", "1", "광명 A 행복주택 입주자 모집", address="경기도 광명시 하안로 60")
    b = n("gm_corp", "2", "광명 B 행복주택 입주자 모집", address="경기도 광명시 광명2동 88-14번지 일원")
    main.process([a, b], store, CONFIG, date(2026, 6, 27))
    assert store.get("gm_corp:1")["map_url"].startswith("https://map.naver.com/p/search/")
    assert store.get("gm_corp:2")["map_url"] is None


def test_far_apart_dates_not_duplicate(tmp_path):
    store = Store(tmp_path / "notices.json")
    a = n("gm_corp", "1", "광명소하 행복주택 입주자 모집", posted=date(2026, 1, 1))
    b = n("gm_city", "x", "광명소하 행복주택 입주자 모집 공고 알림", posted=date(2026, 6, 1))
    main.process([a, b], store, CONFIG, date(2026, 6, 2))
    assert store.get("gm_city:x")["alert"] is True


def test_same_source_correction(tmp_path):
    store = Store(tmp_path / "notices.json")
    orig = n("lh", "1", "[경기남부] 광명 매입임대주택 예비입주자 모집공고")
    corr = n("lh", "2", "[정정공고][경기남부] 광명 매입임대주택 예비입주자 모집공고")
    sibling = n("lh", "3", "[경기남부] 광명 매입임대주택Ⅱ 예비입주자 모집공고")
    main.process([corr, orig, sibling], store, CONFIG, date(2026, 6, 27))
    assert store.get("lh:1")["alert"] is True
    assert store.get("lh:2")["alert"] is False
    assert store.get("lh:3")["alert"] is True  # 같은 소스의 비슷한 별개 공고는 중복 아님
