import typing
from unittest.mock import patch

from django.core.management.color import no_style
from django.db import connection
from django.test.client import Client

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser


class HasTestClientProtocol(typing.Protocol):
    @property
    def client(self) -> Client: ...  # pragma: no cover


class ProfileTestHelperMixin:

    @staticmethod
    def reset_db_sequence(*models):
        """
        Auto fields are no longer incrementing
        after running create with explicit id
        parameter

        see: https://code.djangoproject.com/ticket/11423
        """
        sequence_sql = connection.ops.sequence_reset_sql(
            no_style(), models
        )
        with connection.cursor() as cursor:
            for sql in sequence_sql:
                cursor.execute(sql)

    def get_auth_token(
        self: HasTestClientProtocol,
        kobo_url: str = ("https://kf.kobotoolbox.org"),
        kobo_username: str = "testuser",
        kobo_password: str = "testpass",
    ) -> str:
        """Pre-create an ACTIVE user with the given Kobo
        identity (bypassing the approval gate), then exchange
        credentials for a JWT via the login endpoint. Any
        SystemUser test-side creation must mark the row ACTIVE
        because the live login path now gates non-ACTIVE users
        with a 403 and no token.
        """
        SystemUser.objects.update_or_create(
            kobo_username=kobo_username,
            kobo_url=kobo_url,
            defaults={
                "email": f"{kobo_username}@test.local",
                "name": kobo_username,
                "status": UserStatus.ACTIVE,
                "is_active": True,
            },
        )
        with patch(
            "api.v1.v1_users.views.KoboClient"
        ) as mock_cls:
            mock_cls.return_value \
                .verify_credentials.return_value = True
            payload = {
                "kobo_url": kobo_url,
                "kobo_username": kobo_username,
                "kobo_password": kobo_password,
            }
            response = self.client.post(
                "/api/v1/auth/login",
                payload,
                content_type="application/json",
            )
            data = response.json()
            return data.get("token")
