from datetime import timedelta

from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from api.v1.v1_users.models import SystemUser
from api.v1.v1_users.tests.mixins import ProfileTestHelperMixin


@override_settings(
    USE_TZ=False,
    TEST_ENV=True,
    WEBDOMAIN="http://example.com",
)
class ResendVerificationTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        self.token = self.get_auth_token()
        self.user = SystemUser.objects.first()

    def test_successfully_resend_verification(
        self,
    ):
        self.assertIsNotNone(self.user.email)
        req = self.client.post(
            "/api/v1/email/resend-verify",
            {"email": self.user.email},
            content_type="application/json",
            HTTP_AUTHORIZATION=(f"Bearer {self.token}"),
        )
        self.assertEqual(req.status_code, 200)
        res = req.json()
        self.assertEqual(
            res,
            {"message": ("Verification email " "sent successfully")},
        )

    def test_invalid_email_already_verified(
        self,
    ):
        self.user.email_verified = True
        self.user.save()

        req = self.client.post(
            "/api/v1/email/resend-verify",
            {"email": self.user.email},
            content_type="application/json",
            HTTP_AUTHORIZATION=(f"Bearer {self.token}"),
        )
        self.assertEqual(req.status_code, 400)
        res = req.json()
        self.assertEqual(
            res,
            {"message": ("Email is already verified.")},
        )

    def test_invalid_email_not_match(self):
        req = self.client.post(
            "/api/v1/email/resend-verify",
            {"email": "john.doe@example.com"},
            content_type="application/json",
            HTTP_AUTHORIZATION=(f"Bearer {self.token}"),
        )
        self.assertEqual(req.status_code, 400)
        res = req.json()
        self.assertEqual(
            res,
            {"message": ("Email address not found.")},
        )

    def test_resend_verification_less_than_one_hour(
        self,
    ):
        code_expiry = timezone.now() + timedelta(hours=1)
        self.user.email_verification_expiry = code_expiry
        self.user.save()

        req = self.client.post(
            "/api/v1/email/resend-verify",
            {"email": self.user.email},
            content_type="application/json",
            HTTP_AUTHORIZATION=(f"Bearer {self.token}"),
        )
        self.assertEqual(req.status_code, 400)
        res = req.json()
        self.assertEqual(
            res,
            {
                "message": (
                    "Verification email already "
                    "sent. Please wait before "
                    "requesting a new one."
                )
            },
        )
