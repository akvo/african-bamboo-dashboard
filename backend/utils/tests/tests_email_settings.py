"""Pin the SMTP mail settings.

The interesting part of this wiring is not that it reads
environment variables, but that two of them are booleans Django
refuses to accept together, and that the obvious way to parse a
boolean out of the environment is silently wrong.
"""

import importlib
import os
from unittest.mock import patch

from django.test import SimpleTestCase

from african_bamboo_dashboard import settings as app_settings


def reload_settings(**overrides):
    """Re-execute settings.py against a modified environment.

    Only the settings *module* namespace is affected:
    django.conf.settings copied its values at startup and does
    not read the module again, so the running test's own
    configuration -- database, locmem mail backend, everything
    -- is untouched by this.

    Every EMAIL_* variable inherited from the real environment
    is dropped first, so a developer with credentials exported
    in their shell gets the same result as CI.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("EMAIL_")
    }
    env.update(overrides)
    with patch.dict(os.environ, env, clear=True):
        return importlib.reload(app_settings)


class EnvFlagTest(SimpleTestCase):
    """The parser behind EMAIL_USE_SSL and EMAIL_USE_TLS."""

    def test_falsey_strings_are_false(self):
        # bool("false") is True, which is the whole reason this
        # helper exists rather than an inline expression.
        for raw in ("false", "False", "0", "no", "off"):
            with patch.dict(os.environ, {"FLAG": raw}):
                self.assertFalse(
                    app_settings.env_flag("FLAG", default=True),
                    f"{raw!r} should not enable the flag",
                )

    def test_truthy_strings_are_true(self):
        for raw in ("true", "TRUE", "  True  ", "1", "yes"):
            with patch.dict(os.environ, {"FLAG": raw}):
                self.assertTrue(
                    app_settings.env_flag("FLAG", default=False),
                    f"{raw!r} should enable the flag",
                )

    def test_unset_and_empty_fall_back_to_default(self):
        with patch.dict(os.environ, {"FLAG": ""}):
            self.assertTrue(
                app_settings.env_flag("FLAG", default=True)
            )
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(
                app_settings.env_flag("FLAG", default=True)
            )


class EmailSettingsTest(SimpleTestCase):
    def tearDown(self):
        # Put the module back the way the rest of the suite
        # found it.
        reload_settings()

    def test_defaults_target_a_starttls_relay(self):
        """A deployment supplying only host and credentials
        should land on the common correct configuration."""
        settings = reload_settings()
        self.assertEqual(
            settings.EMAIL_BACKEND,
            "django.core.mail.backends.smtp.EmailBackend",
        )
        self.assertEqual(settings.EMAIL_PORT, 587)
        self.assertTrue(settings.EMAIL_USE_TLS)
        self.assertFalse(settings.EMAIL_USE_SSL)
        # Django's own default is None, i.e. no bound at all.
        self.assertEqual(settings.EMAIL_TIMEOUT, 10)

    def test_ssl_alone_switches_starttls_off(self):
        """Django raises if both flags are set, so moving to
        port 465 must not require remembering to disable the
        other one."""
        settings = reload_settings(
            EMAIL_USE_SSL="true", EMAIL_PORT="465"
        )
        self.assertTrue(settings.EMAIL_USE_SSL)
        self.assertFalse(settings.EMAIL_USE_TLS)
        self.assertEqual(settings.EMAIL_PORT, 465)

    def test_tls_can_be_turned_off_explicitly(self):
        """A relay that speaks neither -- a local catch-all mail
        trap, say -- is reachable without editing settings."""
        settings = reload_settings(EMAIL_USE_TLS="false")
        self.assertFalse(settings.EMAIL_USE_TLS)
        self.assertFalse(settings.EMAIL_USE_SSL)

    def test_credentials_come_from_the_environment(self):
        settings = reload_settings(
            EMAIL_HOST="smtp.example.org",
            EMAIL_HOST_USER="mailer@example.org",
            EMAIL_HOST_PASSWORD="hunter2",
            EMAIL_FROM="noreply@example.org",
        )
        self.assertEqual(settings.EMAIL_HOST, "smtp.example.org")
        self.assertEqual(
            settings.EMAIL_HOST_USER, "mailer@example.org"
        )
        self.assertEqual(
            settings.EMAIL_HOST_PASSWORD, "hunter2"
        )
        self.assertEqual(
            settings.EMAIL_FROM, "noreply@example.org"
        )

    def test_empty_host_leaves_sending_unconfigured(self):
        """Local development sets nothing; send_email logs the
        failure rather than mailing a real recipient."""
        settings = reload_settings(EMAIL_HOST="")
        self.assertEqual(settings.EMAIL_HOST, "")
