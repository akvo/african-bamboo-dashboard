from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class ForgotPasswordTestCase(TestCase):
    def setUp(self):
        self.user = SystemUser.objects.create_superuser(
            email="super@akvo.org",
            password="Changeme123",
            name="Super Admin",
        )

    def test_successfully_forgot_password(self):
        payload = {"email": self.user.email}
        req = self.client.post(
            "/api/v1/auth/forgot-password",
            payload,
            content_type="application/json",
        )
        self.assertEqual(req.status_code, 200)

    def test_email_not_found(self):
        payload = {"email": "random@test.com"}
        req = self.client.post(
            "/api/v1/auth/forgot-password",
            payload,
            content_type="application/json",
        )
        self.assertEqual(req.status_code, 200)
        res = req.json()
        self.assertEqual(res, {"message": "OK"})
