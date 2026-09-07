"""Export filename construction.

TC02 expects the downloaded file to carry the form
name and the date. The names must also stay unique on
disk: utils.storage.upload is a plain copy into a flat
folder, so a collision silently overwrites another
user's export while their job row still points at the
path -- handing them someone else's data.
"""

import os
import tempfile
from datetime import datetime, timezone

from django.test import TestCase, override_settings

from api.v1.v1_odk.export import (
    build_export_filename,
    slugify_form_name,
)
from api.v1.v1_odk.models import FormMetadata

WHEN = datetime(
    2026, 9, 1, 14, 32, 5, tzinfo=timezone.utc
)


class SlugifyFormNameTest(TestCase):
    def test_spaces_and_punctuation_become_underscores(
        self,
    ):
        self.assertEqual(
            slugify_form_name("Bamboo Farm (2025)"),
            "Bamboo_Farm_2025",
        )

    def test_non_ascii_is_stripped(self):
        """\\w would keep these and break the header."""
        slug = slugify_form_name("Bamboo አማርኛ Survey")

        self.assertTrue(slug.isascii())
        self.assertIn("Bamboo", slug)
        self.assertIn("Survey", slug)

    def test_empty_name_falls_back(self):
        self.assertEqual(
            slugify_form_name(""), "export"
        )
        self.assertEqual(
            slugify_form_name(None), "export"
        )

    def test_long_name_is_truncated(self):
        self.assertLessEqual(
            len(slugify_form_name("A" * 200)), 60
        )


class BuildExportFilenameTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="aG7kXm2PqR9vLd3",
            name="Bamboo Survey",
        )
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.exports = os.path.join(
            self.tmpdir.name, "exports"
        )
        os.makedirs(self.exports)

    def _build(self, job_id=1):
        with override_settings(
            STORAGE_PATH=self.tmpdir.name
        ):
            return build_export_filename(
                self.form, job_id, when=WHEN
            )

    def test_contains_name_id_date_and_time(self):
        stem = self._build()

        self.assertEqual(
            stem,
            "Bamboo_Survey_aG7kXm2PqR9vLd3"
            "_2026-09-01_143205",
        )

    def test_appends_job_id_on_collision(self):
        """Two exports in the same second must differ.

        Without this the second overwrites the first
        and the first job row serves the wrong file.
        """
        first = self._build(job_id=1)
        with open(
            os.path.join(
                self.exports, f"{first}.geojson"
            ),
            "wb",
        ) as fh:
            fh.write(b"{}")

        second = self._build(job_id=2)

        self.assertNotEqual(first, second)
        self.assertTrue(second.endswith("_2"))
