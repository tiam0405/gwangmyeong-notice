from notifiers.base import BaseNotifier


class TelegramNotifier(BaseNotifier):
    """텔레그램 봇 발송. TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS(쉼표 구분) 환경변수 사용 (단계 8)."""

    name = "telegram"

    def send(self, text: str) -> bool:
        raise NotImplementedError
