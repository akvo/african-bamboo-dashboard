from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    Submission,
)


def _raw_with_validation(uid):
    """Build raw_data with a _validation_status."""
    return {
        "_validation_status": {
            "uid": uid,
            "timestamp": 1773127236,
            "by_whom": "kobouser",
        },
    }


class BackfillApprovalStatusTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="backfill-form",
            name="Backfill Form",
        )

    def _create_sub(
        self,
        uuid,
        kobo_id,
        raw,
        approval_status=None,
        instance_name=None,
    ):
        return Submission.objects.create(
            uuid=uuid,
            form=self.form,
            kobo_id=kobo_id,
            submission_time=1700000000000,
            raw_data=raw,
            approval_status=approval_status,
            instance_name=instance_name,
        )

    def test_backfill_updates_mismatched_status(
        self,
    ):
        """Submission with not_approved in raw_data
        but approval_status=None should be updated
        to REJECTED."""
        raw = _raw_with_validation(
            "validation_status_not_approved"
        )
        sub = self._create_sub(
            "bf-1", "1", raw,
            approval_status=None,
            instance_name="enum-001",
        )

        out = StringIO()
        call_command(
            "backfill_approval_status",
            stdout=out,
        )

        sub.refresh_from_db()
        self.assertEqual(
            sub.approval_status,
            ApprovalStatusTypes.REJECTED,
        )
        self.assertIn("updated 1", out.getvalue())

    def test_backfill_approved_status(self):
        """Submission with approved in raw_data
        should get approval_status=APPROVED."""
        raw = _raw_with_validation(
            "validation_status_approved"
        )
        sub = self._create_sub(
            "bf-2", "2", raw,
            approval_status=None,
            instance_name="enum-002",
        )

        out = StringIO()
        call_command(
            "backfill_approval_status",
            stdout=out,
        )

        sub.refresh_from_db()
        self.assertEqual(
            sub.approval_status,
            ApprovalStatusTypes.APPROVED,
        )

    def test_backfill_on_hold_sets_none(self):
        """on_hold maps to None; if already None,
        should be skipped."""
        raw = _raw_with_validation(
            "validation_status_on_hold"
        )
        sub = self._create_sub(
            "bf-3", "3", raw,
            approval_status=None,
            instance_name="enum-003",
        )

        out = StringIO()
        call_command(
            "backfill_approval_status",
            stdout=out,
        )

        sub.refresh_from_db()
        self.assertIsNone(sub.approval_status)
        self.assertIn("skipped 1", out.getvalue())

    def test_backfill_skips_already_correct(self):
        """Submission already matching Kobo status
        should be skipped."""
        raw = _raw_with_validation(
            "validation_status_not_approved"
        )
        sub = self._create_sub(
            "bf-4", "4", raw,
            approval_status=(
                ApprovalStatusTypes.REJECTED
            ),
            instance_name="enum-004",
        )

        out = StringIO()
        call_command(
            "backfill_approval_status",
            stdout=out,
        )

        sub.refresh_from_db()
        self.assertEqual(
            sub.approval_status,
            ApprovalStatusTypes.REJECTED,
        )
        self.assertIn("updated 0", out.getvalue())
        self.assertIn("skipped 1", out.getvalue())

    def test_backfill_no_validation_status(self):
        """Submission without _validation_status
        in raw_data should be skipped."""
        sub = self._create_sub(
            "bf-5", "5",
            {"some_field": "value"},
            instance_name="enum-005",
        )

        out = StringIO()
        call_command(
            "backfill_approval_status",
            stdout=out,
        )

        sub.refresh_from_db()
        self.assertIsNone(sub.approval_status)
        self.assertIn("skipped 1", out.getvalue())

    def test_dry_run_no_changes(self):
        """--dry-run should report counts but
        not modify the database."""
        raw = _raw_with_validation(
            "validation_status_not_approved"
        )
        sub = self._create_sub(
            "bf-6", "6", raw,
            approval_status=None,
            instance_name="enum-006",
        )

        out = StringIO()
        call_command(
            "backfill_approval_status",
            "--dry-run",
            stdout=out,
        )

        sub.refresh_from_db()
        self.assertIsNone(sub.approval_status)
        output = out.getvalue()
        self.assertIn("DRY RUN", output)
        self.assertIn("would update 1", output)

    def test_instance_name_filter(self):
        """--instance-name should only process
        the matching submission."""
        raw = _raw_with_validation(
            "validation_status_not_approved"
        )
        sub_a = self._create_sub(
            "bf-7a", "7", raw,
            approval_status=None,
            instance_name="target-sub",
        )
        sub_b = self._create_sub(
            "bf-7b", "8", raw,
            approval_status=None,
            instance_name="other-sub",
        )

        out = StringIO()
        call_command(
            "backfill_approval_status",
            "--instance-name",
            "target-sub",
            stdout=out,
        )

        sub_a.refresh_from_db()
        sub_b.refresh_from_db()
        self.assertEqual(
            sub_a.approval_status,
            ApprovalStatusTypes.REJECTED,
        )
        self.assertIsNone(sub_b.approval_status)
        self.assertIn("updated 1", out.getvalue())
        self.assertIn(
            "Checked 1", out.getvalue()
        )
