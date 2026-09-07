from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin

VIEWS = "api.v1.v1_odk.views"


def kobo_item(kobo_id, uuid_str):
    return {
        "_id": int(kobo_id),
        "_uuid": uuid_str,
        "_submission_time": "2026-04-08T02:08:29",
        "_attachments": [],
    }


@override_settings(USE_TZ=False, TEST_ENV=True)
class StaleSubmissionSyncTest(
    OdkTestHelperMixin, TestCase
):
    """A submission deleted in Kobo can never sync again.

    Every validation-status update for it answers 400
    "One or more submission ids are invalid", so a
    rejection on it silently never reaches Kobo.
    """

    def setUp(self):
        self.user = self.create_kobo_user()
        self.form = FormMetadata.objects.create(
            asset_uid="formSTALE", name="Form Stale"
        )
        self.live = Submission.objects.create(
            uuid="live-uuid",
            form=self.form,
            kobo_id="111",
            submission_time=1700000000000,
            raw_data={},
        )
        self.gone = Submission.objects.create(
            uuid="gone-uuid",
            form=self.form,
            kobo_id="222",
            submission_time=1700000000000,
            raw_data={},
        )
        self.url = (
            f"/api/v1/odk/forms/{self.form.asset_uid}"
            f"/sync/"
        )

    def _sync(self, returned):
        with patch(f"{VIEWS}.KoboClient") as cls, patch(
            f"{VIEWS}.async_task"
        ):
            client = cls.return_value
            client.get_asset_detail.return_value = {}
            client.fetch_all_submissions.return_value = (
                returned
            )
            with patch(
                f"{VIEWS}.sync_form_questions",
                return_value=0,
            ):
                return self.client.post(
                    self.url, **self.get_auth_header()
                )

    def test_sync_flags_submission_missing_from_kobo(self):
        resp = self._sync([kobo_item("111", "live-uuid")])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["stale"], 1)

        self.gone.refresh_from_db()
        self.live.refresh_from_db()
        self.assertIsNotNone(
            self.gone.missing_from_kobo_at
        )
        self.assertIsNone(self.live.missing_from_kobo_at)

    def test_reappearing_submission_is_unflagged(self):
        self._sync([kobo_item("111", "live-uuid")])
        resp = self._sync(
            [
                kobo_item("111", "live-uuid"),
                kobo_item("222", "gone-uuid"),
            ]
        )
        self.assertEqual(resp.json()["stale"], 0)
        self.gone.refresh_from_db()
        self.assertIsNone(self.gone.missing_from_kobo_at)

    def test_empty_fetch_flags_nothing(self):
        """A failed or partial fetch must not condemn
        every row -- the flag blocks approve/reject."""
        resp = self._sync([])
        self.assertEqual(resp.json()["stale"], 0)
        self.gone.refresh_from_db()
        self.assertIsNone(self.gone.missing_from_kobo_at)


@override_settings(USE_TZ=False, TEST_ENV=True)
class StaleSubmissionActionsTest(
    OdkTestHelperMixin, TestCase
):
    def setUp(self):
        self.user = self.create_kobo_user()
        form = FormMetadata.objects.create(
            asset_uid="formSTALE2", name="Form Stale 2"
        )
        self.sub = Submission.objects.create(
            uuid="stale-uuid",
            form=form,
            kobo_id="333",
            submission_time=1700000000000,
            raw_data={},
            missing_from_kobo_at=timezone.now(),
        )
        self.plot = Plot.objects.create(
            plot_name="Stale Plot",
            form=form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=self.sub,
        )
        self.url = (
            f"/api/v1/odk/submissions/{self.sub.uuid}/"
        )

    def test_reject_refused_for_stale_submission(self):
        with patch(f"{VIEWS}.async_task") as mock_async:
            resp = self.client.patch(
                self.url,
                {
                    "approval_status": 2,
                    "reason_category": "overlap",
                },
                content_type="application/json",
                **self.get_auth_header(),
            )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            resp.json()["error_type"],
            "missing_from_kobo",
        )
        mock_async.assert_not_called()
        self.assertFalse(
            RejectionAudit.objects.exists()
        )
        self.sub.refresh_from_db()
        self.assertIsNone(self.sub.approval_status)

    def test_delete_removes_submission_and_plot(self):
        resp = self.client.delete(
            self.url, **self.get_auth_header()
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(
            Submission.objects.filter(
                pk=self.sub.pk
            ).exists()
        )
        # The plot goes too. Plot.submission is SET_NULL, so
        # leaving it behind would orphan a row that has no
        # data, no possible action, and that 500s the plot
        # list when its region is resolved from raw_data.
        self.assertFalse(
            Plot.objects.filter(pk=self.plot.pk).exists()
        )

    def test_delete_leaves_no_orphaned_plot(self):
        """Regression guard: an orphaned plot used to break
        the unfiltered plot list with an AttributeError on
        submission.raw_data."""
        self.client.delete(
            self.url, **self.get_auth_header()
        )
        self.assertFalse(
            Plot.objects.filter(
                submission__isnull=True
            ).exists()
        )

    def test_delete_refused_for_live_submission(self):
        self.sub.missing_from_kobo_at = None
        self.sub.save(
            update_fields=["missing_from_kobo_at"]
        )
        resp = self.client.delete(
            self.url, **self.get_auth_header()
        )
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(
            Submission.objects.filter(
                pk=self.sub.pk
            ).exists()
        )
