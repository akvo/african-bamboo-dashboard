from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.models import SystemUser
from api.v1.v1_users.tests.mixins import ProfileTestHelperMixin


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    WEBDOMAIN="http://example.com",
)
class UpdateProfileTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        self.token = self.get_auth_token()
        self.user = SystemUser.objects.first()

    def test_successfully_update_my_name(self):
        payload = {"name": "Jane Doe"}
        req = self.client.put(
            "/api/v1/users/me",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=(f"Bearer {self.token}"),
        )
        self.assertEqual(req.status_code, 200)
        res = req.json()
        self.assertEqual(
            list(res),
            [
                "id",
                "name",
                "email",
                "email_verified",
                "kobo_url",
                "kobo_username",
            ],
        )
        updated_user = SystemUser.objects.get(pk=self.user.id)
        self.assertEqual(res["name"], updated_user.name)

    def test_successfully_update_my_email(self):
        self.user.email_verified = True
        self.user.save()

        payload = {
            "email": "jane.doe@example.com",
        }
        req = self.client.put(
            "/api/v1/users/me",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=(f"Bearer {self.token}"),
        )
        self.assertEqual(req.status_code, 200)
        res = req.json()

        updated_user = SystemUser.objects.get(pk=self.user.id)
        self.assertEqual(res["email"], updated_user.email)
        self.assertFalse(updated_user.email_verified)
        self.assertNotEqual(
            updated_user.email_verification_code,
            self.user.email_verification_code,
        )
