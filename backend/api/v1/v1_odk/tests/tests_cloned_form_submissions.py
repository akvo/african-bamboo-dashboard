from unittest.mock import patch

from django.test import TestCase, override_settings

from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    Submission,
)
from api.v1.v1_odk.tasks import (
    download_submission_attachments,
)
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin

VIEWS = "api.v1.v1_odk.views"

# The same _uuid on two assets is exactly what cloning a Kobo
# project produces, and what used to 500 the sync endpoint with
# "duplicate key value violates unique constraint
# submissions_uuid_key".
SHARED_UUID = "d5a54017-216c-404c-a283-31bc879fccf6"


def kobo_item(kobo_id, uuid_str):
    return {
        "_id": int(kobo_id),
        "_uuid": uuid_str,
        "_submission_time": "2026-04-08T02:08:29",
        "_attachments": [],
    }


# Deletion is a deployment choice, so pin it off here:
# these tests are about flagging, and must not depend on
# whether the developer has SYNC_DELETE_STALE_AFTER_DAYS set.
@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    SYNC_DELETE_STALE_AFTER_DAYS=None,
)
class ClonedFormSyncTest(OdkTestHelperMixin, TestCase):
    """Kobo's _uuid identifies a submission within an asset.

    Cloning a project copies submissions with their original
    _uuid under fresh _id values, so a globally unique column
    made syncing the clone impossible.
    """

    def setUp(self):
        self.user = self.create_kobo_user()
        self.origin = FormMetadata.objects.create(
            asset_uid="formORIGIN", name="Origin"
        )
        self.clone = FormMetadata.objects.create(
            asset_uid="formCLONE", name="Clone of Origin"
        )
        Submission.objects.create(
            uuid=SHARED_UUID,
            form=self.origin,
            kobo_id="763197472",
            submission_time=1700000000000,
            raw_data={},
        )

    def _sync(self, form, returned):
        url = f"/api/v1/odk/forms/{form.asset_uid}/sync/"
        with patch(f"{VIEWS}.KoboClient") as cls, patch(
            f"{VIEWS}.async_task"
        ), patch(
            f"{VIEWS}.sync_form_questions", return_value=0
        ):
            client = cls.return_value
            client.get_asset_detail.return_value = {}
            client.fetch_all_submissions.return_value = (
                returned
            )
            return self.client.post(
                url, **self.get_auth_header()
            )

    def test_cloned_form_syncs_shared_uuid(self):
        """The production regression: syncing a clone whose
        submission carries the origin's _uuid."""
        resp = self._sync(
            self.clone,
            [kobo_item("999888777", SHARED_UUID)],
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Submission.objects.filter(
                uuid=SHARED_UUID
            ).count(),
            2,
        )
        self.assertTrue(
            Submission.objects.filter(
                uuid=SHARED_UUID,
                form=self.clone,
                kobo_id="999888777",
            ).exists()
        )

    def test_edit_keeps_id_and_refreshes_uuid(self):
        """Editing in Kobo keeps _id and changes _uuid.

        Observed on 4 of 128 rows in one form. Keying the
        upsert on uuid treated each edit as a new submission
        and collided on (form, kobo_id).
        """
        origin_sub = Submission.objects.get(
            form=self.origin, uuid=SHARED_UUID
        )
        original_pk = origin_sub.pk
        plot = Plot.objects.create(
            plot_name="Edited Plot",
            form=self.origin,
            region="R",
            sub_region="S",
            created_at=1700000000000,
            submission=origin_sub,
        )

        resp = self._sync(
            self.origin,
            # Same _id, new _uuid: an edit.
            [kobo_item("763197472", "301180e4-new-uuid")],
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Submission.objects.filter(
                form=self.origin
            ).count(),
            1,
        )
        origin_sub.refresh_from_db()
        self.assertEqual(
            origin_sub.uuid, "301180e4-new-uuid"
        )
        # Same row, so the plot and everything hanging off
        # the submission survive the edit.
        self.assertEqual(origin_sub.pk, original_pk)
        plot.refresh_from_db()
        self.assertEqual(plot.submission_id, original_pk)

    def test_reimport_with_new_id_adds_a_row(self):
        """A re-import keeps _uuid and takes a new _id.

        The old _id is gone from Kobo, so the superseded row
        is left for the stale sweep rather than being
        silently merged into the new one.
        """
        resp = self._sync(
            self.origin,
            # Same _uuid, different _id.
            [kobo_item("808919788", SHARED_UUID)],
        )

        self.assertEqual(resp.status_code, 200)
        rows = Submission.objects.filter(
            form=self.origin, uuid=SHARED_UUID
        )
        self.assertEqual(rows.count(), 2)
        # The row Kobo no longer returns is flagged, so the
        # UI blocks approve/reject on it.
        superseded = rows.get(kobo_id="763197472")
        self.assertIsNotNone(
            superseded.missing_from_kobo_at
        )
        current = rows.get(kobo_id="808919788")
        self.assertIsNone(current.missing_from_kobo_at)

    def test_same_uuid_twice_on_one_form_is_allowed(self):
        """uuid carries no uniqueness. A re-import legitimately
        produces two rows sharing one instance uuid."""
        Submission.objects.create(
            uuid=SHARED_UUID,
            form=self.origin,
            kobo_id="another-id",
            submission_time=1700000000000,
            raw_data={},
        )
        self.assertEqual(
            Submission.objects.filter(
                form=self.origin, uuid=SHARED_UUID
            ).count(),
            2,
        )


# Deletion is a deployment choice, so pin it off here:
# these tests are about flagging, and must not depend on
# whether the developer has SYNC_DELETE_STALE_AFTER_DAYS set.
@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    SYNC_DELETE_STALE_AFTER_DAYS=None,
)
class ClonedFormLookupTest(OdkTestHelperMixin, TestCase):
    """A bare /submissions/<uuid>/ is ambiguous once a clone
    exists. Answering with whichever row sorted first would
    show the wrong form's data, or apply a decision to it."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.origin = FormMetadata.objects.create(
            asset_uid="formORIGIN", name="Origin"
        )
        self.clone = FormMetadata.objects.create(
            asset_uid="formCLONE", name="Clone of Origin"
        )
        self.origin_sub = Submission.objects.create(
            uuid=SHARED_UUID,
            form=self.origin,
            kobo_id="111",
            submission_time=1700000000000,
            raw_data={},
            instance_name="from-origin",
        )
        self.clone_sub = Submission.objects.create(
            uuid=SHARED_UUID,
            form=self.clone,
            kobo_id="222",
            submission_time=1700000000000,
            raw_data={},
            instance_name="from-clone",
        )
        self.url = f"/api/v1/odk/submissions/{SHARED_UUID}/"

    def test_ambiguous_uuid_returns_409(self):
        resp = self.client.get(
            self.url, **self.get_auth_header()
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            resp.json()["error_type"],
            "ambiguous_submission",
        )

    def test_asset_uid_resolves_the_right_form(self):
        for form, expected in (
            (self.origin, "from-origin"),
            (self.clone, "from-clone"),
        ):
            resp = self.client.get(
                f"{self.url}?asset_uid={form.asset_uid}",
                **self.get_auth_header(),
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(
                resp.json()["instance_name"], expected
            )

    def test_patch_applies_to_the_named_form_only(self):
        """The decision must land on the form the validator
        was looking at, not its clone."""
        with patch(f"{VIEWS}.async_task"):
            resp = self.client.patch(
                f"{self.url}"
                f"?asset_uid={self.clone.asset_uid}",
                {"approval_status": 1},
                content_type="application/json",
                **self.get_auth_header(),
            )
        self.assertEqual(resp.status_code, 200)

        self.clone_sub.refresh_from_db()
        self.origin_sub.refresh_from_db()
        self.assertEqual(self.clone_sub.approval_status, 1)
        self.assertIsNone(
            self.origin_sub.approval_status
        )

    def test_unknown_uuid_still_404s(self):
        resp = self.client.get(
            "/api/v1/odk/submissions/no-such-uuid/",
            **self.get_auth_header(),
        )
        self.assertEqual(resp.status_code, 404)

    def test_unambiguous_uuid_needs_no_asset_uid(self):
        """Most submissions are not cloned, so the common
        case must keep working without the extra param."""
        self.clone_sub.delete()
        resp = self.client.get(
            self.url, **self.get_auth_header()
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["instance_name"], "from-origin"
        )

    def test_attachment_task_picks_the_named_form(self):
        """download_submission_attachments used .get(uuid=),
        which now raises MultipleObjectsReturned."""
        with patch(
            "api.v1.v1_odk.tasks.KoboClient"
        ) as cls:
            download_submission_attachments(
                "https://kf.kobotoolbox.org",
                "kobouser",
                self.user.kobo_password,
                SHARED_UUID,
                self.clone.asset_uid,
            )
            # No attachments in raw_data, so it returns before
            # contacting Kobo. Reaching here at all means the
            # lookup resolved to exactly one row.
            cls.assert_not_called()
