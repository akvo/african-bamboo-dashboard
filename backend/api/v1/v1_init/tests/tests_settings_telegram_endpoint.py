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


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    TELEGRAM_ENABLED=True,
    TELEGRAM_BOT_TOKEN="env-token",
    TELEGRAM_SUPERVISOR_GROUP_ID="env-sup",
    TELEGRAM_ENUMERATOR_GROUP_ID="env-enum",
)
class TelegramSettingsFallbackTest(
    V1InitTestHelperMixin, TestCase
):
    """Blank DB rows must not shadow the env defaults.

    Every field used to carry a serializer default of
    "", so one save of the settings tab wrote blanks
    for keys the admin never touched -- permanently
    masking the env fallback and silently disabling
    notifications. A candidate cause of TC19.
    """

    URL = "/api/v1/settings/telegram/"

    def setUp(self):
        self.user = self.create_admin_user()

    def test_blank_db_value_falls_back_to_env(self):
        SystemSetting.objects.create(
            group="telegram",
            key="bot_token",
            value="",
        )
        auth = self.login()

        resp = self.client.get(self.URL, **auth)

        self.assertEqual(
            resp.json()["bot_token"], "env-token"
        )

    def test_put_with_blank_value_deletes_row(self):
        SystemSetting.objects.create(
            group="telegram",
            key="bot_token",
            value="stale-token",
        )
        auth = self.login()

        resp = self.client.put(
            self.URL,
            {"bot_token": ""},
            content_type="application/json",
            **auth,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            SystemSetting.objects.filter(
                group="telegram", key="bot_token"
            ).exists()
        )
        self.assertEqual(
            resp.json()["bot_token"], "env-token"
        )

    def test_partial_put_does_not_disable_enabled(self):
        """An omitted key must stay omitted.

        enabled used to default to False, so a PUT that
        only set a token silently switched
        notifications off.
        """
        SystemSetting.objects.create(
            group="telegram",
            key="enabled",
            value="true",
        )
        auth = self.login()

        resp = self.client.put(
            self.URL,
            {"bot_token": "abc"},
            content_type="application/json",
            **auth,
        )

        self.assertTrue(resp.json()["enabled"])

    def test_put_persists_enabled_lowercase(self):
        auth = self.login()

        self.client.put(
            self.URL,
            {"enabled": True},
            content_type="application/json",
            **auth,
        )

        row = SystemSetting.objects.get(
            group="telegram", key="enabled"
        )
        self.assertEqual(row.value, "true")

    def test_legacy_capitalised_true_is_parsed(self):
        """Rows written by the previous str(True)."""
        SystemSetting.objects.create(
            group="telegram",
            key="enabled",
            value="True",
        )
        auth = self.login()

        resp = self.client.get(self.URL, **auth)

        self.assertTrue(resp.json()["enabled"])

    def test_explicit_false_still_disables(self):
        SystemSetting.objects.create(
            group="telegram",
            key="enabled",
            value="false",
        )
        auth = self.login()

        resp = self.client.get(self.URL, **auth)

        self.assertFalse(resp.json()["enabled"])
