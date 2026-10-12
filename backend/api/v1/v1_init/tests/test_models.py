from django.db import IntegrityError
from django.test import TestCase

from api.v1.v1_init.models import SystemSetting, TelegramGroup


class SystemSettingModelTest(TestCase):
    def test_create_setting(self):
        s = SystemSetting.objects.create(
            group="telegram",
            key="enabled",
            value="True",
        )
        self.assertEqual(str(s), "telegram.enabled")
        self.assertIsNotNone(s.updated_at)

    def test_unique_constraint(self):
        SystemSetting.objects.create(
            group="telegram",
            key="bot_token",
            value="abc",
        )
        with self.assertRaises(IntegrityError):
            SystemSetting.objects.create(
                group="telegram",
                key="bot_token",
                value="xyz",
            )


class TelegramGroupModelTest(TestCase):
    def test_defaults_to_all_regions(self):
        g = TelegramGroup.objects.create(chat_id="-100111")
        self.assertEqual(g.regions, [])
        self.assertEqual(g.title, "")

    def test_chat_id_unique(self):
        TelegramGroup.objects.create(chat_id="-100111")
        with self.assertRaises(IntegrityError):
            TelegramGroup.objects.create(chat_id="-100111")
