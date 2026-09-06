import logging

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from api.v1.v1_users.constants import UserStatus

logger = logging.getLogger(__name__)


class StatusAwareJWTAuthentication(JWTAuthentication):
    """JWT auth that rejects non-active or suspended users.

    Existing JWTs minted before a user was suspended will be
    rejected on the next authenticated request, so admin
    deactivation takes effect without requiring a token
    blocklist.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        if not user.is_active:
            raise AuthenticationFailed(
                "User access has been revoked.",
                code="user_inactive",
            )
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationFailed(
                "User access is not active.",
                code="user_not_active",
            )
        return user, validated_token


class StatusAwareJWTScheme(SimpleJWTScheme):
    """Expose the custom JWT auth to drf-spectacular.

    SimpleJWTScheme has match_subclasses = False, so our subclass
    otherwise resolves to no security scheme and Swagger UI shows
    no Authorize button.
    """

    target_class = StatusAwareJWTAuthentication
