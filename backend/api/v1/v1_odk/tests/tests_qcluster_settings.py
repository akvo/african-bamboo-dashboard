"""Guard the Django-Q cluster configuration.

The suite never runs a real qcluster worker
(``Q_CLUSTER["sync"]`` is False and nothing consumes
the queue), so the queue configuration itself is
invisible to every other test. These assertions pin
the invariants whose violation caused TC02.
"""

from django.conf import settings
from django.test import SimpleTestCase

from api.v1.v1_jobs.constants import EXPORT_TASK_TIMEOUT


class QClusterSettingsTest(SimpleTestCase):
    def test_retry_exceeds_global_timeout(self):
        """retry is the ORM broker's visibility timeout.

        If it is shorter than the task timeout, a task
        that is still running gets redelivered to
        another worker and re-runs forever -- the
        export never completes and nothing says why.
        """
        self.assertGreater(
            settings.Q_CLUSTER["retry"],
            settings.Q_CLUSTER["timeout"],
        )

    def test_retry_exceeds_export_task_timeout(self):
        """The export overrides timeout per task.

        django_q's own startup guard only compares the
        two globals, so a per-task override can break
        the invariant silently.
        """
        self.assertGreater(
            settings.Q_CLUSTER["retry"],
            EXPORT_TASK_TIMEOUT,
        )

    def test_max_attempts_is_one(self):
        """A completed export must never be re-run."""
        self.assertEqual(
            settings.Q_CLUSTER["max_attempts"], 1
        )

    def test_ack_failures_enabled(self):
        """A raising task must be acked, not requeued.

        sync_kobo_validation_status re-raises so the
        Telegram gate can see a real failure; without
        ack_failures that raise would loop.
        """
        self.assertTrue(
            settings.Q_CLUSTER["ack_failures"]
        )
