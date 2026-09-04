"""Download endpoint filename handling.

TC02 requires the downloaded file to be named after
the form and the date. The name is carried in
``job.info["download_name"]`` and served through
Content-Disposition.
"""

import os
import tempfile

from django.test import TestCase, override_settings

from api.v1.v1_jobs.constants import JobStatus, JobTypes
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin

DOWNLOAD_URL = "/api/v1/jobs/{job_id}/download/"


class JobsDownloadEndpointTest(
    OdkTestHelperMixin, TestCase
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.header = self.get_auth_header()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        os.makedirs(
            os.path.join(self.tmpdir.name, "exports")
        )

    def _job_with_file(self, name, info_extra=None):
        rel = f"exports/{name}"
        with open(
            os.path.join(self.tmpdir.name, rel), "wb"
        ) as fh:
            fh.write(b"data")
        info = {"file_path": rel}
        info.update(info_extra or {})
        return Jobs.objects.create(
            type=JobTypes.export_geojson,
            status=JobStatus.done,
            created_by=self.user,
            info=info,
        )

    def _download(self, job):
        with override_settings(
            STORAGE_PATH=self.tmpdir.name
        ):
            return self.client.get(
                DOWNLOAD_URL.format(job_id=job.pk),
                **self.header,
            )

    def test_uses_download_name_from_job_info(self):
        job = self._job_with_file(
            "Chain_Form_formX_2026-09-01_143205.geojson",
            {
                "download_name": (
                    "Chain_Form_formX_"
                    "2026-09-01_143205.geojson"
                )
            },
        )

        resp = self._download(job)

        self.assertEqual(resp.status_code, 200)
        disposition = resp["Content-Disposition"]
        self.assertIn("Chain_Form", disposition)
        self.assertIn("formX", disposition)
        self.assertIn("2026-09-01", disposition)

    def test_falls_back_to_basename(self):
        """Jobs created before download_name existed."""
        job = self._job_with_file("legacy_name.geojson")

        resp = self._download(job)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "legacy_name.geojson",
            resp["Content-Disposition"],
        )
