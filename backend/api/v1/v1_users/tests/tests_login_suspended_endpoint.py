from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser


KOBO_URL = "https://kf.kobotoolbox.org"


@override_settings(USE_TZ=False, TEST_ENV=True)
class LoginSuspendedEndpointTestCase(TestCase):
    """A SUSPENDED user (reached via reject from PENDING or
    deactivate from ACTIVE) is refused at login with 403 and
    the 'suspended' status label."""

    def _make_suspended(self, kobo_username="bob"):
        return SystemUser.objects.create(
            email=f"{kobo_username}@kf.kobotoolbox.org",
            name=kobo_username,
            kobo_url=KOBO_URL,
            kobo_username=kobo_username,
            status=UserStatus.SUSPENDED,
            is_active=False,
        )

    @patch("api.v1.v1_users.views.KoboClient")
    def test_suspended_user_login_returns_403(
        self, mock_client_cls
    ):
        self._make_suspended()
        mock_client_cls.return_value \
            .verify_credentials.return_value = True
        resp = self.client.post(
            "/api/v1/auth/login",
            {
                "kobo_url": KOBO_URL,
                "kobo_username": "bob",
                "kobo_password": "x",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertEqual(body["status"], "suspended")
        self.assertIn(
            "denied", body["message"].lower()
        )
        self.assertNotIn("token", body)

    @patch("api.v1.v1_users.views.KoboClient")
    def test_suspended_user_still_has_single_row(
        self, mock_client_cls
    ):
        """Login for a SUSPENDED user must not create a
        duplicate row."""
        self._make_suspended()
        mock_client_cls.return_value \
            .verify_credentials.return_value = True
        self.client.post(
            "/api/v1/auth/login",
            {
                "kobo_url": KOBO_URL,
                "kobo_username": "bob",
                "kobo_password": "x",
            },
            content_type="application/json",
        )
        self.assertEqual(
            SystemUser.objects.filter(
                kobo_username="bob"
            ).count(),
            1,
        )
