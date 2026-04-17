from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings

from django_q.conf import Conf

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser
from utils.email_helper import (
    EmailTypes,
    queue_email,
    send_email_by_user_id,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class EmailNotificationsTest(TestCase):
    """Every EmailTypes value routes through queue_email, lands
    in mail.outbox (locmem backend), and renders the shared
    email/main.html template.

    Conf.SYNC is flipped on per-test so async_task runs inline
    and mail.outbox assertions are immediate. The TEST_ENV env
    var may or may not be set at manage.py test launch, so we
    can't rely on Q_CLUSTER["sync"] being True from settings.
    """

    _original_sync = None

    def setUp(self):
        self._original_sync = Conf.SYNC
        Conf.SYNC = True
        self.user = SystemUser.objects._create_user(
            email="alice@example.com",
            password="x",
            name="Alice",
            status=UserStatus.ACTIVE,
            kobo_username="ab_admin",
            kobo_url="https://kf.kobotoolbox.org",
        )
        mail.outbox = []

    def tearDown(self):
        Conf.SYNC = self._original_sync

    def test_sync_send_lands_in_outbox(self):
        """Sanity: calling send_email_by_user_id directly (the
        task entry-point) puts a message in the outbox. This
        isolates whether async_task's sync mode is the
        bottleneck."""
        send_email_by_user_id(
            self.user.id, EmailTypes.account_approved
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_invitation_email_rendered_and_sent(self):
        queue_email(
            self.user,
            EmailTypes.account_invited,
            extra_context={"inviter_name": "Bob"},
        )
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("invited", msg.subject.lower())
        self.assertEqual(msg.to, ["alice@example.com"])
        html = msg.alternatives[0][0]
        self.assertIn("Bob", html)
        # CTA button is rendered for invited
        self.assertIn("/login", html)

    def test_approved_email_rendered_and_sent(self):
        queue_email(self.user, EmailTypes.account_approved)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn(
            "approved", msg.subject.lower()
        )
        self.assertIn("/login", msg.alternatives[0][0])

    def test_rejected_email_has_no_cta(self):
        queue_email(self.user, EmailTypes.account_rejected)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("denied", msg.subject.lower())
        # No CTA button: cta_url is None in email_context
        self.assertNotIn(
            "/login", msg.alternatives[0][0]
        )

    def test_deactivated_email_has_no_cta(self):
        queue_email(
            self.user, EmailTypes.account_deactivated
        )
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("revoked", msg.subject.lower())
        self.assertNotIn(
            "/login", msg.alternatives[0][0]
        )

    def test_reactivated_email_has_cta(self):
        queue_email(
            self.user, EmailTypes.account_reactivated
        )
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("restored", msg.subject.lower())
        self.assertIn("/login", msg.alternatives[0][0])

    def test_emails_name_the_kobo_account(self):
        """Users with multiple Kobo accounts sharing an email
        must see which account was acted on. The body should
        include the kobo_username for all state-change
        emails."""
        for email_type in (
            EmailTypes.account_approved,
            EmailTypes.account_rejected,
            EmailTypes.account_deactivated,
            EmailTypes.account_reactivated,
        ):
            mail.outbox = []
            queue_email(self.user, email_type)
            body = mail.outbox[0].alternatives[0][0]
            self.assertIn(
                "ab_admin",
                body,
                f"kobo_username missing for {email_type}",
            )

    def test_emails_omit_account_label_if_no_kobo_username(
        self,
    ):
        """Invite-only rows (PENDING, kobo_username still
        null) don't have a Kobo account to name. The email
        body should not include an empty 'for account ``'
        fragment."""
        self.user.kobo_username = None
        self.user.save()
        queue_email(self.user, EmailTypes.account_approved)
        body = mail.outbox[0].alternatives[0][0]
        self.assertNotIn("for the KoboToolbox account", body)
        self.assertNotIn("``", body)

    def test_recipient_name_falls_back_to_email(self):
        """If user.name is blank, the template greets them by
        email address instead of an empty Hello."""
        self.user.name = ""
        self.user.save()
        queue_email(self.user, EmailTypes.account_approved)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "alice@example.com", mail.outbox[0].alternatives[0][0]
        )

    def test_deleted_user_between_enqueue_and_run(self):
        """send_email_by_user_id gracefully skips if the user
        row is missing — no email sent, warning logged, no
        exception bubbles."""
        ghost_id = 999999
        with self.assertLogs(
            "utils.email_helper", level="WARNING"
        ) as log:
            send_email_by_user_id(
                ghost_id, EmailTypes.account_approved
            )
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(
            any("no longer exists" in m for m in log.output)
        )

    @patch(
        "utils.email_helper.EmailMultiAlternatives.send",
        side_effect=RuntimeError("SMTP down"),
    )
    def test_mailjet_failure_is_swallowed(self, _mock_send):
        """Mailjet outage must not break the lifecycle action
        that queued the email. send_email catches the exception
        and logs a warning; caller keeps going."""
        with self.assertLogs(
            "utils.email_helper", level="WARNING"
        ) as log:
            queue_email(
                self.user, EmailTypes.account_approved
            )
        # mail.outbox does not record the send because
        # EmailMultiAlternatives.send itself raised.
        self.assertTrue(
            any(
                "Failed to send email" in m
                for m in log.output
            )
        )
