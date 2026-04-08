from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


def _make_kobo_submission(
    uuid, kobo_id, validation_status=None
):
    """Build a minimal Kobo submission dict."""
    item = {
        "_uuid": uuid,
        "_id": kobo_id,
        "_submission_time": (
            "2024-01-15T10:30:00+00:00"
        ),
        "_submitted_by": "user1",
        "meta/instanceName": f"inst-{uuid}",
        "_geolocation": [9.0, 38.7],
        "_tags": [],
    }
    if validation_status is not None:
        item["_validation_status"] = (
            validation_status
        )
    return item


@override_settings(USE_TZ=False, TEST_ENV=True)
class SyncValidationStatusTest(
    TestCase, OdkTestHelperMixin
):
    """Sync should map Kobo _validation_status
    to Submission.approval_status."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="vs-form",
            name="Validation Status Form",
        )

    def _sync(self, submissions):
        with patch(
            "api.v1.v1_odk.views.KoboClient"
        ) as mock_cls:
            mock = mock_cls.return_value
            mock.fetch_all_submissions.return_value = (  # noqa: E501
                submissions
            )
            resp = self.client.post(
                "/api/v1/odk/forms/"
                "vs-form/sync/",
                content_type=(
                    "application/json"
                ),
                **self.auth,
            )
        return resp

    def test_approved_status_synced(self):
        sub = _make_kobo_submission(
            "uuid-ap",
            1,
            {
                "uid": (
                    "validation_status"
                    "_approved"
                ),
                "label": "Approved",
            },
        )
        self._sync([sub])
        obj = Submission.objects.get(
            uuid="uuid-ap"
        )
        self.assertEqual(
            obj.approval_status,
            ApprovalStatusTypes.APPROVED,
        )

    def test_rejected_status_synced(self):
        sub = _make_kobo_submission(
            "uuid-rej",
            2,
            {
                "uid": (
                    "validation_status"
                    "_not_approved"
                ),
                "label": "Not Approved",
            },
        )
        self._sync([sub])
        obj = Submission.objects.get(
            uuid="uuid-rej"
        )
        self.assertEqual(
            obj.approval_status,
            ApprovalStatusTypes.REJECTED,
        )

    def test_on_hold_maps_to_pending(self):
        sub = _make_kobo_submission(
            "uuid-oh",
            3,
            {
                "uid": (
                    "validation_status"
                    "_on_hold"
                ),
                "label": "On Hold",
            },
        )
        self._sync([sub])
        obj = Submission.objects.get(
            uuid="uuid-oh"
        )
        self.assertIsNone(obj.approval_status)

    def test_no_validation_status_is_pending(
        self,
    ):
        sub = _make_kobo_submission(
            "uuid-none", 4
        )
        self._sync([sub])
        obj = Submission.objects.get(
            uuid="uuid-none"
        )
        self.assertIsNone(obj.approval_status)

    def test_empty_validation_status_is_pending(
        self,
    ):
        sub = _make_kobo_submission(
            "uuid-empty", 5, {}
        )
        self._sync([sub])
        obj = Submission.objects.get(
            uuid="uuid-empty"
        )
        self.assertIsNone(obj.approval_status)

    def test_resync_updates_status(self):
        """Re-syncing a submission updates its
        approval_status from Kobo."""
        sub = _make_kobo_submission(
            "uuid-resync", 6
        )
        self._sync([sub])
        obj = Submission.objects.get(
            uuid="uuid-resync"
        )
        self.assertIsNone(obj.approval_status)

        # Kobo now shows it as approved
        sub["_validation_status"] = {
            "uid": (
                "validation_status_approved"
            ),
            "label": "Approved",
        }
        self._sync([sub])
        obj.refresh_from_db()
        self.assertEqual(
            obj.approval_status,
            ApprovalStatusTypes.APPROVED,
        )

    def test_full_sync_captures_status_change(
        self,
    ):
        """Full sync picks up validation-status
        changes even when _submission_time is
        unchanged (the bug that incremental sync
        missed)."""
        sub = _make_kobo_submission(
            "uuid-full", 7,
            {
                "uid": (
                    "validation_status_approved"
                ),
                "label": "Approved",
            },
        )
        self._sync([sub])
        obj = Submission.objects.get(
            uuid="uuid-full"
        )
        self.assertEqual(
            obj.approval_status,
            ApprovalStatusTypes.APPROVED,
        )

        # Status changed on Kobo to rejected,
        # _submission_time stays the same
        sub["_validation_status"] = {
            "uid": (
                "validation_status"
                "_not_approved"
            ),
            "label": "Not Approved",
        }
        resp = self._sync([sub])
        data = resp.json()
        self.assertEqual(data["updated"], 1)
        self.assertEqual(data["created"], 0)
        obj.refresh_from_db()
        self.assertEqual(
            obj.approval_status,
            ApprovalStatusTypes.REJECTED,
        )

    def test_full_sync_updates_raw_data(self):
        """Full sync updates raw_data when field
        values change on Kobo."""
        sub = _make_kobo_submission(
            "uuid-raw", 8
        )
        sub["farmer_name"] = "Original"
        self._sync([sub])
        obj = Submission.objects.get(
            uuid="uuid-raw"
        )
        self.assertEqual(
            obj.raw_data["farmer_name"],
            "Original",
        )

        # Field edited on Kobo, same
        # _submission_time
        sub["farmer_name"] = "Edited"
        self._sync([sub])
        obj.refresh_from_db()
        self.assertEqual(
            obj.raw_data["farmer_name"],
            "Edited",
        )
