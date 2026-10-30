from collectors.base import BaseCollector
from models import Notice


class GmCorpCollector(BaseCollector):
    """광명도시공사 청약센터 house.gmuc.co.kr (단계 4)"""

    name = "gm_corp"

    def fetch(self) -> list[Notice]:
        raise NotImplementedError
