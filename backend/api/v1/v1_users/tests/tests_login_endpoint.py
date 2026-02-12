from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class LoginTestCase(TestCase):

    @patch("api.v1.v1_users.views.KoboClient")
    def test_successfully_logged_in(self, mock_client_cls):
        mock_client_cls.return_value.verify_credentials.return_value = True
        payload = {
            "kobo_url": ("https://kf.kobotoolbox.org"),
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
                "email_verified",
                "kobo_url",
                "kobo_username",
            ],
        )
        self.assertEqual(res["user"]["kobo_username"], "testuser")
        self.assertEqual(
            res["user"]["kobo_url"],
            "https://kf.kobotoolbox.org",
        )

    @patch("api.v1.v1_users.views.KoboClient")
    def test_creates_system_user(self, mock_client_cls):
        mock_client_cls.return_value.verify_credentials.return_value = True
        payload = {
            "kobo_url": ("https://kf.kobotoolbox.org"),
            "kobo_username": "newuser",
            "kobo_password": "newpass",
        }
        self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        self.assertTrue(
            SystemUser.objects.filter(kobo_username="newuser").exists()
        )

    @patch("api.v1.v1_users.views.KoboClient")
    def test_updates_existing_user_credentials(self, mock_client_cls):
        mock_client_cls.return_value.verify_credentials.return_value = True
        payload = {
            "kobo_url": ("https://kf.kobotoolbox.org"),
            "kobo_username": "testuser",
            "kobo_password": "oldpass",
        }
        self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        # Login again with new password
        payload["kobo_password"] = "newpass"
        req = self.client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
        )
        self.assertEqual(req.status_code, 200)
        # Should still be one user
        self.assertEqual(
            SystemUser.objects.filter(kobo_username="testuser").count(),
            1,
        )

    @patch("api.v1.v1_users.views.KoboClient")
    def test_invalid_kobo_credentials(self, mock_client_cls):
        mock_client_cls.return_value.verify_credentials.return_value = False
        payload = {
            "kobo_url": ("https://kf.kobotoolbox.org"),
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
            {"message": ("Invalid KoboToolbox credentials")},
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
