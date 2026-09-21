from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings

from django_q.conf import Conf

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser
from api.v1.v1_users.services.approval import (
    BindOutcome,
    bind_pending_login,
    create_invite,
)

KOBO_URL = "https://kf.kobotoolbox.org"


@override_settings(USE_TZ=False, TEST_ENV=True)
class InviteDeletedUserTest(TestCase):
    """Re-admitting a soft-deleted user.

    SystemUser.objects hides soft-deleted rows, but the
    UNIQUE constraints on `email` and on the kobo identity
    do not. Every lookup that decides whether to create a
    row must therefore see deleted rows too, or the create
    raises IntegrityError.
    """

    _original_sync = None

    def setUp(self):
        self._original_sync = Conf.SYNC
        Conf.SYNC = True
        self.admin = SystemUser.objects._create_user(
            email="admin@test.local",
            password="x",
            name="Admin",
            status=UserStatus.ACTIVE,
        )
        mail.outbox = []

    def tearDown(self):
        Conf.SYNC = self._original_sync

    def _deleted_user(self, **overrides):
        fields = {
            "email": "iwan@akvo.org",
            "name": "Iwan",
            "status": UserStatus.ACTIVE,
            "is_active": True,
        }
        fields.update(overrides)
        user = SystemUser.objects.create(**fields)
        user.soft_delete()
        return user

    def test_invite_restores_soft_deleted_user(self):
        deleted = self._deleted_user()

        user = create_invite(
            email="iwan@akvo.org",
            name="Iwan",
            kobo_url=None,
            invited_by=self.admin,
        )

        self.assertEqual(user.pk, deleted.pk)
        self.assertIsNone(user.deleted_at)
        self.assertEqual(user.status, UserStatus.PENDING)
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.invited_at)
        self.assertEqual(user.status_changed_by, self.admin)
        self.assertEqual(
            SystemUser.objects_with_deleted.filter(
                email="iwan@akvo.org"
            ).count(),
            1,
        )

    def test_invite_restore_clears_stale_kobo_binding(self):
        """A restored row must be bindable again: the login
        flow only auto-approves a PENDING invite whose
        kobo_username is still NULL."""
        self._deleted_user(
            kobo_username="iwan",
            kobo_url=KOBO_URL,
            kobo_password="old-secret",
        )

        user = create_invite(
            email="iwan@akvo.org",
            name="Iwan",
            kobo_url=KOBO_URL,
            invited_by=self.admin,
        )

        self.assertIsNone(user.kobo_username)
        self.assertIsNone(user.kobo_password)

    def test_invite_restore_sends_invitation_email(self):
        self._deleted_user()

        create_invite(
            email="iwan@akvo.org",
            name="Iwan",
            kobo_url=None,
            invited_by=self.admin,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("invited", mail.outbox[0].subject.lower())

    def test_invite_still_rejects_live_duplicate(self):
        SystemUser.objects.create(
            email="live@akvo.org", name="Live"
        )
        with self.assertRaises(ValueError):
            create_invite(
                email="live@akvo.org",
                name="Live",
                kobo_url=None,
                invited_by=self.admin,
            )

    def test_login_of_soft_deleted_kobo_identity(self):
        """Kobo login by a soft-deleted identity must not
        explode on the kobo-identity UNIQUE constraint."""
        deleted = self._deleted_user(
            kobo_username="iwan",
            kobo_url=KOBO_URL,
            kobo_password="old-secret",
        )

        user, outcome = bind_pending_login(
            email_from_kobo="iwan@akvo.org",
            kobo_username="iwan",
            kobo_url=KOBO_URL,
            encrypted_password="new-secret",
            name_from_kobo="Iwan",
            email_was_synthesized=False,
        )

        self.assertEqual(user.pk, deleted.pk)
        self.assertEqual(outcome, BindOutcome.SILENT_PENDING)
        self.assertIsNotNone(user.deleted_at)
        # Untouched: deletion is not undone by logging in.
        self.assertEqual(user.kobo_password, "old-secret")
        self.assertEqual(
            SystemUser.objects_with_deleted.filter(
                kobo_username="iwan", kobo_url=KOBO_URL
            ).count(),
            1,
        )

    def test_login_binds_restored_invite(self):
        """End to end: delete, re-invite, log back in."""
        deleted = self._deleted_user(
            kobo_username="iwan",
            kobo_url=KOBO_URL,
            kobo_password="old-secret",
        )
        create_invite(
            email="iwan@akvo.org",
            name="Iwan",
            kobo_url=KOBO_URL,
            invited_by=self.admin,
        )

        user, outcome = bind_pending_login(
            email_from_kobo="iwan@akvo.org",
            kobo_username="iwan",
            kobo_url=KOBO_URL,
            encrypted_password="new-secret",
            name_from_kobo="Iwan",
            email_was_synthesized=False,
        )

        self.assertEqual(user.pk, deleted.pk)
        self.assertEqual(outcome, BindOutcome.BOUND)
        self.assertEqual(user.status, UserStatus.ACTIVE)
        self.assertTrue(user.is_active)
        self.assertEqual(user.kobo_username, "iwan")


@override_settings(USE_TZ=False, TEST_ENV=True)
class LoginDeletedUserTest(TestCase):
    """HTTP-level guard: a soft-deleted user must not receive
    a token, even when the row still reads status=ACTIVE."""

    @patch("api.v1.v1_users.views.KoboClient")
    def test_login_of_deleted_user_is_forbidden(
        self, mock_client_cls
    ):
        user = SystemUser.objects.create(
            email="iwan@akvo.org",
            name="Iwan",
            kobo_url=KOBO_URL,
            kobo_username="iwan",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        user.soft_delete()
        mock_client_cls.return_value \
            .verify_credentials.return_value = {
                "email": "iwan@akvo.org",
                "name": "Iwan",
            }

        res = self.client.post(
            "/api/v1/auth/login",
            {
                "kobo_url": KOBO_URL,
                "kobo_username": "iwan",
                "kobo_password": "secret",
            },
            content_type="application/json",
        )

        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["status"], "suspended")
        self.assertNotIn("token", res.json())
