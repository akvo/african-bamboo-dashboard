from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_init.models import SystemSetting, TelegramGroup
from api.v1.v1_init.tests.mixins import V1InitTestHelperMixin


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    TELEGRAM_ENABLED=False,
    TELEGRAM_BOT_TOKEN="env-token",
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
        self.assertEqual(data["groups"], [])
        self.assertNotIn("supervisor_group_id", data)

    def test_put_saves_and_get_returns_updated(self):
        auth = self.login()
        payload = {
            "enabled": True,
            "bot_token": "new-token",
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
            2,
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

    def _put(self, payload):
        return self.client.put(
            self.URL,
            payload,
            content_type="application/json",
            **self.login(),
        )

    def test_put_groups_replaces_full_set(self):
        TelegramGroup.objects.create(
            chat_id="-100111", title="AB Management"
        )
        TelegramGroup.objects.create(chat_id="-100999")
        resp = self._put(
            {
                "groups": [
                    {"chat_id": "-100111", "regions": []},
                    {
                        "chat_id": "-100222",
                        "regions": ["ORO", "ET04"],
                    },
                ]
            }
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["groups"],
            [
                {
                    "chat_id": "-100111",
                    "title": "AB Management",
                    "regions": [],
                },
                {
                    "chat_id": "-100222",
                    "title": "",
                    "regions": ["ORO", "ET04"],
                },
            ],
        )
        self.assertFalse(
            TelegramGroup.objects.filter(
                chat_id="-100999"
            ).exists()
        )
        self.assertFalse(
            SystemSetting.objects.filter(key="groups").exists()
        )

    def test_put_without_groups_leaves_rows(self):
        TelegramGroup.objects.create(
            chat_id="-100111", regions=["SID"]
        )
        self._put({"enabled": True})
        self.assertEqual(
            TelegramGroup.objects.get().regions, ["SID"]
        )

    def test_put_empty_groups_deletes_all(self):
        TelegramGroup.objects.create(chat_id="-100111")
        resp = self._put({"groups": []})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(TelegramGroup.objects.exists())

    def test_put_duplicate_chat_id_is_400(self):
        TelegramGroup.objects.create(chat_id="-100111")
        resp = self._put(
            {
                "groups": [
                    {"chat_id": "-100222", "regions": []},
                    {"chat_id": "-100222", "regions": ["ORO"]},
                ]
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json(),
            {"groups": ["Duplicate chat_id: -100222"]},
        )
        # Nothing half-applied.
        self.assertEqual(
            list(
                TelegramGroup.objects.values_list(
                    "chat_id", flat=True
                )
            ),
            ["-100111"],
        )

    def test_put_blank_chat_id_is_400(self):
        resp = self._put(
            {"groups": [{"chat_id": " ", "regions": []}]}
        )
        self.assertEqual(resp.status_code, 400)

    def test_put_blank_region_is_400(self):
        resp = self._put(
            {"groups": [{"chat_id": "-1", "regions": [""]}]}
        )
        self.assertEqual(resp.status_code, 400)

    def test_role_keys_no_longer_accepted(self):
        self._put({"supervisor_group_id": "-100111"})
        self.assertFalse(
            SystemSetting.objects.filter(
                key="supervisor_group_id"
            ).exists()
        )


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    TELEGRAM_ENABLED=True,
    TELEGRAM_BOT_TOKEN="env-token",
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
