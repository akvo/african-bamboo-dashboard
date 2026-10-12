import importlib

from django.apps import apps
from django.test import TestCase

from api.v1.v1_init.models import SystemSetting, TelegramGroup

migration = importlib.import_module(
    "api.v1.v1_init.migrations.0002_telegram_group"
)

SUP_ENV = "TELEGRAM_SUPERVISOR_GROUP_ID"
ENUM_ENV = "TELEGRAM_ENUMERATOR_GROUP_ID"


def setting(key, value):
    SystemSetting.objects.create(
        group="telegram", key=key, value=value
    )


class TelegramGroupCarryOverTest(TestCase):
    def rows(self):
        return list(
            TelegramGroup.objects.order_by("pk").values_list(
                "chat_id", "regions"
            )
        )

    def test_db_ids_become_all_regions_rows(self):
        setting("supervisor_group_id", "-100111")
        setting("enumerator_group_id", "-100222")
        migration.carry_over(apps, {})
        self.assertEqual(self.rows(), [("-100111", []), ("-100222", [])])

    def test_env_used_when_db_blank(self):
        setting("supervisor_group_id", "")
        migration.carry_over(apps, {SUP_ENV: "-100333"})
        self.assertEqual(self.rows(), [("-100333", [])])

    def test_db_value_wins_over_env(self):
        setting("supervisor_group_id", "-100111")
        migration.carry_over(apps, {SUP_ENV: "-100999"})
        self.assertEqual(self.rows(), [("-100111", [])])

    def test_same_id_twice_yields_one_row(self):
        migration.carry_over(
            apps,
            {SUP_ENV: "-4858621327", ENUM_ENV: "-4858621327"},
        )
        self.assertEqual(self.rows(), [("-4858621327", [])])

    def test_nothing_configured_yields_no_rows(self):
        migration.carry_over(apps, {})
        self.assertEqual(self.rows(), [])

    def test_role_keys_removed_others_kept(self):
        setting("supervisor_group_id", "-100111")
        setting("enabled", "true")
        migration.carry_over(apps, {})
        self.assertEqual(
            list(SystemSetting.objects.values_list("key", flat=True)),
            ["enabled"],
        )

    def test_backwards_restores_role_keys(self):
        TelegramGroup.objects.create(chat_id="-100111")
        TelegramGroup.objects.create(chat_id="-100222", regions=["ORO"])
        migration.backwards(apps, None)
        self.assertEqual(
            dict(
                SystemSetting.objects.filter(group="telegram").values_list(
                    "key", "value"
                )
            ),
            {
                "supervisor_group_id": "-100111",
                "enumerator_group_id": "-100222",
            },
        )
