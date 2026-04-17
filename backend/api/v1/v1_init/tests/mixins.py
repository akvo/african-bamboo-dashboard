from unittest.mock import patch

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser
from utils.encryption import encrypt


class V1InitTestHelperMixin:
    """Shared helpers for v1_init tests.

    Provides an admin SystemUser with Kobo credentials already
    attached and marked ACTIVE so StatusAwareJWTAuthentication
    accepts the login JWT on subsequent authenticated calls.
    """

    KOBO_URL = "https://kf.kobotoolbox.org"
    KOBO_USERNAME = "admin"
    KOBO_PASSWORD = "pass"

    def create_admin_user(self):
        user = SystemUser.objects.create_superuser(
            email="admin@test.local",
            password="Changeme123",
            name="admin",
        )
        user.kobo_url = self.KOBO_URL
        user.kobo_username = self.KOBO_USERNAME
        user.kobo_password = encrypt(self.KOBO_PASSWORD)
        user.status = UserStatus.ACTIVE
        user.is_active = True
        user.save()
        return user

    def login(self):
        """Mock Kobo verification and exchange credentials
        for a JWT via the real login endpoint. Returns auth
        header dict ready to splat into `self.client.*`."""
        with patch(
            "api.v1.v1_users.views.KoboClient"
        ) as mock_cls:
            mock_cls.return_value \
                .verify_credentials.return_value = True
            resp = self.client.post(
                "/api/v1/auth/login",
                {
                    "kobo_url": self.KOBO_URL,
                    "kobo_username": self.KOBO_USERNAME,
                    "kobo_password": self.KOBO_PASSWORD,
                },
                content_type="application/json",
            )
            token = resp.json()["token"]
            return {
                "HTTP_AUTHORIZATION": f"Bearer {token}",
            }
