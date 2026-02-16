from unittest.mock import patch

from api.v1.v1_users.models import SystemUser
from utils.encryption import encrypt


class OdkTestHelperMixin:
    """Shared helpers for v1_odk tests."""

    def create_kobo_user(self):
        """Create a SystemUser with Kobo credentials
        for testing."""
        user = SystemUser.objects.create_superuser(
            email="kobouser@kf.kobotoolbox.org.local",
            password="Changeme123",
            name="kobouser",
        )
        user.kobo_url = "https://kf.kobotoolbox.org"
        user.kobo_username = "kobouser"
        user.kobo_password = encrypt("kobopass")
        user.save()
        return user

    def get_auth_header(self):
        """Login via Kobo mock and return auth header
        dict."""
        with patch("api.v1.v1_users.views.KoboClient") as mock_cls:
            mock_cls.return_value.verify_credentials.return_value = True
            resp = self.client.post(
                "/api/v1/auth/login",
                {
                    "kobo_url": ("https://kf.kobotoolbox.org"),
                    "kobo_username": "kobouser",
                    "kobo_password": "kobopass",
                },
                content_type="application/json",
            )
            token = resp.json()["token"]
            return {
                "HTTP_AUTHORIZATION": (f"Bearer {token}"),
            }
