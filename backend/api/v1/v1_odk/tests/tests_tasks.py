import logging
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.tasks import (
    sync_kobo_validation_status,
)
from utils.encryption import encrypt
from utils.kobo_client import KoboClient


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    SECRET_KEY="test-secret-key-for-encryption",
)
class SyncKoboValidationStatusTest(TestCase):
    def setUp(self):
        self.kobo_url = "https://kf.kobotoolbox.org"
        self.kobo_username = "testuser"
        self.kobo_password_enc = encrypt("testpass")
        self.asset_uid = "aXYZ123"
        self.kobo_ids = [100, 101]

    @patch(
        "api.v1.v1_odk.tasks.KoboClient"
    )
    def test_sync_success(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        sync_kobo_validation_status(
            self.kobo_url,
            self.kobo_username,
            self.kobo_password_enc,
            self.asset_uid,
            self.kobo_ids,
            ApprovalStatusTypes.APPROVED,
        )

        mock_cls.assert_called_once_with(
            self.kobo_url,
            self.kobo_username,
            "testpass",
        )
        mock_client.update_validation_statuses.assert_called_once_with(  # noqa: E501
            self.asset_uid,
            self.kobo_ids,
            "validation_status_approved",
        )

    @patch(
        "api.v1.v1_odk.tasks.KoboClient"
    )
    def test_sync_failure_logs_no_exception(
        self, mock_cls,
    ):
        mock_client = MagicMock()
        mock_client.update_validation_statuses.side_effect = (  # noqa: E501
            Exception("Kobo API down")
        )
        mock_cls.return_value = mock_client

        with self.assertLogs(
            "api.v1.v1_odk.tasks",
            level=logging.ERROR,
        ) as cm:
            sync_kobo_validation_status(
                self.kobo_url,
                self.kobo_username,
                self.kobo_password_enc,
                self.asset_uid,
                self.kobo_ids,
                ApprovalStatusTypes.REJECTED,
            )

        self.assertTrue(
            any(
                "Failed to sync" in msg
                for msg in cm.output
            )
        )


class KoboClientValidationStatusTest(
    SimpleTestCase,
):
    """Unit test for KoboClient
    .update_validation_statuses()."""

    @patch("utils.kobo_client.requests.Session")
    def test_update_validation_statuses(
        self, mock_session_cls,
    ):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_session.patch.return_value = mock_resp
        mock_session_cls.return_value = (
            mock_session
        )

        client = KoboClient(
            "https://kf.kobotoolbox.org",
            "user",
            "pass",
        )
        client.update_validation_statuses(
            "aXYZ",
            [10, 20],
            "validation_status_approved",
        )

        mock_session.patch.assert_called_once()
        call_args = mock_session.patch.call_args
        self.assertIn(
            "/api/v2/assets/aXYZ"
            "/data/validation_statuses/",
            call_args[0][0],
        )
        payload = call_args[1]["json"]
        self.assertEqual(
            payload["payload"]["submission_ids"],
            [10, 20],
        )
        self.assertEqual(
            payload["payload"][
                "validation_status.uid"
            ],
            "validation_status_approved",
        )
        mock_resp.raise_for_status.assert_called_once()
