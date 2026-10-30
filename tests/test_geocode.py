import pytest

from enrich.geocode import map_url, precise_address


@pytest.mark.parametrize("address, expected", [
    ("광명시 하안로 60", "광명시 하안로 60"),
    ("경기도 광명시 하안로 60 하안주공", "경기도 광명시 하안로 60"),
    ("경기도 과천시 갈현동 581-1", "경기도 과천시 갈현동 581-1"),
    ("경기도 과천시 갈현동 579-5 ", "경기도 과천시 갈현동 579-5"),
    ("경기도 안양시 동안구 관양동 1498-21 안양관양 행복주택", "경기도 안양시 동안구 관양동 1498-21"),
    ("경기도 광명시 오리로 123번길 4", "경기도 광명시 오리로 123번길 4"),
    ("광명시 철산동 산 12", "광명시 철산동 산 12"),
])
def test_precise(address, expected):
    assert precise_address(address) == expected


@pytest.mark.parametrize("address", [
    None, "", "광명시", "광명시 하안동", "경기도 광명시 하안동 일원",
    "경기도 광명시 광명2동 88-14번지 일원", "광명시 소하동 1234 외 3필지", "광명시 하안동 일대",
])
def test_vague_has_no_link(address):
    assert map_url(address) is None


def test_naver_link_encoded():
    assert map_url("광명시 하안로 60") == \
        "https://map.naver.com/p/search/%EA%B4%91%EB%AA%85%EC%8B%9C%20%ED%95%98%EC%95%88%EB%A1%9C%2060"
