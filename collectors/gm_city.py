from collectors.base import BaseCollector
from models import Notice


class GmCityCollector(BaseCollector):
    """광명시청 고시공고·공지사항 (단계 4)"""

    name = "gm_city"

    def fetch(self) -> list[Notice]:
        raise NotImplementedError
