from unittest.mock import patch, MagicMock

import requests
from django.test import TestCase

from utils.telegram_client import (
    TelegramClient,
    TelegramSendError,
)


class TelegramClientTest(TestCase):
    def setUp(self):
        self.tg_client = TelegramClient(
            "test-bot-token"
        )

    @patch("utils.telegram_client.requests")
    def test_send_message_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": {"message_id": 42}
        }
        mock_req.request.return_value = mock_resp

        msg_id = self.tg_client.send_message(
            "-100001", "Hello"
        )
        self.assertEqual(msg_id, 42)

    @patch("utils.telegram_client.requests")
    def test_send_message_api_error(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_req.request.return_value = mock_resp

        with self.assertRaises(TelegramSendError):
            self.tg_client.send_message(
                "-100001", "Hello"
            )

    @patch("utils.telegram_client.requests.request")
    def test_connection_error_raises_send_error(
        self, mock_request
    ):
        """Transport faults must not escape as themselves.

        An uncaught requests exception is what previously
        killed the notification task outright.
        """
        mock_request.side_effect = (
            requests.ConnectionError("Connection failed")
        )

        with self.assertRaises(TelegramSendError) as ctx:
            self.tg_client.send_message(
                "-100001", "Hello"
            )
        self.assertIn(
            "Connection failed", str(ctx.exception)
        )

    @patch("utils.telegram_client.requests.request")
    def test_timeout_raises_send_error(
        self, mock_request
    ):
        mock_request.side_effect = requests.Timeout(
            "Timed out"
        )

        with self.assertRaises(TelegramSendError):
            self.tg_client.send_message(
                "-100001", "Hello"
            )

    @patch("utils.telegram_client.requests")
    def test_ok_false_body_raises(self, mock_req):
        """Telegram answers some failures with HTTP 200."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": False,
            "description": "chat not found",
        }
        mock_req.request.return_value = mock_resp

        with self.assertRaises(TelegramSendError) as ctx:
            self.tg_client.send_message(
                "-100001", "Hello"
            )
        self.assertIn(
            "chat not found", str(ctx.exception)
        )

    @patch("utils.telegram_client.requests")
    def test_429_captures_retry_after(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 429
        mock_resp.json.return_value = {
            "ok": False,
            "description": "Too Many Requests",
            "parameters": {"retry_after": 17},
        }
        mock_req.request.return_value = mock_resp

        with self.assertRaises(TelegramSendError) as ctx:
            self.tg_client.send_message(
                "-100001", "Hello"
            )
        self.assertEqual(ctx.exception.retry_after, 17)

    @patch("utils.telegram_client.requests")
    def test_migration_captures_new_chat_id(
        self, mock_req
    ):
        """A group upgraded to a supergroup gets a new id.

        Without this the feature breaks permanently the
        moment the group is upgraded.
        """
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "ok": False,
            "description": (
                "Bad Request: group chat was upgraded "
                "to a supergroup chat"
            ),
            "parameters": {
                "migrate_to_chat_id": -1001234567890
            },
        }
        mock_req.request.return_value = mock_resp

        with self.assertRaises(TelegramSendError) as ctx:
            self.tg_client.send_message(
                "-100001", "Hello"
            )
        self.assertEqual(
            ctx.exception.migrate_to_chat_id,
            -1001234567890,
        )

    @patch("utils.telegram_client.requests")
    def test_get_chat_returns_title(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": {
                "id": -4858621327,
                "title": "Akvo Testing",
                "type": "group",
            },
        }
        mock_req.request.return_value = mock_resp

        chat = self.tg_client.get_chat("-4858621327")
        self.assertEqual(chat["id"], "-4858621327")
        self.assertEqual(chat["title"], "Akvo Testing")
        self.assertEqual(chat["type"], "group")

    @patch("utils.telegram_client.requests")
    def test_send_message_payload(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": {"message_id": 1}
        }
        mock_req.request.return_value = mock_resp

        self.tg_client.send_message(
            "-100001", "Test msg"
        )

        call_kwargs = mock_req.request.call_args
        payload = call_kwargs.kwargs.get(
            "json",
            call_kwargs[1].get("json", {}),
        )
        self.assertEqual(
            payload["chat_id"], "-100001"
        )
        self.assertEqual(
            payload["text"], "Test msg"
        )
        self.assertEqual(
            payload["parse_mode"], "HTML"
        )

    @patch("utils.telegram_client.requests")
    def test_send_message_url_format(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": {"message_id": 1}
        }
        mock_req.request.return_value = mock_resp

        self.tg_client.send_message(
            "-100001", "Hi"
        )

        url = mock_req.request.call_args[0][1]
        self.assertEqual(
            url,
            "https://api.telegram.org/"
            "bottest-bot-token/sendMessage",
        )

    @patch("utils.telegram_client.requests")
    def test_get_groups_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": [
                {
                    "message": {
                        "chat": {
                            "id": -100111,
                            "title": "Supervisors",
                            "type": "supergroup",
                        }
                    }
                },
                {
                    "message": {
                        "chat": {
                            "id": -100222,
                            "title": "Enumerators",
                            "type": "group",
                        }
                    }
                },
            ]
        }
        mock_req.request.return_value = mock_resp

        groups = self.tg_client.get_groups()
        self.assertEqual(len(groups), 2)
        self.assertEqual(
            groups[0]["id"], "-100111"
        )
        self.assertEqual(
            groups[0]["title"], "Supervisors"
        )
        self.assertEqual(
            groups[1]["type"], "group"
        )

    @patch("utils.telegram_client.requests")
    def test_get_groups_api_error(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_req.request.return_value = mock_resp

        with self.assertRaises(TelegramSendError):
            self.tg_client.get_groups()

    @patch("utils.telegram_client.requests")
    def test_get_groups_empty_updates(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": []
        }
        mock_req.request.return_value = mock_resp

        groups = self.tg_client.get_groups()
        self.assertEqual(groups, [])

    @patch("utils.telegram_client.requests")
    def test_get_groups_skips_private_chats(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": [
                {
                    "message": {
                        "chat": {
                            "id": 12345,
                            "type": "private",
                            "first_name": "User",
                        }
                    }
                },
                {
                    "message": {
                        "chat": {
                            "id": -100111,
                            "title": "Group",
                            "type": "group",
                        }
                    }
                },
            ]
        }
        mock_req.request.return_value = mock_resp

        groups = self.tg_client.get_groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(
            groups[0]["id"], "-100111"
        )

    @patch("utils.telegram_client.requests")
    def test_get_groups_deduplicates(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": [
                {
                    "message": {
                        "chat": {
                            "id": -100111,
                            "title": "Group",
                            "type": "group",
                        }
                    }
                },
                {
                    "message": {
                        "chat": {
                            "id": -100111,
                            "title": "Group",
                            "type": "group",
                        }
                    }
                },
            ]
        }
        mock_req.request.return_value = mock_resp

        groups = self.tg_client.get_groups()
        self.assertEqual(len(groups), 1)

    @patch("utils.telegram_client.requests")
    def test_get_groups_my_chat_member(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": [
                {
                    "my_chat_member": {
                        "chat": {
                            "id": -100333,
                            "title": "Via Member",
                            "type": "supergroup",
                        }
                    }
                },
            ]
        }
        mock_req.request.return_value = mock_resp

        groups = self.tg_client.get_groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(
            groups[0]["id"], "-100333"
        )
        self.assertEqual(
            groups[0]["title"], "Via Member"
        )

    @patch("utils.telegram_client.requests")
    def test_get_groups_skips_no_message(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": [
                {"update_id": 1},
            ]
        }
        mock_req.request.return_value = mock_resp

        groups = self.tg_client.get_groups()
        self.assertEqual(groups, [])

    @patch("utils.telegram_client.requests")
    def test_get_groups_missing_title_defaults(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": [
                {
                    "message": {
                        "chat": {
                            "id": -100444,
                            "type": "group",
                        }
                    }
                },
            ]
        }
        mock_req.request.return_value = mock_resp

        groups = self.tg_client.get_groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(
            groups[0]["title"], "Untitled"
        )

    @patch("utils.telegram_client.requests")
    def test_get_groups_url_format(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "ok": True,
            "result": []
        }
        mock_req.request.return_value = mock_resp

        self.tg_client.get_groups()

        url = mock_req.request.call_args[0][1]
        self.assertEqual(
            url,
            "https://api.telegram.org/"
            "bottest-bot-token/getUpdates",
        )
