import os
import shutil
from io import BytesIO, StringIO
from unittest.mock import MagicMock, patch

from PIL import Image

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import (
    FormMetadata,
    Submission,
)
from api.v1.v1_users.models import SystemUser
from utils.encryption import encrypt


def _make_jpeg_bytes(width=10, height=10):
    """Create a minimal JPEG byte buffer."""
    img = Image.new("RGB", (width, height))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


STORAGE = "/tmp/test_storage"

RAW_DATA_WITH_IMAGE = {
    "_attachments": [
        {
            "mimetype": "image/jpeg",
            "uid": "att1",
            "media_file_basename": "deed.jpg",
            "download_large_url": (
                "http://kobo/large/att1"
            ),
        }
    ]
}


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    SECRET_KEY="test-secret-key-for-encryption",
    STORAGE_PATH=STORAGE,
)
class FixAttachmentOrientationTest(TestCase):
    def setUp(self):
        self.form = FormMetadata.objects.create(
            asset_uid="orient-form",
            name="Orientation Form",
        )

    def tearDown(self):
        shutil.rmtree(
            os.path.join(STORAGE, "attachments"),
            ignore_errors=True,
        )

    def _create_sub(self, uuid, kobo_id, raw):
        return Submission.objects.create(
            uuid=uuid,
            form=self.form,
            kobo_id=kobo_id,
            submission_time=1700000000000,
            raw_data=raw,
        )

    def _write_file(
        self, sub_uuid, filename, data
    ):
        dest_dir = os.path.join(
            STORAGE,
            "attachments",
            sub_uuid,
        )
        os.makedirs(dest_dir, exist_ok=True)
        path = os.path.join(dest_dir, filename)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_dry_run_does_not_modify_files(self):
        sub = self._create_sub(
            "sub-o1", "1", RAW_DATA_WITH_IMAGE
        )
        data = _make_jpeg_bytes()
        path = self._write_file(
            sub.uuid, "att1.jpg", data
        )

        out = StringIO()
        call_command(
            "fix_attachment_orientation",
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("DRY RUN", output)
        self.assertIn("Would fix", output)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), data)

    def test_fixes_local_file(self):
        sub = self._create_sub(
            "sub-o2", "2", RAW_DATA_WITH_IMAGE
        )
        data = _make_jpeg_bytes()
        self._write_file(
            sub.uuid, "att1.jpg", data
        )

        out = StringIO()
        call_command(
            "fix_attachment_orientation",
            "--submission-uuid",
            sub.uuid,
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("attachments", output)

    def test_skips_missing_file(self):
        self._create_sub(
            "sub-o3", "3", RAW_DATA_WITH_IMAGE
        )

        out = StringIO()
        call_command(
            "fix_attachment_orientation",
            "--submission-uuid",
            "sub-o3",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("skipped 1", output)

    def test_skips_submission_without_images(
        self,
    ):
        self._create_sub(
            "sub-o4",
            "4",
            {"_attachments": []},
        )

        out = StringIO()
        call_command(
            "fix_attachment_orientation",
            "--submission-uuid",
            "sub-o4",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Fixed 0", output)

    def test_handles_corrupt_file(self):
        sub = self._create_sub(
            "sub-o5", "5", RAW_DATA_WITH_IMAGE
        )
        self._write_file(
            sub.uuid,
            "att1.jpg",
            b"not-an-image",
        )

        out = StringIO()
        with self.assertLogs(
            "api.v1.v1_odk.management.commands"
            ".fix_attachment_orientation",
            level="WARNING",
        ):
            call_command(
                "fix_attachment_orientation",
                "--submission-uuid",
                sub.uuid,
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("errors 1", output)

    def test_filter_by_submission_uuid(self):
        self._create_sub(
            "sub-o6a", "6", RAW_DATA_WITH_IMAGE
        )
        sub_b = self._create_sub(
            "sub-o6b", "7", RAW_DATA_WITH_IMAGE
        )
        self._write_file(
            "sub-o6a",
            "att1.jpg",
            _make_jpeg_bytes(),
        )
        self._write_file(
            "sub-o6b",
            "att1.jpg",
            _make_jpeg_bytes(),
        )

        out = StringIO()
        call_command(
            "fix_attachment_orientation",
            "--submission-uuid",
            sub_b.uuid,
            stdout=out,
        )

        output = out.getvalue()
        self.assertNotIn("sub-o6a", output)

    @patch(
        "api.v1.v1_odk.management.commands"
        ".fix_attachment_orientation.KoboClient"
    )
    def test_redownload_skipped_without_user(
        self, mock_cls
    ):
        self._create_sub(
            "sub-o7", "8", RAW_DATA_WITH_IMAGE
        )
        self._write_file(
            "sub-o7",
            "att1.jpg",
            _make_jpeg_bytes(),
        )

        out = StringIO()
        call_command(
            "fix_attachment_orientation",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn(
            "No Kobo user found", output
        )
        mock_cls.assert_not_called()

    @patch(
        "api.v1.v1_odk.management.commands"
        ".fix_attachment_orientation.KoboClient"
    )
    def test_redownload_from_large_url(
        self, mock_cls
    ):
        user = (
            SystemUser.objects.create_superuser(
                email="kobo@test.local",
                password="Changeme123",
                name="kobouser",
            )
        )
        user.kobo_url = (
            "https://kf.kobotoolbox.org"
        )
        user.kobo_username = "kobouser"
        user.kobo_password = encrypt("kobopass")
        user.save()

        sub = self._create_sub(
            "sub-o8", "9", RAW_DATA_WITH_IMAGE
        )
        self._write_file(
            sub.uuid,
            "att1.jpg",
            _make_jpeg_bytes(),
        )

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = _make_jpeg_bytes()
        mock_client.session.get.return_value = (
            mock_resp
        )
        mock_cls.return_value = mock_client

        out = StringIO()
        call_command(
            "fix_attachment_orientation",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Re-downloaded 1", output)
        mock_client.session.get.assert_called_once()
        call_url = (
            mock_client.session.get.call_args[0][
                0
            ]
        )
        self.assertIn("large", call_url)

    def test_redownload_skipped_for_single_sub(
        self,
    ):
        """--submission-uuid should NOT trigger
        the re-download phase."""
        sub = self._create_sub(
            "sub-o9", "10", RAW_DATA_WITH_IMAGE
        )
        self._write_file(
            sub.uuid,
            "att1.jpg",
            _make_jpeg_bytes(),
        )

        out = StringIO()
        call_command(
            "fix_attachment_orientation",
            "--submission-uuid",
            sub.uuid,
            stdout=out,
        )

        output = out.getvalue()
        self.assertNotIn("Re-downloaded", output)
        self.assertNotIn(
            "No Kobo user", output
        )
