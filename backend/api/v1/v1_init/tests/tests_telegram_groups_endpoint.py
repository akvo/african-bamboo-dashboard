from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.test.utils import override_settings

import requests

from api.v1.v1_init.tests.mixins import V1InitTestHelperMixin
from utils.telegram_client import TelegramSendError


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    TELEGRAM_BOT_TOKEN="saved-token",
)
class TelegramGroupsTest(V1InitTestHelperMixin, TestCase):
    URL = "/api/v1/settings/telegram/groups/"

    def setUp(self):
        self.user = self.create_admin_user()

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 401)

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_no_token_returns_400(self):
        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            "No bot token", resp.json()["detail"]
        )

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_returns_groups_from_saved_token(
        self, mock_cls
    ):
        mock_client = MagicMock()
        mock_client.get_groups.return_value = [
            {
                "id": "-100111",
                "title": "Supervisors",
                "type": "supergroup",
            },
            {
                "id": "-100222",
                "title": "Enumerators",
                "type": "group",
            },
        ]
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["title"], "Supervisors")
        self.assertEqual(data[1]["id"], "-100222")
        mock_cls.assert_called_once_with("saved-token")

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_query_param_overrides_saved_token(
        self, mock_cls
    ):
        mock_client = MagicMock()
        mock_client.get_groups.return_value = []
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(
            f"{self.URL}?bot_token=custom-tok",
            **auth,
        )
        self.assertEqual(resp.status_code, 200)
        mock_cls.assert_called_once_with("custom-tok")

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_telegram_api_error_returns_502(
        self, mock_cls
    ):
        mock_client = MagicMock()
        mock_client.get_groups.side_effect = (
            TelegramSendError("Unauthorized")
        )
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 502)
        self.assertIn(
            "Unauthorized", resp.json()["detail"]
        )

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_empty_groups_returns_empty_list(
        self, mock_cls
    ):
        mock_client = MagicMock()
        mock_client.get_groups.return_value = []
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_network_error_returns_502(self, mock_cls):
        mock_client = MagicMock()
        mock_client.get_groups.side_effect = (
            requests.ConnectionError("Connection refused")
        )
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 502)
        self.assertIn(
            "Failed to connect", resp.json()["detail"]
        )

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_timeout_error_returns_502(self, mock_cls):
        mock_client = MagicMock()
        mock_client.get_groups.side_effect = (
            requests.Timeout("Request timed out")
        )
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 502)
        self.assertIn(
            "Failed to connect", resp.json()["detail"]
        )
