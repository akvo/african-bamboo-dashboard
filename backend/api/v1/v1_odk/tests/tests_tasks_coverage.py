import logging
import os
import shutil
from io import BytesIO
from unittest.mock import MagicMock, patch

from PIL import Image

from django.test import TestCase, SimpleTestCase
from django.test.utils import override_settings

from api.v1.v1_jobs.constants import (
    JobStatus,
    JobTypes,
)
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
    SyncStatus,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    FormQuestion,
    FormOption,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.tasks import (
    _escape_markdown,
    _resolve_field_spec,
    _resolve_plot_location,
    generate_export_file,
    on_kobo_sync_complete,
    send_telegram_rejection_notification,
    sync_kobo_validation_status,
    download_submission_attachments,
)
from api.v1.v1_users.models import SystemUser
from utils.encryption import encrypt


# ── generate_export_file ──────────────────────


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
)
class GenerateExportFileTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="formEX",
            name="Export Form",
            filter_fields=["species"],
        )
        self.sub_approved = Submission.objects.create(
            uuid="sub-ex-1",
            form=self.form,
            kobo_id="500",
            submission_time=1700000000000,
            submitted_by="enum1",
            approval_status=(
                ApprovalStatusTypes.APPROVED
            ),
            raw_data={
                "species": "bamboo",
                "q": "a",
            },
        )
        self.plot_approved = Plot.objects.create(
            plot_name="Export Plot 1",
            form=self.form,
            region="Region A",
            sub_region="Sub A",
            created_at=1700000000000,
            submission=self.sub_approved,
            polygon_wkt="POLYGON((0 0,1 0,1 1,0 0))",
        )
        self.sub_rejected = Submission.objects.create(
            uuid="sub-ex-2",
            form=self.form,
            kobo_id="501",
            submission_time=1700100000000,
            submitted_by="enum2",
            approval_status=(
                ApprovalStatusTypes.REJECTED
            ),
            raw_data={"species": "oak", "q": "b"},
        )
        self.plot_rejected = Plot.objects.create(
            plot_name="Export Plot 2",
            form=self.form,
            region="Region B",
            sub_region="Sub B",
            created_at=1700100000000,
            submission=self.sub_rejected,
            polygon_wkt="POLYGON((2 2,3 2,3 3,2 2))",
        )

    def _create_job(self, filters=None, fmt="shp"):
        job_type = (
            JobTypes.export_geojson
            if fmt == "geojson"
            else JobTypes.export_shapefile
        )
        return Jobs.objects.create(
            type=job_type,
            status=JobStatus.pending,
            info={
                "form_id": "formEX",
                "filters": filters or {},
            },
        )

    def test_job_not_found(self):
        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.ERROR,
        ):
            generate_export_file(99999)

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_basic_export_success(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = (
            "/tmp/test.zip",
            2,
        )
        job = self._create_job()

        generate_export_file(job.pk)

        job.refresh_from_db()
        self.assertEqual(
            job.status, JobStatus.done
        )
        self.assertEqual(
            job.info["record_count"], 2
        )
        mock_cleanup.assert_called_once()

    @patch(
        "api.v1.v1_odk.tasks.generate_geojson"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_geojson_export(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = (
            "/tmp/test.geojson",
            1,
        )
        job = self._create_job(fmt="geojson")

        generate_export_file(job.pk)

        job.refresh_from_db()
        self.assertEqual(
            job.status, JobStatus.done
        )
        mock_gen.assert_called_once()

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_status_filter_approved(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = ("/tmp/t.zip", 1)
        job = self._create_job(
            filters={"status": "approved"}
        )

        generate_export_file(job.pk)

        qs = mock_gen.call_args[0][0]
        self.assertEqual(qs.count(), 1)
        self.assertEqual(
            qs.first().pk, self.plot_approved.pk
        )

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_status_filter_rejected(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = ("/tmp/t.zip", 1)
        job = self._create_job(
            filters={"status": "rejected"}
        )

        generate_export_file(job.pk)

        qs = mock_gen.call_args[0][0]
        self.assertEqual(qs.count(), 1)
        self.assertEqual(
            qs.first().pk, self.plot_rejected.pk
        )

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_status_filter_pending(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = ("/tmp/t.zip", 0)
        job = self._create_job(
            filters={"status": "pending"}
        )

        generate_export_file(job.pk)

        qs = mock_gen.call_args[0][0]
        self.assertEqual(qs.count(), 0)

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_region_filter(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = ("/tmp/t.zip", 1)
        job = self._create_job(
            filters={"region": "Region A"}
        )

        generate_export_file(job.pk)

        qs = mock_gen.call_args[0][0]
        self.assertEqual(qs.count(), 1)
        self.assertEqual(
            qs.first().region, "Region A"
        )

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_sub_region_filter(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = ("/tmp/t.zip", 1)
        job = self._create_job(
            filters={"sub_region": "Sub B"}
        )

        generate_export_file(job.pk)

        qs = mock_gen.call_args[0][0]
        self.assertEqual(qs.count(), 1)
        self.assertEqual(
            qs.first().sub_region, "Sub B"
        )

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_search_filter(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = ("/tmp/t.zip", 1)
        job = self._create_job(
            filters={"search": "Plot 1"}
        )

        generate_export_file(job.pk)

        qs = mock_gen.call_args[0][0]
        self.assertEqual(qs.count(), 1)
        self.assertEqual(
            qs.first().plot_name, "Export Plot 1"
        )

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_date_range_filter(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = ("/tmp/t.zip", 1)
        job = self._create_job(
            filters={
                "start_date": 1700050000000,
                "end_date": 1700200000000,
            }
        )

        generate_export_file(job.pk)

        qs = mock_gen.call_args[0][0]
        self.assertEqual(qs.count(), 1)
        self.assertEqual(
            qs.first().pk, self.plot_rejected.pk
        )

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_dynamic_filter(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.return_value = ("/tmp/t.zip", 1)
        job = self._create_job(
            filters={
                "dynamic_filters": {
                    "species": "bamboo"
                }
            }
        )

        generate_export_file(job.pk)

        qs = mock_gen.call_args[0][0]
        self.assertEqual(qs.count(), 1)
        self.assertEqual(
            qs.first().pk, self.plot_approved.pk
        )

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_dynamic_filter_not_in_allowed(
        self, mock_cleanup, mock_gen
    ):
        """Dynamic filter for a field not in
        filter_fields should be ignored."""
        mock_gen.return_value = ("/tmp/t.zip", 2)
        job = self._create_job(
            filters={
                "dynamic_filters": {
                    "unknown_field": "val"
                }
            }
        )

        generate_export_file(job.pk)

        qs = mock_gen.call_args[0][0]
        self.assertEqual(qs.count(), 2)

    @patch(
        "api.v1.v1_odk.tasks.generate_shapefile"
    )
    @patch(
        "api.v1.v1_odk.tasks.cleanup_old_exports"
    )
    def test_export_failure_sets_failed(
        self, mock_cleanup, mock_gen
    ):
        mock_gen.side_effect = Exception(
            "shapefile error"
        )
        job = self._create_job()

        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level="ERROR",
        ):
            generate_export_file(job.pk)

        job.refresh_from_db()
        self.assertEqual(
            job.status, JobStatus.failed
        )
        self.assertIn(
            "shapefile error", job.result
        )


# ── sync_kobo_validation_status edge cases ───


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    SECRET_KEY="test-secret-key-for-encryption",
)
class SyncKoboValidationStatusEdgeTest(TestCase):
    def test_no_status_mapping_skips(self):
        """Unmapped approval_status should log
        warning and return early."""
        enc = encrypt("pass")
        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.WARNING,
        ) as cm:
            sync_kobo_validation_status(
                "https://kf.kobotoolbox.org",
                "user",
                enc,
                "aXYZ",
                [1],
                999,
            )

        self.assertTrue(
            any(
                "No Kobo status mapping" in m
                for m in cm.output
            )
        )


# ── on_kobo_sync_complete edge cases ────────


@override_settings(USE_TZ=False, TEST_ENV=True)
class KoboSyncHookEdgeCasesTest(TestCase):
    def test_no_audit_id_returns_early(self):
        task = MagicMock()
        task.kwargs = {}

        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.WARNING,
        ):
            on_kobo_sync_complete(task)

    def test_audit_not_found_returns_early(self):
        task = MagicMock()
        task.kwargs = {"audit_id": 99999}
        task.success = True

        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.ERROR,
        ):
            on_kobo_sync_complete(task)

    @override_settings(TELEGRAM_ENABLED=False)
    @patch(
        "api.v1.v1_odk.tasks.async_task"
    )
    def test_hook_success_telegram_disabled(
        self, mock_async
    ):
        form = FormMetadata.objects.create(
            asset_uid="formHK2",
            name="Hook Form 2",
        )
        sub = Submission.objects.create(
            uuid="sub-hk2",
            form=form,
            kobo_id="900",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={},
        )
        plot = Plot.objects.create(
            plot_name="Hook Plot",
            form=form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=sub,
        )
        validator = (
            SystemUser.objects.create_superuser(
                email="hk2@test.local",
                password="Changeme123",
                name="hk2",
            )
        )
        audit = RejectionAudit.objects.create(
            plot=plot,
            submission=sub,
            validator=validator,
            reason_category="other",
        )

        task = MagicMock()
        task.success = True
        task.kwargs = {"audit_id": audit.pk}

        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.INFO,
        ) as cm:
            on_kobo_sync_complete(task)

        mock_async.assert_not_called()
        audit.refresh_from_db()
        self.assertEqual(
            audit.sync_status, SyncStatus.SYNCED
        )
        self.assertTrue(
            any(
                "Telegram disabled" in m
                for m in cm.output
            )
        )


# ── _escape_markdown ─────────────────────────


class EscapeMarkdownTest(SimpleTestCase):
    def test_escapes_special_chars(self):
        text = "hello_world *bold* `code` [link]"
        result = _escape_markdown(text)
        self.assertEqual(
            result,
            "hello\\_world \\*bold\\* "
            "\\`code\\` \\[link]",
        )

    def test_no_special_chars(self):
        self.assertEqual(
            _escape_markdown("plain"),
            "plain",
        )


# ── _resolve_field_spec ──────────────────────


@override_settings(USE_TZ=False, TEST_ENV=True)
class ResolveFieldSpecTest(TestCase):
    def test_with_option_lookup(self):
        result = _resolve_field_spec(
            {"region": "ET04"},
            "region",
            {"region": {"ET04": "Amhara"}},
            {"region": "select_one"},
        )
        self.assertEqual(result, "Amhara")

    def test_without_option_lookup(self):
        result = _resolve_field_spec(
            {"name": "John"},
            "name",
            {},
            {},
        )
        self.assertEqual(result, "John")

    def test_multiple_fields(self):
        result = _resolve_field_spec(
            {"f1": "A", "f2": "B"},
            "f1,f2",
            {},
            {},
        )
        self.assertEqual(result, "A - B")

    def test_missing_field_skipped(self):
        result = _resolve_field_spec(
            {"f1": "A"},
            "f1,f2",
            {},
            {},
        )
        self.assertEqual(result, "A")

    def test_all_missing_returns_none(self):
        result = _resolve_field_spec(
            {},
            "f1,f2",
            {},
            {},
        )
        self.assertIsNone(result)

    def test_empty_value_skipped(self):
        result = _resolve_field_spec(
            {"f1": "  "},
            "f1",
            {},
            {},
        )
        self.assertIsNone(result)


# ── _resolve_plot_location ───────────────────


@override_settings(USE_TZ=False, TEST_ENV=True)
class ResolvePlotLocationTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="formLOC",
            name="Loc Form",
            region_field="region",
            sub_region_field="woreda",
        )
        self.sub = Submission.objects.create(
            uuid="sub-loc-1",
            form=self.form,
            kobo_id="600",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={
                "region": "ET04",
                "woreda": "W01",
            },
        )
        self.plot = Plot.objects.create(
            plot_name="Loc Plot",
            form=self.form,
            region="Fallback Region",
            sub_region="Fallback Sub",
            created_at=1700000000000,
            submission=self.sub,
        )
        q_region = FormQuestion.objects.create(
            form=self.form,
            name="region",
            label="Region",
            type="select_one",
        )
        FormOption.objects.create(
            question=q_region,
            name="ET04",
            label="Amhara",
        )
        q_woreda = FormQuestion.objects.create(
            form=self.form,
            name="woreda",
            label="Woreda",
            type="select_one",
        )
        FormOption.objects.create(
            question=q_woreda,
            name="W01",
            label="Bahir Dar",
        )

    def test_resolves_with_options(self):
        result = _resolve_plot_location(
            self.sub, self.plot
        )
        self.assertEqual(
            result, "Amhara - Bahir Dar"
        )

    def test_fallback_to_plot_values(self):
        self.sub.raw_data = {}
        self.sub.save()

        result = _resolve_plot_location(
            self.sub, self.plot
        )
        self.assertEqual(
            result,
            "Fallback Region - Fallback Sub",
        )

    def test_region_only(self):
        self.sub.raw_data = {}
        self.sub.save()
        self.plot.sub_region = ""
        self.plot.save()

        result = _resolve_plot_location(
            self.sub, self.plot
        )
        self.assertEqual(
            result, "Fallback Region"
        )

    def test_sub_region_only(self):
        self.sub.raw_data = {}
        self.sub.save()
        self.plot.region = ""
        self.plot.save()

        result = _resolve_plot_location(
            self.sub, self.plot
        )
        self.assertEqual(
            result, "Fallback Sub"
        )

    def test_unknown_location(self):
        self.sub.raw_data = {}
        self.sub.save()
        self.plot.region = ""
        self.plot.sub_region = ""
        self.plot.save()

        result = _resolve_plot_location(
            self.sub, self.plot
        )
        self.assertEqual(
            result, "Unknown Location"
        )


# ── send_telegram_rejection_notification ─────


@override_settings(USE_TZ=False, TEST_ENV=True)
class TelegramNotificationEdgeCasesTest(
    TestCase
):
    def test_audit_not_found(self):
        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.ERROR,
        ):
            send_telegram_rejection_notification(
                99999
            )

    @override_settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="",
    )
    def test_no_bot_token_skips(self):
        form = FormMetadata.objects.create(
            asset_uid="formNBT",
            name="NBT",
        )
        sub = Submission.objects.create(
            uuid="sub-nbt",
            form=form,
            kobo_id="700",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={},
        )
        plot = Plot.objects.create(
            plot_name="NBT Plot",
            form=form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=sub,
        )
        validator = (
            SystemUser.objects.create_superuser(
                email="nbt@test.local",
                password="Changeme123",
                name="nbt",
            )
        )
        audit = RejectionAudit.objects.create(
            plot=plot,
            submission=sub,
            validator=validator,
            reason_category="overlap",
        )

        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.WARNING,
        ) as cm:
            send_telegram_rejection_notification(
                audit.pk
            )

        self.assertTrue(
            any(
                "BOT_TOKEN not set" in m
                for m in cm.output
            )
        )

    @override_settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_SUPERVISOR_GROUP_ID="-100001",
        TELEGRAM_ENUMERATOR_GROUP_ID="-100002",
    )
    @patch(
        "api.v1.v1_odk.tasks.TelegramClient"
    )
    def test_reason_without_text(
        self, mock_client_cls
    ):
        """When reason_text is empty, message
        should contain only category display."""
        form = FormMetadata.objects.create(
            asset_uid="formRNT",
            name="RNT",
        )
        sub = Submission.objects.create(
            uuid="sub-rnt",
            form=form,
            kobo_id="710",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={},
        )
        plot = Plot.objects.create(
            plot_name="RNT Plot",
            form=form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=sub,
        )
        validator = (
            SystemUser.objects.create_superuser(
                email="rnt@test.local",
                password="Changeme123",
                name="rnt",
            )
        )
        audit = RejectionAudit.objects.create(
            plot=plot,
            submission=sub,
            validator=validator,
            reason_category="duplicate",
            reason_text="",
        )

        mock_client = MagicMock()
        mock_client.send_message.return_value = 1
        mock_client_cls.return_value = (
            mock_client
        )

        send_telegram_rejection_notification(
            audit.pk
        )

        msg = (
            mock_client.send_message.call_args[
                0
            ][1]
        )
        self.assertIn(
            "Duplicate Submission", msg
        )
        self.assertNotIn(":", msg.split(
            "Duplicate Submission"
        )[1].split("\n")[0])

    @override_settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_SUPERVISOR_GROUP_ID="-100001",
        TELEGRAM_ENUMERATOR_GROUP_ID="-100002",
    )
    @patch(
        "api.v1.v1_odk.tasks.TelegramClient"
    )
    def test_no_validator(
        self, mock_client_cls
    ):
        """When validator is None, message shows
        'Unknown'."""
        form = FormMetadata.objects.create(
            asset_uid="formNV",
            name="NV",
        )
        sub = Submission.objects.create(
            uuid="sub-nv",
            form=form,
            kobo_id="720",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={},
        )
        plot = Plot.objects.create(
            plot_name="NV Plot",
            form=form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=sub,
        )
        audit = RejectionAudit.objects.create(
            plot=plot,
            submission=sub,
            validator=None,
            reason_category="other",
        )

        mock_client = MagicMock()
        mock_client.send_message.return_value = 1
        mock_client_cls.return_value = (
            mock_client
        )

        send_telegram_rejection_notification(
            audit.pk
        )

        msg = (
            mock_client.send_message.call_args[
                0
            ][1]
        )
        self.assertIn("Unknown", msg)


# ── download_submission_attachments ──────────


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    SECRET_KEY="test-secret-key-for-encryption",
    STORAGE_PATH="/tmp/test_storage",
)
class DownloadSubmissionAttachmentsTest(
    TestCase
):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="formDL",
            name="DL Form",
        )
        self.kobo_url = (
            "https://kf.kobotoolbox.org"
        )
        self.kobo_username = "testuser"
        self.kobo_password_enc = encrypt(
            "testpass"
        )

    def test_submission_not_found(self):
        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.ERROR,
        ):
            download_submission_attachments(
                self.kobo_url,
                self.kobo_username,
                self.kobo_password_enc,
                "nonexistent-uuid",
            )

    def test_no_attachments_returns_early(self):
        Submission.objects.create(
            uuid="sub-dl-1",
            form=self.form,
            kobo_id="800",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={"q": "a"},
        )
        # Should not raise
        download_submission_attachments(
            self.kobo_url,
            self.kobo_username,
            self.kobo_password_enc,
            "sub-dl-1",
        )

    def test_no_image_attachments_returns(self):
        Submission.objects.create(
            uuid="sub-dl-2",
            form=self.form,
            kobo_id="801",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={
                "_attachments": [
                    {
                        "mimetype": "text/csv",
                        "download_medium_url": (
                            "http://x/f.csv"
                        ),
                        "uid": "att1",
                    }
                ]
            },
        )
        download_submission_attachments(
            self.kobo_url,
            self.kobo_username,
            self.kobo_password_enc,
            "sub-dl-2",
        )

    @patch(
        "api.v1.v1_odk.tasks.KoboClient"
    )
    def test_downloads_image(
        self, mock_cls
    ):
        Submission.objects.create(
            uuid="sub-dl-3",
            form=self.form,
            kobo_id="802",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={
                "_attachments": [
                    {
                        "mimetype": "image/jpeg",
                        "download_medium_url": (
                            "http://x/img.jpg"
                        ),
                        "uid": "imguid1",
                        "media_file_basename": (
                            "photo.jpg"
                        ),
                    }
                ]
            },
        )
        mock_client = MagicMock()
        mock_resp = MagicMock()
        buf = BytesIO()
        Image.new("RGB", (10, 10)).save(
            buf, format="JPEG"
        )
        mock_resp.content = buf.getvalue()
        mock_client.session.get.return_value = (
            mock_resp
        )
        mock_cls.return_value = mock_client

        try:
            download_submission_attachments(
                self.kobo_url,
                self.kobo_username,
                self.kobo_password_enc,
                "sub-dl-3",
            )

            dest = os.path.join(
                "/tmp/test_storage",
                "attachments",
                "sub-dl-3",
                "imguid1.jpg",
            )
            self.assertTrue(os.path.exists(dest))
        finally:
            shutil.rmtree(
                os.path.join(
                    "/tmp/test_storage",
                    "attachments",
                    "sub-dl-3",
                ),
                ignore_errors=True,
            )

    @patch(
        "api.v1.v1_odk.tasks.KoboClient"
    )
    def test_all_urls_fail(self, mock_cls):
        Submission.objects.create(
            uuid="sub-dl-4",
            form=self.form,
            kobo_id="803",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={
                "_attachments": [
                    {
                        "mimetype": "image/png",
                        "download_medium_url": (
                            "http://x/img.png"
                        ),
                        "uid": "imguid2",
                    }
                ]
            },
        )
        mock_client = MagicMock()
        mock_client.session.get.side_effect = (
            Exception("network error")
        )
        mock_cls.return_value = mock_client

        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.ERROR,
        ) as cm:
            download_submission_attachments(
                self.kobo_url,
                self.kobo_username,
                self.kobo_password_enc,
                "sub-dl-4",
            )

        self.assertTrue(
            any(
                "All URLs failed" in m
                for m in cm.output
            )
        )

    @patch(
        "api.v1.v1_odk.tasks.KoboClient"
    )
    def test_skips_existing_file(
        self, mock_cls
    ):
        Submission.objects.create(
            uuid="sub-dl-5",
            form=self.form,
            kobo_id="804",
            submission_time=1700000000000,
            submitted_by="t",
            raw_data={
                "_attachments": [
                    {
                        "mimetype": "image/jpeg",
                        "download_medium_url": (
                            "http://x/img.jpg"
                        ),
                        "uid": "imguid3",
                        "media_file_basename": (
                            "photo.jpg"
                        ),
                    }
                ]
            },
        )
        dest_dir = os.path.join(
            "/tmp/test_storage",
            "attachments",
            "sub-dl-5",
        )
        os.makedirs(dest_dir, exist_ok=True)
        dest_file = os.path.join(
            dest_dir, "imguid3.jpg"
        )
        with open(dest_file, "w") as f:
            f.write("existing")

        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        try:
            download_submission_attachments(
                self.kobo_url,
                self.kobo_username,
                self.kobo_password_enc,
                "sub-dl-5",
            )
            mock_client.session.get.assert_not_called()
        finally:
            shutil.rmtree(
                dest_dir, ignore_errors=True
            )
