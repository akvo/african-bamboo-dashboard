from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser


KOBO_URL = "https://kf.kobotoolbox.org"


@override_settings(USE_TZ=False, TEST_ENV=True)
class LoginPendingEndpointTestCase(TestCase):
    """A user whose status is PENDING cannot log in — the Kobo
    credential check may succeed but the approval gate
    returns 403 with a 'pending' status label."""

    @patch("api.v1.v1_users.views.KoboClient")
    def test_first_time_login_creates_pending_row_and_403s(
        self, mock_client_cls
    ):
        mock_client_cls.return_value \
            .verify_credentials.return_value = True
        resp = self.client.post(
            "/api/v1/auth/login",
            {
                "kobo_url": KOBO_URL,
                "kobo_username": "alice",
                "kobo_password": "x",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertEqual(body["status"], "pending")
        self.assertIn("awaiting", body["message"].lower())
        self.assertNotIn("token", body)
        self.assertTrue(
            SystemUser.objects.filter(
                kobo_username="alice",
                status=UserStatus.PENDING,
            ).exists()
        )

    @patch("api.v1.v1_users.views.KoboClient")
    def test_invited_user_with_matching_email_is_bound(
        self, mock_client_cls
    ):
        """An invite (PENDING + no kobo_username) whose email
        matches the email Kobo returns should be bound and
        flipped to ACTIVE on first login, producing a JWT."""
        SystemUser.objects.create(
            email="alice@example.com",
            name="Alice",
            status=UserStatus.PENDING,
            is_active=False,
        )
        mock_client_cls.return_value \
            .verify_credentials.return_value = {
                "email": "alice@example.com",
                "name": "Alice Kobo",
            }
        resp = self.client.post(
            "/api/v1/auth/login",
            {
                "kobo_url": KOBO_URL,
                "kobo_username": "alice",
                "kobo_password": "x",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("token", body)
        u = SystemUser.objects.get(email="alice@example.com")
        self.assertEqual(u.status, UserStatus.ACTIVE)
        self.assertEqual(u.kobo_username, "alice")

    @patch("api.v1.v1_users.views.KoboClient")
    def test_pending_user_with_kobo_creds_still_403s(
        self, mock_client_cls
    ):
        """An already-bound but not-yet-approved user (e.g.
        after repeating a silent-pending login) must keep
        getting 403 until an admin approves."""
        SystemUser.objects.create(
            email="bob@kf.kobotoolbox.org",
            name="bob",
            kobo_url=KOBO_URL,
            kobo_username="bob",
            status=UserStatus.PENDING,
            is_active=False,
        )
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
        self.assertEqual(
            resp.json()["status"], "pending"
        )
