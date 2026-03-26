from unittest.mock import Mock, patch

import requests
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_odk.models import FormMetadata
from api.v1.v1_odk.tests.mixins import OdkTestHelperMixin
from utils.kobo_client import KoboClient, KoboUnauthorizedError


@override_settings(USE_TZ=False, TEST_ENV=True)
class SyncKoboUnauthorizedTest(TestCase, OdkTestHelperMixin):
    """sync/ returns 403 when Kobo rejects
    stored credentials."""

    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="formA",
            name="Form A",
        )

    def test_sync_returns_403_on_asset_detail_401(
        self,
    ):
        """get_asset_detail raises
        KoboUnauthorizedError → 403."""
        with patch("api.v1.v1_odk.views.KoboClient") as mock_cls:
            mock_cls.return_value.get_asset_detail.side_effect = (  # noqa: E501
                KoboUnauthorizedError("Credentials expired")
            )
            resp = self.client.post(
                f"/api/v1/odk/forms/" f"{self.form.asset_uid}/sync/",
                **self.auth,
            )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            resp.json()["error_type"],
            "kobo_unauthorized",
        )

    def test_sync_returns_403_on_fetch_401(self):
        """fetch_all_submissions raises
        KoboUnauthorizedError → 403."""
        with patch("api.v1.v1_odk.views.KoboClient") as mock_cls:
            instance = mock_cls.return_value
            instance.get_asset_detail.return_value = {
                "survey": [],
                "choices": [],
            }
            instance.fetch_all_submissions.side_effect = (  # noqa: E501
                KoboUnauthorizedError("Credentials expired")
            )
            resp = self.client.post(
                f"/api/v1/odk/forms/" f"{self.form.asset_uid}/sync/",
                **self.auth,
            )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            resp.json()["error_type"],
            "kobo_unauthorized",
        )

    def test_sync_502_on_generic_error(self):
        """Non-auth errors still return 502."""
        with patch("api.v1.v1_odk.views.KoboClient") as mock_cls:
            mock_cls.return_value.get_asset_detail.side_effect = (  # noqa: E501
                requests.exceptions.ConnectionError("Connection refused")
            )
            resp = self.client.post(
                f"/api/v1/odk/forms/" f"{self.form.asset_uid}/sync/",
                **self.auth,
            )
        self.assertEqual(resp.status_code, 502)


class CheckResponseTest(TestCase):
    """Unit tests for KoboClient._check_response."""

    def setUp(self):
        self.kobo_client = KoboClient(
            "https://example.com",
            "user",
            "pass",
        )

    def test_401_raises_kobo_unauthorized(self):
        resp = Mock(status_code=401)
        with self.assertRaises(KoboUnauthorizedError):
            self.kobo_client._check_response(resp)

    def test_200_passes(self):
        resp = Mock(status_code=200)
        resp.raise_for_status = Mock()
        self.kobo_client._check_response(resp)
        resp.raise_for_status.assert_called_once()

    def test_500_raises_http_error(self):
        resp = Mock(status_code=500)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError()
        with self.assertRaises(requests.exceptions.HTTPError):
            self.kobo_client._check_response(resp)
