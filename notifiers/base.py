class BaseNotifier:
    """알림 채널. 성공하면 True, 실패하면 False (실패 시 notified_at을 기록하지 않음)."""

    name = "base"

    def send(self, text: str) -> bool:
        raise NotImplementedError
