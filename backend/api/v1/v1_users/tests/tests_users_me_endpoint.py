from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_users.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class MyProfileTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        self.token = self.get_auth_token()

    def test_successfully_get_my_account(self):
        req = self.client.get(
            "/api/v1/users/me",
            content_type="application/json",
            HTTP_AUTHORIZATION=(f"Bearer {self.token}"),
        )
        self.assertTrue(req.status_code, 200)
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

    def test_my_deleted_account(self):
        from api.v1.v1_users.models import SystemUser

        user = SystemUser.objects.first()
        user.soft_delete()
        req = self.client.get(
            "/api/v1/users/me",
            content_type="application/json",
            HTTP_AUTHORIZATION=(f"Bearer {self.token}"),
        )
        self.assertTrue(req.status_code, 401)
        res = req.json()
        self.assertEqual(
            res,
            {
                "detail": "User not found",
                "code": "user_not_found",
            },
        )
