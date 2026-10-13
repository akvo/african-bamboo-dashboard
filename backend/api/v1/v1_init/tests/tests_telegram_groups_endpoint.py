from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_init.models import TelegramGroup
from api.v1.v1_init.tests.mixins import V1InitTestHelperMixin
from utils.telegram_client import TelegramSendError


# Groups now come only from the DB, so the token pin is what
# matters. An unconfigured MagicMock reaching the renderer
# (get_chat or get_chat_member_count) is JSON-encoded by DRF.
# hasattr() is always true on a MagicMock, so the encoder recurses into
# auto-created attributes until the process is OOM-killed.
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
                "title": "Field A",
                "type": "supergroup",
            },
            {
                "id": "-100222",
                "title": "Field B",
                "type": "group",
            },
        ]
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["title"], "Field A")
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
    def test_transport_error_returns_502(self, mock_cls):
        """TelegramClient normalises transport faults.

        A DNS failure or timeout reaches the view as a
        TelegramSendError, not a raw requests exception,
        so there is only one path to handle.
        """
        mock_client = MagicMock()
        mock_client.get_groups.side_effect = (
            TelegramSendError(
                "Telegram request failed: "
                "Connection refused"
            )
        )
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 502)
        self.assertIn(
            "Connection refused", resp.json()["detail"]
        )

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_configured_row_resolved_via_get_chat(
        self, mock_cls
    ):
        """getUpdates only sees the last 24h of activity.

        A configured group must still render with its
        name after a quiet day, which is what getChat
        provides.
        """
        TelegramGroup.objects.create(chat_id="-100999")
        mock_client = MagicMock()
        mock_client.get_groups.return_value = []
        mock_client.get_chat.return_value = {
            "id": "-100999",
            "title": "Akvo Testing",
            "type": "group",
        }
        mock_client.get_chat_member_count.return_value = 6
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(),
            [
                {
                    "id": "-100999",
                    "title": "Akvo Testing",
                    "type": "group",
                    "member_count": 6,
                }
            ],
        )

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_every_row_resolved_even_if_discovered(
        self, mock_cls
    ):
        """Spec: getChat for every configured row, not
        only the ones getUpdates missed."""
        TelegramGroup.objects.create(chat_id="-100111")
        TelegramGroup.objects.create(chat_id="-100222")
        mock_client = MagicMock()
        mock_client.get_groups.return_value = [
            {"id": "-100111", "title": "Old", "type": "group"},
        ]
        mock_client.get_chat.side_effect = lambda cid: {
            "id": cid,
            "title": f"T{cid}",
            "type": "supergroup",
        }
        mock_client.get_chat_member_count.return_value = 3
        mock_cls.return_value = mock_client

        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(
            [c.args[0] for c in mock_client.get_chat.call_args_list],
            ["-100111", "-100222"],
        )
        self.assertEqual(
            [g["title"] for g in resp.json()],
            ["T-100111", "T-100222"],
        )

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_title_cached_on_row(self, mock_cls):
        TelegramGroup.objects.create(chat_id="-100999")
        mock_client = MagicMock()
        mock_client.get_groups.return_value = []
        mock_client.get_chat.return_value = {
            "id": "-100999",
            "title": "AB Sidama",
            "type": "group",
        }
        mock_client.get_chat_member_count.return_value = 6
        mock_cls.return_value = mock_client

        self.client.get(self.URL, **self.login())
        self.assertEqual(
            TelegramGroup.objects.get().title, "AB Sidama"
        )

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_get_chat_rescues_failed_discovery(
        self, mock_cls
    ):
        """A getUpdates outage no longer empties the list."""
        TelegramGroup.objects.create(chat_id="-100999")
        mock_client = MagicMock()
        mock_client.get_groups.side_effect = (
            TelegramSendError("getUpdates exploded")
        )
        mock_client.get_chat.return_value = {
            "id": "-100999",
            "title": "Akvo Testing",
            "type": "group",
        }
        mock_client.get_chat_member_count.return_value = 6
        mock_cls.return_value = mock_client

        auth = self.login()
        with self.assertLogs("api.v1.v1_init.views", "WARNING"):
            resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()[0]["title"], "Akvo Testing"
        )

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_get_chat_failure_drops_only_that_entry(
        self, mock_cls
    ):
        TelegramGroup.objects.create(chat_id="-100999")
        mock_client = MagicMock()
        mock_client.get_groups.return_value = [
            {
                "id": "-100111",
                "title": "Field",
                "type": "supergroup",
            },
        ]
        mock_client.get_chat.side_effect = (
            TelegramSendError("chat not found")
        )
        mock_client.get_chat_member_count.return_value = 6
        mock_cls.return_value = mock_client

        auth = self.login()
        with self.assertLogs("api.v1.v1_init.views", "WARNING"):
            resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "-100111")

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_member_count_failure_is_null(self, mock_cls):
        mock_client = MagicMock()
        mock_client.get_groups.return_value = [
            {"id": "-100111", "title": "A", "type": "group"},
        ]
        mock_client.get_chat_member_count.side_effect = (
            TelegramSendError("forbidden")
        )
        mock_cls.return_value = mock_client

        with self.assertLogs("api.v1.v1_init.views", "WARNING"):
            resp = self.client.get(self.URL, **self.login())
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()[0]["member_count"])

    @patch("api.v1.v1_init.views.TelegramClient")
    def test_non_int_member_count_is_null(self, mock_cls):
        """Anything but an int must never reach the JSON
        encoder (see the OOM note on this class)."""
        mock_client = MagicMock()
        mock_client.get_groups.return_value = [
            {"id": "-100111", "title": "A", "type": "group"},
        ]
        mock_cls.return_value = mock_client

        resp = self.client.get(self.URL, **self.login())
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()[0]["member_count"])
