from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser


KOBO_URL = "https://kf.kobotoolbox.org"


def _make_active_user(**overrides):
    defaults = {
        "email": "testuser@test.local",
        "name": "testuser",
        "kobo_url": KOBO_URL,
        "kobo_username": "testuser",
        "status": UserStatus.ACTIVE,
        "is_active": True,
    }
    defaults.update(overrides)
    return SystemUser.objects._create_user(
        password="internal", **defaults
    )


@override_settings(USE_TZ=False, TEST_ENV=True)
class LoginTestCase(TestCase):

    @patch("api.v1.v1_users.views.KoboClient")
    def test_successfully_logged_in(self, mock_client_cls):
        # Approval gate: an ACTIVE user must already exist for
        # the Kobo-valid login to succeed with 200 + JWT.
        _make_active_user()
        mock_client_cls.return_value \
            .verify_credentials.return_value = True
        payload = {
            "kobo_url": KOBO_URL,
            "kobo_username": "testuser",
            "kobo_password": "testpass",
        }
        req = self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        self.assertEqual(req.status_code, 200)
        res = req.json()
        self.assertEqual(
            list(res),
            ["user", "token", "expiration_time"],
        )
        self.assertEqual(
            list(res["user"]),
            [
                "id",
                "name",
                "email",
                "kobo_url",
                "kobo_username",
            ],
        )
        self.assertEqual(
            res["user"]["kobo_username"], "testuser"
        )
        self.assertEqual(
            res["user"]["kobo_url"], KOBO_URL
        )

    @patch("api.v1.v1_users.views.KoboClient")
    def test_new_user_row_created_but_pending(
        self, mock_client_cls
    ):
        """First-time Kobo login creates a row (silent PENDING)
        but the approval gate returns 403 instead of a JWT."""
        mock_client_cls.return_value \
            .verify_credentials.return_value = True
        payload = {
            "kobo_url": KOBO_URL,
            "kobo_username": "newuser",
            "kobo_password": "newpass",
        }
        req = self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        self.assertEqual(req.status_code, 403)
        user = SystemUser.objects.get(kobo_username="newuser")
        self.assertEqual(user.status, UserStatus.PENDING)

    @patch("api.v1.v1_users.views.KoboClient")
    def test_updates_existing_user_credentials(
        self, mock_client_cls
    ):
        """An ACTIVE user logging in again with a new password
        updates the stored encrypted password and still gets
        200 + JWT. Only one row exists throughout."""
        _make_active_user()
        mock_client_cls.return_value \
            .verify_credentials.return_value = True
        payload = {
            "kobo_url": KOBO_URL,
            "kobo_username": "testuser",
            "kobo_password": "oldpass",
        }
        self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        payload["kobo_password"] = "newpass"
        req = self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        self.assertEqual(req.status_code, 200)
        self.assertEqual(
            SystemUser.objects.filter(
                kobo_username="testuser"
            ).count(),
            1,
        )

    @patch("api.v1.v1_users.views.KoboClient")
    def test_invalid_kobo_credentials(self, mock_client_cls):
        mock_client_cls.return_value \
            .verify_credentials.return_value = False
        payload = {
            "kobo_url": KOBO_URL,
            "kobo_username": "baduser",
            "kobo_password": "badpass",
        }
        req = self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        self.assertEqual(req.status_code, 401)
        res = req.json()
        self.assertEqual(
            res,
            {"message": "Invalid KoboToolbox credentials"},
        )

    def test_all_inputs_are_required(self):
        payload = {
            "kobo_url": "",
            "kobo_username": "",
            "kobo_password": "",
        }
        req = self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        self.assertEqual(req.status_code, 400)

    def test_invalid_kobo_url(self):
        payload = {
            "kobo_url": "not-a-url",
            "kobo_username": "user",
            "kobo_password": "pass",
        }
        req = self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        self.assertEqual(req.status_code, 400)
