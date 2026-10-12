from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from api.v1.v1_init.models import TelegramGroup
from api.v1.v1_odk.constants import SyncStatus
from api.v1.v1_odk.models import FormMetadata, Plot, RejectionAudit, Submission
from api.v1.v1_odk.tasks import send_telegram_rejection_notification
from utils.telegram_client import TelegramSendError

TASKS = "api.v1.v1_odk.tasks"


@override_settings(USE_TZ=False, TEST_ENV=True)
class TelegramSupergroupMigrationTest(TestCase):
    """Telegram issues a new id when a group becomes a
    supergroup; the row must follow it, keeping regions."""

    def setUp(self):
        form = FormMetadata.objects.create(
            asset_uid="formMG", name="Form MG"
        )
        sub = Submission.objects.create(
            uuid="sub-mg-001",
            form=form,
            kobo_id="903",
            submission_time=1700000000000,
            raw_data={},
        )
        plot = Plot.objects.create(
            plot_name="MG Plot",
            form=form,
            region="ORO",
            sub_region="S",
            created_at=1700000000000,
            submission=sub,
        )
        self.audit = RejectionAudit.objects.create(
            plot=plot,
            submission=sub,
            reason_category="overlap",
            sync_status=SyncStatus.SYNCED,
        )

    def _run_with_migration(self):
        moved = TelegramSendError(
            "upgraded", migrate_to_chat_id=-100999
        )
        with patch(
            f"{TASKS}.get_telegram_config",
            return_value={"enabled": True, "bot_token": "tok"},
        ), patch(f"{TASKS}.TelegramClient") as cls:
            client = MagicMock()
            client.send_message.side_effect = [moved, 7]
            cls.return_value = client
            send_telegram_rejection_notification(self.audit.pk)
        self.audit.refresh_from_db()

    def test_row_follows_new_id_and_keeps_regions(self):
        TelegramGroup.objects.create(
            chat_id="-100111", title="AB Oromia", regions=["ORO"]
        )
        self._run_with_migration()
        row = TelegramGroup.objects.get()
        self.assertEqual(row.chat_id, "-100999")
        self.assertEqual(row.regions, ["ORO"])
        self.assertEqual(row.title, "AB Oromia")
        self.assertEqual(self.audit.telegram_chat_ids, ["-100999"])
        self.assertIsNotNone(self.audit.telegram_sent_at)

    def test_migration_onto_existing_row_merges_regions(self):
        TelegramGroup.objects.create(chat_id="-100111", regions=["ORO"])
        TelegramGroup.objects.create(chat_id="-100999", regions=["SID"])
        self._run_with_migration()
        row = TelegramGroup.objects.get()
        self.assertEqual(row.chat_id, "-100999")
        self.assertEqual(row.regions, ["SID", "ORO"])

    def test_merge_with_all_regions_row_stays_all_regions(self):
        TelegramGroup.objects.create(chat_id="-100111", regions=["ORO"])
        TelegramGroup.objects.create(chat_id="-100999", regions=[])
        self._run_with_migration()
        self.assertEqual(TelegramGroup.objects.get().regions, [])
