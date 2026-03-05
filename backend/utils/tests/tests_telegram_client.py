from unittest.mock import patch, MagicMock

from django.test import TestCase

from utils.telegram_client import (
    TelegramClient,
    TelegramSendError,
)


class TelegramClientTest(TestCase):
    def setUp(self):
        self.client = TelegramClient(
            "test-bot-token"
        )

    @patch("utils.telegram_client.requests")
    def test_send_message_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "result": {"message_id": 42}
        }
        mock_req.post.return_value = mock_resp

        msg_id = self.client.send_message(
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
        mock_req.post.return_value = mock_resp

        with self.assertRaises(TelegramSendError):
            self.client.send_message(
                "-100001", "Hello"
            )

    @patch("utils.telegram_client.requests")
    def test_send_message_network_error(
        self, mock_req
    ):
        import requests

        mock_req.post.side_effect = (
            requests.ConnectionError(
                "Connection failed"
            )
        )

        with self.assertRaises(
            requests.ConnectionError
        ):
            self.client.send_message(
                "-100001", "Hello"
            )

    @patch("utils.telegram_client.requests")
    def test_send_message_timeout(
        self, mock_req
    ):
        import requests

        mock_req.post.side_effect = (
            requests.Timeout("Timed out")
        )

        with self.assertRaises(requests.Timeout):
            self.client.send_message(
                "-100001", "Hello"
            )

    @patch("utils.telegram_client.requests")
    def test_send_message_payload(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "result": {"message_id": 1}
        }
        mock_req.post.return_value = mock_resp

        self.client.send_message(
            "-100001", "Test msg"
        )

        call_kwargs = mock_req.post.call_args
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
            payload["parse_mode"], "Markdown"
        )

    @patch("utils.telegram_client.requests")
    def test_send_message_url_format(
        self, mock_req
    ):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "result": {"message_id": 1}
        }
        mock_req.post.return_value = mock_resp

        self.client.send_message(
            "-100001", "Hi"
        )

        url = mock_req.post.call_args[0][0]
        self.assertEqual(
            url,
            "https://api.telegram.org/"
            "bottest-bot-token/sendMessage",
        )
