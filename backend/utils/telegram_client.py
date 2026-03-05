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

    def get_groups(self):
        """Fetch group chats from recent updates.

        Calls getUpdates and extracts unique
        group/supergroup chats the bot has seen.
        Returns list of {id, title, type}.
        """
        resp = requests.get(
            f"{self.base_url}/getUpdates",
            timeout=10,
        )
        if not resp.ok:
            raise TelegramSendError(
                f"Telegram API error "
                f"{resp.status_code}: "
                f"{resp.text}"
            )
        results = resp.json().get("result", [])
        seen = {}
        for update in results:
            msg = (
                update.get("message")
                or update.get("my_chat_member", {})
                .get("chat")
            )
            if not msg:
                continue
            chat = msg.get("chat") or msg
            chat_type = chat.get("type", "")
            if chat_type not in (
                "group",
                "supergroup",
            ):
                continue
            chat_id = str(chat.get("id"))
            if chat_id not in seen:
                seen[chat_id] = {
                    "id": chat_id,
                    "title": chat.get(
                        "title", "Untitled"
                    ),
                    "type": chat_type,
                }
        return list(seen.values())

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
