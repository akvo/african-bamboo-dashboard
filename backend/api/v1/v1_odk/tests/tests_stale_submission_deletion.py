from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from api.v1.v1_odk.constants import RejectionCategory
from api.v1.v1_odk.models import (
    FormMetadata,
    MainPlot,
    MainPlotSubmission,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin

VIEWS = "api.v1.v1_odk.views"


@override_settings(USE_TZ=False, TEST_ENV=True)
class StaleSubmissionDeletionTest(OdkTestHelperMixin, TestCase):
    """Opt-in removal of rows KoboToolbox stopped returning.

    Flagging is reversible and deleting is not, so the sweep
    is off unless SYNC_DELETE_STALE_AFTER_DAYS is set, waits
    out a grace period, and leaves anything carrying
    user-visible history alone.
    """

    def setUp(self):
        self.user = self.create_kobo_user()
        self.form = FormMetadata.objects.create(
            asset_uid="formSTALE", name="Stale"
        )

    def _submission(self, kobo_id, flagged_days_ago=None):
        sub = Submission.objects.create(
            uuid=f"uuid-{kobo_id}",
            form=self.form,
            kobo_id=kobo_id,
            submission_time=1700000000000,
            raw_data={},
        )
        if flagged_days_ago is not None:
            sub.missing_from_kobo_at = (
                timezone.now()
                - timedelta(days=flagged_days_ago)
            )
            sub.save(update_fields=["missing_from_kobo_at"])
        return sub

    def _plot_for(self, sub, name="Plot"):
        return Plot.objects.create(
            plot_name=name,
            form=self.form,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=sub,
        )

    def _sync(self, returned=()):
        url = f"/api/v1/odk/forms/{self.form.asset_uid}/sync/"
        with patch(f"{VIEWS}.KoboClient") as cls, patch(
            f"{VIEWS}.async_task"
        ), patch(
            f"{VIEWS}.sync_form_questions", return_value=0
        ):
            client = cls.return_value
            client.get_asset_detail.return_value = {}
            client.fetch_all_submissions.return_value = list(
                returned
            )
            return self.client.post(
                url, **self.get_auth_header()
            )

    def test_disabled_by_default_keeps_stale_rows(self):
        """The default deployment only flags. Data loss must
        never be something a partner gets by accident."""
        self._submission("111", flagged_days_ago=999)

        resp = self._sync()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["stale_deleted"], 0
        )
        self.assertTrue(
            Submission.objects.filter(kobo_id="111").exists()
        )

    @override_settings(SYNC_DELETE_STALE_AFTER_DAYS=7)
    def test_deletes_row_and_plot_past_grace_period(self):
        sub = self._submission("111", flagged_days_ago=30)
        self._plot_for(sub)

        resp = self._sync()

        self.assertEqual(resp.json()["stale_deleted"], 1)
        self.assertFalse(
            Submission.objects.filter(kobo_id="111").exists()
        )
        # An orphaned plot has no data and no possible
        # action, so it goes with the submission.
        self.assertEqual(Plot.objects.count(), 0)

    @override_settings(SYNC_DELETE_STALE_AFTER_DAYS=7)
    def test_grace_period_survives_a_transient_kobo_blip(self):
        """A row flagged this sync must still be here next
        sync, when Kobo returns it again."""
        self._submission("111", flagged_days_ago=1)

        resp = self._sync()

        self.assertEqual(resp.json()["stale_deleted"], 0)
        self.assertTrue(
            Submission.objects.filter(kobo_id="111").exists()
        )

    @override_settings(SYNC_DELETE_STALE_AFTER_DAYS=7)
    def test_reappearing_submission_is_unflagged_not_deleted(
        self,
    ):
        """Flagging clears before deletion is considered, so
        a long outage that resolves loses nothing."""
        self._submission("111", flagged_days_ago=30)

        resp = self._sync(
            [
                {
                    "_id": 111,
                    "_uuid": "uuid-111",
                    "_submission_time": "2026-04-08T02:08:29",
                    "_attachments": [],
                }
            ]
        )

        self.assertEqual(resp.json()["stale_deleted"], 0)
        sub = Submission.objects.get(kobo_id="111")
        self.assertIsNone(sub.missing_from_kobo_at)

    @override_settings(SYNC_DELETE_STALE_AFTER_DAYS=7)
    def test_keeps_rows_with_a_rejection_audit(self):
        """A rejection is a record someone made. It does not
        disappear because an upstream row did."""
        sub = self._submission("111", flagged_days_ago=30)
        RejectionAudit.objects.create(
            plot=self._plot_for(sub),
            submission=sub,
            validator=self.user,
            reason_category=RejectionCategory.OVERLAP,
        )

        resp = self._sync()

        self.assertEqual(resp.json()["stale_deleted"], 0)
        self.assertEqual(resp.json()["stale_kept"], 1)
        self.assertTrue(
            Submission.objects.filter(kobo_id="111").exists()
        )

    @override_settings(SYNC_DELETE_STALE_AFTER_DAYS=7)
    def test_keeps_rows_carrying_a_plot_id(self):
        sub = self._submission("111", flagged_days_ago=30)
        main_plot = MainPlot.objects.create(
            uid="AB-0001",
            form=self.form,
        )
        MainPlotSubmission.objects.create(
            main_plot=main_plot, submission=sub
        )

        resp = self._sync()

        self.assertEqual(resp.json()["stale_kept"], 1)
        self.assertTrue(
            Submission.objects.filter(kobo_id="111").exists()
        )

    @override_settings(SYNC_DELETE_STALE_AFTER_DAYS=7)
    def test_protected_row_does_not_shield_its_neighbours(
        self,
    ):
        """One kept row must not abort the whole sweep."""
        protected = self._submission(
            "111", flagged_days_ago=30
        )
        RejectionAudit.objects.create(
            plot=self._plot_for(protected),
            submission=protected,
            validator=self.user,
            reason_category=RejectionCategory.OVERLAP,
        )
        self._submission("222", flagged_days_ago=30)
        self._submission("333", flagged_days_ago=30)
        # Never flagged: still live in Kobo as far as we know.
        self._submission("444")

        resp = self._sync()

        self.assertEqual(resp.json()["stale_deleted"], 2)
        self.assertEqual(resp.json()["stale_kept"], 1)
        self.assertCountEqual(
            Submission.objects.values_list(
                "kobo_id", flat=True
            ),
            ["111", "444"],
        )
