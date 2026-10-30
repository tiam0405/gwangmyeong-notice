from collectors.base import BaseCollector
from models import Notice


class LHCollector(BaseCollector):
    """LH 분양임대공고 목록·상세 API (단계 4)"""

    name = "lh"

    def fetch(self) -> list[Notice]:
        raise NotImplementedError
