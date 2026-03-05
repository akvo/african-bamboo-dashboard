import logging

import requests

logger = logging.getLogger(__name__)


class TelegramSendError(Exception):
    """Raised when Telegram API returns non-OK."""


class TelegramClient:
    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = self.BASE_URL.format(
            token=bot_token
        )

    def send_message(
        self, chat_id, text, parse_mode="Markdown"
    ):
        """Send message to a Telegram chat.

        Returns message_id on success.
        Raises TelegramSendError on failure.
        """
        resp = requests.post(
            f"{self.base_url}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            },
            timeout=10,
        )
        if not resp.ok:
            raise TelegramSendError(
                f"Telegram API error "
                f"{resp.status_code}: "
                f"{resp.text}"
            )
        return resp.json()["result"][
            "message_id"
        ]
