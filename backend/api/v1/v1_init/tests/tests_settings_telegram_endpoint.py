from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_init.models import SystemSetting
from api.v1.v1_init.tests.mixins import V1InitTestHelperMixin


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    TELEGRAM_ENABLED=False,
    TELEGRAM_BOT_TOKEN="env-token",
    TELEGRAM_SUPERVISOR_GROUP_ID="env-sup",
    TELEGRAM_ENUMERATOR_GROUP_ID="env-enum",
)
class TelegramSettingsTest(V1InitTestHelperMixin, TestCase):
    URL = "/api/v1/settings/telegram/"

    def setUp(self):
        self.user = self.create_admin_user()

    def test_get_unauthenticated_returns_401(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 401)

    def test_get_returns_fallback_defaults(self):
        auth = self.login()
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["enabled"])
        self.assertEqual(data["bot_token"], "env-token")
        self.assertEqual(
            data["supervisor_group_id"], "env-sup"
        )
        self.assertEqual(
            data["enumerator_group_id"], "env-enum"
        )

    def test_put_saves_and_get_returns_updated(self):
        auth = self.login()
        payload = {
            "enabled": True,
            "bot_token": "new-token",
            "supervisor_group_id": "-100111",
            "enumerator_group_id": "-100222",
        }
        resp = self.client.put(
            self.URL,
            payload,
            content_type="application/json",
            **auth,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["enabled"])
        self.assertEqual(data["bot_token"], "new-token")

        # Verify DB was written
        self.assertEqual(
            SystemSetting.objects.filter(
                group="telegram"
            ).count(),
            4,
        )

        # Subsequent GET returns updated values
        resp2 = self.client.get(self.URL, **auth)
        data2 = resp2.json()
        self.assertTrue(data2["enabled"])
        self.assertEqual(data2["bot_token"], "new-token")

    def test_put_unauthenticated_returns_401(self):
        resp = self.client.put(
            self.URL,
            {"enabled": True},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)
