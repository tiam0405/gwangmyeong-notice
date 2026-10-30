from datetime import date

from enrich.apply_guide import ATTACHMENT_NOTE, DEFAULT, build
from models import Notice


def n(**kw):
    return Notice(source="lh", source_id="1", title="t", url="u", posted_at=date(2026, 1, 1), **kw)


def test_structured_field_used_as_is():
    g = build(n(apply_method="신청장소: 행정복지센터", institution="광명시청 통합돌봄과"))
    assert g == "신청장소: 행정복지센터"


def test_institution_template():
    assert "apply.lh.or.kr" in build(n(institution="LH"))
    assert "apply.gh.or.kr" in build(n(institution="GH"))
    assert "house.gmuc.co.kr" in build(n(institution="광명도시공사"))


def test_unknown_institution_points_to_original():
    assert build(n(institution="광명시청 복지정책과")) == DEFAULT


def test_attachment_note():
    g = build(n(institution="LH", attachments=[{"name": "공고문.pdf"}]))
    assert g.endswith(ATTACHMENT_NOTE)


def test_long_text_trimmed():
    g = build(n(apply_method="\n".join(f"{i}번째 줄" for i in range(10))))
    assert len(g.splitlines()) == 5
