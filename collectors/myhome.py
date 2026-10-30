from collectors.base import BaseCollector
from models import Notice


class MyHomeCollector(BaseCollector):
    """마이홈포털 공공주택 모집공고 API (단계 4)"""

    name = "myhome"

    def fetch(self) -> list[Notice]:
        raise NotImplementedError
