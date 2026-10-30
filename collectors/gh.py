from collectors.base import BaseCollector
from models import Notice


class GHCollector(BaseCollector):
    """GH 청약센터 apply.gh.or.kr 임대 목록 (단계 4)"""

    name = "gh"

    def fetch(self) -> list[Notice]:
        raise NotImplementedError
