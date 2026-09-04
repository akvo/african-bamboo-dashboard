"""Job status endpoint, including the stale reaper.

TC02's symptom was an export that never finished and
never errored: the job sat at ``pending`` because
nothing was consuming the queue, and the client polled
it forever. These tests cover the endpoint's escape
hatch and the newly exposed failure reason.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from api.v1.v1_jobs.constants import (
    JOB_STALE_SECONDS,
    JobStatus,
    JobTypes,
)
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin
from api.v1.v1_users.models import SystemUser

JOB_URL = "/api/v1/jobs/{job_id}/"


class JobsStatusEndpointTest(
    OdkTestHelperMixin, TestCase
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.header = self.get_auth_header()

    def _job(self, status, age_seconds=0):
        job = Jobs.objects.create(
            type=JobTypes.export_xlsx,
            status=status,
            created_by=self.user,
            info={"form_id": "abc"},
        )
        if age_seconds:
            # created is auto_now_add, so it can only
            # be backdated with a queryset update.
            Jobs.objects.filter(pk=job.pk).update(
                created=(
                    timezone.now()
                    - timedelta(seconds=age_seconds)
                )
            )
            job.refresh_from_db()
        return job

    def _get(self, job):
        return self.client.get(
            JOB_URL.format(job_id=job.pk),
            **self.header,
        )

    def test_status_includes_result_on_failure(self):
        job = self._job(JobStatus.failed)
        job.result = "boom: something broke"
        job.save()

        resp = self._get(job)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["result"],
            "boom: something broke",
        )

    def test_status_result_null_when_pending(self):
        job = self._job(JobStatus.pending)

        resp = self._get(job)

        self.assertEqual(resp.json()["status"], "pending")
        self.assertIsNone(resp.json()["result"])

    def test_stale_pending_job_marked_failed(self):
        """The core TC02 escape hatch."""
        job = self._job(
            JobStatus.pending,
            age_seconds=JOB_STALE_SECONDS + 60,
        )

        resp = self._get(job)

        self.assertEqual(resp.json()["status"], "failed")
        self.assertIn(
            "worker", resp.json()["result"]
        )
        job.refresh_from_db()
        self.assertEqual(
            job.status, JobStatus.failed
        )

    def test_stale_on_progress_job_marked_failed(self):
        """A worker killed mid-run leaves on_progress."""
        job = self._job(
            JobStatus.on_progress,
            age_seconds=JOB_STALE_SECONDS + 60,
        )

        resp = self._get(job)

        self.assertEqual(resp.json()["status"], "failed")

    def test_fresh_pending_job_is_left_alone(self):
        job = self._job(
            JobStatus.pending,
            age_seconds=JOB_STALE_SECONDS - 60,
        )

        resp = self._get(job)

        self.assertEqual(resp.json()["status"], "pending")
        job.refresh_from_db()
        self.assertEqual(
            job.status, JobStatus.pending
        )

    def test_done_job_is_never_reaped(self):
        """A slow but successful export must survive."""
        job = self._job(
            JobStatus.done,
            age_seconds=JOB_STALE_SECONDS * 10,
        )

        resp = self._get(job)

        self.assertEqual(resp.json()["status"], "done")

    def test_other_users_job_returns_404(self):
        other = SystemUser.objects.create_superuser(
            email="other-jobs@test.local",
            password="Changeme123",
            name="other",
        )
        job = Jobs.objects.create(
            type=JobTypes.export_xlsx,
            status=JobStatus.done,
            created_by=other,
        )

        resp = self._get(job)

        self.assertEqual(resp.status_code, 404)
