from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import AccessToken

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class StatusAwareJWTAuthTest(TestCase):
    """The auth class accepts JWTs for ACTIVE users only.
    Flipping status to SUSPENDED revokes all outstanding JWTs
    on the user's next authenticated request (lightweight
    revocation — no token blocklist needed)."""

    URL = "/api/v1/users/me"

    def _token_for(self, user):
        return str(AccessToken.for_user(user))

    def test_active_user_jwt_is_accepted(self):
        user = SystemUser.objects._create_user(
            email="active@test.local",
            password="x",
            name="A",
            status=UserStatus.ACTIVE,
        )
        auth = {
            "HTTP_AUTHORIZATION": (
                f"Bearer {self._token_for(user)}"
            ),
        }
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 200)

    def test_pending_user_jwt_is_rejected(self):
        user = SystemUser.objects._create_user(
            email="pending@test.local",
            password="x",
            name="P",
            status=UserStatus.PENDING,
        )
        auth = {
            "HTTP_AUTHORIZATION": (
                f"Bearer {self._token_for(user)}"
            ),
        }
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 401)

    def test_deactivated_active_user_jwt_is_revoked(self):
        """Mint a JWT while the user is ACTIVE, then flip them
        to SUSPENDED / is_active=False. The next request with
        the still-unexpired JWT must return 401."""
        user = SystemUser.objects._create_user(
            email="revoked@test.local",
            password="x",
            name="R",
            status=UserStatus.ACTIVE,
        )
        token = self._token_for(user)
        auth = {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 200)

        user.status = UserStatus.SUSPENDED
        user.is_active = False
        user.save()

        resp2 = self.client.get(self.URL, **auth)
        self.assertEqual(resp2.status_code, 401)

    def test_is_active_false_alone_revokes(self):
        """is_active=False with status=ACTIVE is a defensive
        combo (shouldn't occur via normal flow) — the auth
        class should still reject on the is_active check."""
        user = SystemUser.objects._create_user(
            email="halfrevoked@test.local",
            password="x",
            name="H",
            status=UserStatus.ACTIVE,
        )
        token = self._token_for(user)
        user.is_active = False
        user.save(update_fields=["is_active"])
        auth = {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        resp = self.client.get(self.URL, **auth)
        self.assertEqual(resp.status_code, 401)
