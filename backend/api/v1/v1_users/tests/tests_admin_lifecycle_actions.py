from django.contrib.admin.sites import site
from django.contrib.messages.storage.cookie import (
    CookieStorage,
)
from django.core import mail
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings

from django_q.conf import Conf

from api.v1.v1_users.admin import InviteUserForm, SystemUserAdmin
from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser


def _request_with_messages(rf, user):
    """ModelAdmin action handlers expect request.user and a
    working messages backend. Cookie storage sidesteps the
    session middleware requirement for in-unit-test calls."""
    req = rf.post("/admin/fake/")
    req.user = user
    req._messages = CookieStorage(req)
    return req


@override_settings(USE_TZ=False, TEST_ENV=True)
class AdminLifecycleActionsTest(TestCase):
    """The four admin bulk actions (approve / reject /
    deactivate / reactivate) each fire only from their allowed
    source state. Off-state rows are skipped with a warning.
    Each action enqueues the matching transactional email."""

    _original_sync = None

    def setUp(self):
        self._original_sync = Conf.SYNC
        Conf.SYNC = True
        self.admin_user = (
            SystemUser.objects._create_user(
                email="root@test.local",
                password="x",
                name="Root",
                status=UserStatus.ACTIVE,
                is_superuser=True,
            )
        )
        self.modeladmin = SystemUserAdmin(
            SystemUser, site
        )
        self.rf = RequestFactory()
        mail.outbox = []

    def tearDown(self):
        Conf.SYNC = self._original_sync

    def _make(self, status):
        return SystemUser.objects._create_user(
            email=(
                f"u{status}-"
                f"{SystemUser.objects.count()}@t.local"
            ),
            password="x",
            name="u",
            status=status,
        )

    # --- approve (PENDING -> ACTIVE) ---

    def test_approve_flips_pending_to_active(self):
        u = self._make(UserStatus.PENDING)
        req = _request_with_messages(
            self.rf, self.admin_user
        )
        self.modeladmin.action_approve(
            req, SystemUser.objects.filter(pk=u.pk)
        )
        u.refresh_from_db()
        self.assertEqual(u.status, UserStatus.ACTIVE)
        self.assertTrue(u.is_active)
        self.assertEqual(
            u.status_changed_by, self.admin_user
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "approved", mail.outbox[0].subject.lower()
        )

    def test_approve_skips_non_pending(self):
        active = self._make(UserStatus.ACTIVE)
        req = _request_with_messages(
            self.rf, self.admin_user
        )
        self.modeladmin.action_approve(
            req, SystemUser.objects.filter(pk=active.pk)
        )
        active.refresh_from_db()
        self.assertEqual(
            active.status, UserStatus.ACTIVE
        )
        self.assertEqual(len(mail.outbox), 0)

    # --- reject (PENDING -> SUSPENDED) ---

    def test_reject_flips_pending_to_suspended(self):
        u = self._make(UserStatus.PENDING)
        req = _request_with_messages(
            self.rf, self.admin_user
        )
        self.modeladmin.action_reject(
            req, SystemUser.objects.filter(pk=u.pk)
        )
        u.refresh_from_db()
        self.assertEqual(u.status, UserStatus.SUSPENDED)
        self.assertFalse(u.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "denied", mail.outbox[0].subject.lower()
        )

    # --- deactivate (ACTIVE -> SUSPENDED) ---

    def test_deactivate_flips_active_to_suspended(self):
        u = self._make(UserStatus.ACTIVE)
        req = _request_with_messages(
            self.rf, self.admin_user
        )
        self.modeladmin.action_deactivate(
            req, SystemUser.objects.filter(pk=u.pk)
        )
        u.refresh_from_db()
        self.assertEqual(u.status, UserStatus.SUSPENDED)
        self.assertFalse(u.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "revoked", mail.outbox[0].subject.lower()
        )

    def test_deactivate_skips_pending(self):
        pending = self._make(UserStatus.PENDING)
        req = _request_with_messages(
            self.rf, self.admin_user
        )
        self.modeladmin.action_deactivate(
            req, SystemUser.objects.filter(pk=pending.pk)
        )
        pending.refresh_from_db()
        self.assertEqual(
            pending.status, UserStatus.PENDING
        )
        self.assertEqual(len(mail.outbox), 0)

    # --- reactivate (SUSPENDED -> ACTIVE) ---

    def test_reactivate_flips_suspended_to_active(self):
        u = self._make(UserStatus.SUSPENDED)
        req = _request_with_messages(
            self.rf, self.admin_user
        )
        self.modeladmin.action_reactivate(
            req, SystemUser.objects.filter(pk=u.pk)
        )
        u.refresh_from_db()
        self.assertEqual(u.status, UserStatus.ACTIVE)
        self.assertTrue(u.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "restored", mail.outbox[0].subject.lower()
        )

    def test_reactivate_skips_active(self):
        active = self._make(UserStatus.ACTIVE)
        req = _request_with_messages(
            self.rf, self.admin_user
        )
        self.modeladmin.action_reactivate(
            req, SystemUser.objects.filter(pk=active.pk)
        )
        active.refresh_from_db()
        self.assertEqual(
            active.status, UserStatus.ACTIVE
        )
        self.assertEqual(len(mail.outbox), 0)

    # --- bulk mixed queryset ---

    def test_approve_mixed_queryset_only_touches_pending(
        self,
    ):
        p1 = self._make(UserStatus.PENDING)
        p2 = self._make(UserStatus.PENDING)
        active = self._make(UserStatus.ACTIVE)
        suspended = self._make(UserStatus.SUSPENDED)

        req = _request_with_messages(
            self.rf, self.admin_user
        )
        self.modeladmin.action_approve(
            req,
            SystemUser.objects.filter(
                pk__in=[
                    p1.pk, p2.pk, active.pk, suspended.pk
                ]
            ),
        )
        p1.refresh_from_db()
        p2.refresh_from_db()
        active.refresh_from_db()
        suspended.refresh_from_db()
        self.assertEqual(p1.status, UserStatus.ACTIVE)
        self.assertEqual(p2.status, UserStatus.ACTIVE)
        self.assertEqual(
            active.status, UserStatus.ACTIVE
        )
        self.assertEqual(
            suspended.status, UserStatus.SUSPENDED
        )
        # Two emails sent, one per pending-flipped user
        self.assertEqual(len(mail.outbox), 2)


@override_settings(USE_TZ=False, TEST_ENV=True)
class AdminPermissionsTest(TestCase):
    """Admin is visible only to superusers."""

    def setUp(self):
        self.modeladmin = SystemUserAdmin(
            SystemUser, site
        )
        self.rf = RequestFactory()

    def test_non_superuser_has_no_module_permission(self):
        ordinary = SystemUser.objects._create_user(
            email="joe@test.local",
            password="x",
            name="Joe",
            status=UserStatus.ACTIVE,
            is_superuser=False,
        )
        req = self.rf.get("/admin/")
        req.user = ordinary
        self.assertFalse(
            self.modeladmin.has_module_permission(req)
        )

    def test_superuser_has_module_permission(self):
        admin_user = SystemUser.objects._create_user(
            email="root@test.local",
            password="x",
            name="Root",
            status=UserStatus.ACTIVE,
            is_superuser=True,
        )
        req = self.rf.get("/admin/")
        req.user = admin_user
        self.assertTrue(
            self.modeladmin.has_module_permission(req)
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class InviteUserFormTest(TestCase):
    """Basic form validation for the admin Invite form."""

    def test_email_is_required(self):
        form = InviteUserForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_valid_form_accepts_email_only(self):
        form = InviteUserForm(
            data={"email": "alice@example.com"}
        )
        self.assertTrue(form.is_valid())

    def test_invalid_email_rejected(self):
        form = InviteUserForm(
            data={"email": "not-an-email"}
        )
        self.assertFalse(form.is_valid())
