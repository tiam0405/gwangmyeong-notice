class BaseNotifier:
    """알림 채널. 성공하면 True, 실패하면 False (실패 시 notified_at을 기록하지 않음).

    url: 메시지에 버튼/링크로 붙일 공고 원문 주소 (채널이 지원할 때)
    """

    name = "base"

    def send(self, text: str, url: str | None = None) -> bool:
        raise NotImplementedError
