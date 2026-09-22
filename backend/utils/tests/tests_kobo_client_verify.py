from unittest.mock import patch

import requests
from django.test import TestCase

from utils.kobo_client import KoboClient

KOBO_URL = "https://eu.kobotoolbox.org"


def _response(status_code, payload):
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = payload
    resp.headers["Content-Type"] = "application/json"
    return resp


class VerifyCredentialsTest(TestCase):
    """KoboClient.verify_credentials must distinguish a
    rejected login from an accepted one.

    /me/ returns a JSON body on 401 as readily as on 200, so
    a check that only parses the body accepts every password.
    """

    def _verify(self, resp):
        client = KoboClient(KOBO_URL, "ifirmawan", "pw")
        with patch.object(
            client.session, "get", return_value=resp
        ):
            return client.verify_credentials()

    def test_unauthorized_is_rejected(self):
        resp = _response(
            401,
            b'{"detail": "Invalid username/password."}',
        )
        self.assertIs(self._verify(resp), False)

    def test_server_error_is_rejected(self):
        resp = _response(500, b'{"detail": "boom"}')
        self.assertIs(self._verify(resp), False)

    def test_non_json_body_is_rejected(self):
        resp = _response(200, b"<html>login page</html>")
        self.assertIs(self._verify(resp), False)

    def test_non_dict_json_is_rejected(self):
        resp = _response(200, b'["not", "a", "user"]')
        self.assertIs(self._verify(resp), False)

    def test_valid_login_returns_identity(self):
        resp = _response(
            200,
            b'{"username": "ifirmawan", '
            b'"email": "iwan@akvo.org", '
            b'"extra_details": {"name": "Iwan"}}',
        )
        self.assertEqual(
            self._verify(resp),
            {"name": "Iwan", "email": "iwan@akvo.org"},
        )

    def test_missing_email_returns_none_and_warns(self):
        resp = _response(
            200,
            b'{"username": "ifirmawan", '
            b'"extra_details": {"name": "Iwan"}}',
        )
        with self.assertLogs(
            "utils.kobo_client", level="WARNING"
        ) as captured:
            result = self._verify(resp)
        self.assertIsNone(result["email"])
        self.assertIn(
            "returned no email", captured.output[0]
        )

    def test_blank_email_is_normalized_to_none(self):
        resp = _response(
            200,
            b'{"username": "ifirmawan", "email": "", '
            b'"extra_details": {}}',
        )
        with self.assertLogs(
            "utils.kobo_client", level="WARNING"
        ):
            result = self._verify(resp)
        self.assertIsNone(result["email"])

    def test_request_exception_is_rejected(self):
        client = KoboClient(KOBO_URL, "ifirmawan", "pw")
        with patch.object(
            client.session,
            "get",
            side_effect=requests.ConnectionError("down"),
        ):
            self.assertIs(client.verify_credentials(), False)
