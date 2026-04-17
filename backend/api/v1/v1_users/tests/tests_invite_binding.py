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
class InviteBindingTest(TestCase):
    """Service-level tests for approval.create_invite and
    approval.bind_pending_login. These bypass the HTTP layer
    so they can exercise the full matrix of binding outcomes
    without mocking Kobo."""

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

    def test_create_invite_creates_pending_row(self):
        user = create_invite(
            email="alice@example.com",
            name="Alice",
            kobo_url=None,
            invited_by=self.admin,
        )
        self.assertEqual(user.status, UserStatus.PENDING)
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.invited_at)
        self.assertEqual(user.status_changed_by, self.admin)
        self.assertIsNone(user.kobo_username)

    def test_create_invite_sends_invitation_email(self):
        create_invite(
            email="alice@example.com",
            name="Alice",
            kobo_url=None,
            invited_by=self.admin,
        )
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["alice@example.com"])
        self.assertIn("Admin", msg.alternatives[0][0])

    def test_create_invite_duplicate_email_raises(self):
        create_invite(
            email="alice@example.com",
            name="Alice",
            kobo_url=None,
            invited_by=self.admin,
        )
        with self.assertRaises(ValueError):
            create_invite(
                email="alice@example.com",
                name="Alice again",
                kobo_url=None,
                invited_by=self.admin,
            )

    def test_bind_email_match_flips_to_active(self):
        create_invite(
            email="alice@example.com",
            name="Alice",
            kobo_url=None,
            invited_by=self.admin,
        )
        mail.outbox = []
        user, outcome = bind_pending_login(
            email_from_kobo="alice@example.com",
            kobo_username="alice",
            kobo_url=KOBO_URL,
            encrypted_password="encpw",
            name_from_kobo="Alice Kobo",
            email_was_synthesized=False,
        )
        self.assertEqual(outcome, BindOutcome.BOUND)
        self.assertEqual(user.status, UserStatus.ACTIVE)
        self.assertEqual(user.kobo_username, "alice")
        self.assertEqual(user.kobo_url, KOBO_URL)
        # Approved email enqueued (sync mode => inline)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "approved", mail.outbox[0].subject.lower()
        )

    def test_bind_case_insensitive_email_match(self):
        create_invite(
            email="alice@example.com",
            name="Alice",
            kobo_url=None,
            invited_by=self.admin,
        )
        user, outcome = bind_pending_login(
            email_from_kobo="Alice@Example.COM",
            kobo_username="alice",
            kobo_url=KOBO_URL,
            encrypted_password="encpw",
            name_from_kobo=None,
            email_was_synthesized=False,
        )
        self.assertEqual(outcome, BindOutcome.BOUND)
        self.assertEqual(user.status, UserStatus.ACTIVE)

    def test_bind_synthesized_email_does_not_auto_bind(self):
        """When Kobo returns no real email, the fallback
        synthesized address (e.g. `user@kf.kobotoolbox.org`)
        must not be auto-matched against any invite by email,
        because the synthesized form is deterministic and
        could trivially collide. A warning is logged and a
        silent PENDING row is created with the synthesized
        address — separate from the invite row."""
        create_invite(
            email="alice@example.com",
            name="Alice",
            kobo_url=None,
            invited_by=self.admin,
        )
        mail.outbox = []
        synth_email = "alice@kf.kobotoolbox.org"
        with self.assertLogs(
            "api.v1.v1_users.services.approval",
            level="WARNING",
        ) as log:
            user, outcome = bind_pending_login(
                email_from_kobo=synth_email,
                kobo_username="alice",
                kobo_url=KOBO_URL,
                encrypted_password="encpw",
                name_from_kobo=None,
                email_was_synthesized=True,
            )
        self.assertEqual(
            outcome, BindOutcome.SILENT_PENDING
        )
        self.assertEqual(user.status, UserStatus.PENDING)
        self.assertEqual(user.email, synth_email)
        # The invite row (alice@example.com) is untouched.
        invite = SystemUser.objects.get(
            email="alice@example.com"
        )
        self.assertIsNone(invite.kobo_username)
        self.assertEqual(invite.status, UserStatus.PENDING)
        self.assertTrue(
            any(
                "did not return a real email" in m
                for m in log.output
            )
        )
        # No approved email sent
        self.assertEqual(len(mail.outbox), 0)

    def test_bind_no_invite_creates_silent_pending(self):
        user, outcome = bind_pending_login(
            email_from_kobo="nobody@example.com",
            kobo_username="nobody",
            kobo_url=KOBO_URL,
            encrypted_password="encpw",
            name_from_kobo="Nobody",
            email_was_synthesized=False,
        )
        self.assertEqual(
            outcome, BindOutcome.SILENT_PENDING
        )
        self.assertEqual(user.status, UserStatus.PENDING)
        self.assertEqual(user.kobo_username, "nobody")

    def test_bind_existing_active_returns_already_active(
        self,
    ):
        SystemUser.objects.create(
            email="returning@kf.kobotoolbox.org",
            name="returning",
            kobo_url=KOBO_URL,
            kobo_username="returning",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        user, outcome = bind_pending_login(
            email_from_kobo="returning@kf.kobotoolbox.org",
            kobo_username="returning",
            kobo_url=KOBO_URL,
            encrypted_password="newpw",
            name_from_kobo="Returning User",
            email_was_synthesized=False,
        )
        self.assertEqual(
            outcome, BindOutcome.ALREADY_ACTIVE
        )
        self.assertEqual(user.kobo_password, "newpw")

    def test_bind_existing_pending_returns_silent_pending(
        self,
    ):
        SystemUser.objects.create(
            email="bob@kf.kobotoolbox.org",
            name="bob",
            kobo_url=KOBO_URL,
            kobo_username="bob",
            status=UserStatus.PENDING,
            is_active=False,
        )
        user, outcome = bind_pending_login(
            email_from_kobo="bob@kf.kobotoolbox.org",
            kobo_username="bob",
            kobo_url=KOBO_URL,
            encrypted_password="newpw",
            name_from_kobo=None,
            email_was_synthesized=False,
        )
        self.assertEqual(
            outcome, BindOutcome.SILENT_PENDING
        )
        self.assertEqual(user.status, UserStatus.PENDING)

    def test_bind_two_kobo_users_sharing_email(self):
        """Regression: two distinct Kobo identities (different
        kobo_username) can legally share an email address on
        KoboToolbox. The first arriver stores the real email;
        the second must still get a row (synthesized email)
        instead of crashing on the unique constraint."""
        shared_email = "shared@africa-bamboo.com"

        u1, o1 = bind_pending_login(
            email_from_kobo=shared_email,
            kobo_username="ab_enumerator",
            kobo_url=KOBO_URL,
            encrypted_password="pw1",
            name_from_kobo="Alice",
            email_was_synthesized=False,
        )
        self.assertEqual(o1, BindOutcome.SILENT_PENDING)
        self.assertEqual(u1.email, shared_email)

        with self.assertLogs(
            "api.v1.v1_users.services.approval",
            level="WARNING",
        ) as log:
            u2, o2 = bind_pending_login(
                email_from_kobo=shared_email,
                kobo_username="ab_admin",
                kobo_url=KOBO_URL,
                encrypted_password="pw2",
                name_from_kobo="Alice",
                email_was_synthesized=False,
            )
        self.assertEqual(o2, BindOutcome.SILENT_PENDING)
        # Second user keeps its own row with a synthesized
        # email so the unique constraint holds.
        self.assertNotEqual(u2.pk, u1.pk)
        self.assertNotEqual(u2.email, shared_email)
        self.assertEqual(u2.kobo_username, "ab_admin")
        self.assertEqual(u2.status, UserStatus.PENDING)
        self.assertTrue(
            any(
                "Email collision on silent-pending" in m
                for m in log.output
            )
        )
