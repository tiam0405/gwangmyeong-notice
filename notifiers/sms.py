from notifiers.base import BaseNotifier


class SmsNotifier(BaseNotifier):
    """문자 발송 (나중에)."""

    name = "sms"

    def send(self, text: str) -> bool:
        raise NotImplementedError
