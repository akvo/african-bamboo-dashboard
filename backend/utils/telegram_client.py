import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10


class TelegramSendError(Exception):
    """Raised when a Telegram API call does not succeed.

    Covers transport faults (DNS failure, connection
    reset, timeout) as well as non-OK responses, so
    callers have exactly one exception type to handle.
    Letting a bare requests exception escape is what
    previously killed the notification task outright.
    """

    def __init__(
        self,
        message,
        retry_after=None,
        migrate_to_chat_id=None,
    ):
        super().__init__(message)
        # Telegram returns both of these inside the
        # "parameters" object of an error body.
        self.retry_after = retry_after
        self.migrate_to_chat_id = migrate_to_chat_id


class TelegramClient:
    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(
        self, bot_token, timeout=DEFAULT_TIMEOUT
    ):
        self.bot_token = bot_token
        self.timeout = timeout
        self.base_url = self.BASE_URL.format(
            token=bot_token
        )

    def _request(self, method, path, **kwargs):
        """Perform one API call, normalising failures.

        Every failure mode -- transport, HTTP status,
        and an ok=false body on HTTP 200 -- leaves this
        method as TelegramSendError.
        """
        try:
            resp = requests.request(
                method,
                f"{self.base_url}/{path}",
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as e:
            raise TelegramSendError(
                f"Telegram request failed: {e}"
            ) from e

        try:
            payload = resp.json()
        except ValueError:
            payload = {}

        if not resp.ok or not payload.get("ok"):
            params = payload.get("parameters") or {}
            description = (
                payload.get("description") or resp.text
            )
            raise TelegramSendError(
                f"Telegram API error "
                f"{resp.status_code}: {description}",
                retry_after=params.get("retry_after"),
                migrate_to_chat_id=params.get(
                    "migrate_to_chat_id"
                ),
            )
        return payload.get("result")

    def get_groups(self):
        """Discover group chats from recent updates.

        getUpdates only sees the last 24h of activity
        and a bot's own messages generate no updates, so
        this is for DISCOVERY only. Use get_chat to
        resolve a chat id that is already configured.
        """
        results = (
            self._request("GET", "getUpdates") or []
        )
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

    def get_chat(self, chat_id):
        """Resolve a chat's title from its id.

        Authoritative and permanent, unlike getUpdates
        which empties itself after a quiet day.
        """
        chat = (
            self._request(
                "GET",
                "getChat",
                params={"chat_id": chat_id},
            )
            or {}
        )
        return {
            "id": str(chat.get("id", chat_id)),
            "title": chat.get("title", "Untitled"),
            "type": chat.get("type", ""),
        }

    def send_message(
        self, chat_id, text, parse_mode="HTML"
    ):
        """Send message to a Telegram chat.

        Returns message_id on success.
        Raises TelegramSendError on any failure.
        """
        body = {"chat_id": chat_id, "text": text}
        if parse_mode:
            body["parse_mode"] = parse_mode
        result = (
            self._request(
                "POST", "sendMessage", json=body
            )
            or {}
        )
        return result.get("message_id")
