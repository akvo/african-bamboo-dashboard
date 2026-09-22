import logging
from base64 import b64encode

import requests

logger = logging.getLogger(__name__)


class KoboUnauthorizedError(Exception):
    """Raised when KoboToolbox returns 401 Unauthorized.

    Signals that the stored Kobo credentials are
    invalid or expired.
    """

    pass


class KoboClient:
    """Server-side client for KoboToolbox API v2."""

    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: int = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.session = requests.Session()
        credentials = b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers["Authorization"] = f"Basic {credentials}"

    def _check_response(self, resp):
        """Raise KoboUnauthorizedError on 401,
        otherwise delegate to raise_for_status."""
        if resp.status_code == 401:
            raise KoboUnauthorizedError(
                "KoboToolbox credentials are "
                "invalid or expired. Please "
                "log in again with your updated "
                "Kobo password."
            )
        resp.raise_for_status()

    def verify_credentials(self):
        """Validate credentials with a lightweight API call.

        Returns the account's identity as a dict, or False
        when Kobo rejects or cannot answer the request.

        The status check is not optional. /me/ answers a wrong
        password with 401 and a JSON body, so parsing the body
        regardless of status made every rejected login look
        like an accepted one whose email merely happened to be
        missing -- which is precisely the shape that skips the
        invite auto-bind and files a silent PENDING row.
        """
        try:
            url = f"{self.base_url}/me/"
            resp = self.session.get(
                url,
                params={"limit": 0},
                timeout=self.timeout,
            )
            if resp.status_code == 401:
                return False
            resp.raise_for_status()
            detail = resp.json()
        except (requests.RequestException, ValueError):
            return False
        if not isinstance(detail, dict):
            return False
        email = detail.get("email") or None
        if not email:
            # Without an email there is nothing to match an
            # invite against, so the user lands in the manual
            # approval queue. Say so, or the cause is invisible.
            logger.warning(
                "Kobo at %s returned no email for user %r; "
                "invite auto-bind cannot run. Keys returned: %s",
                self.base_url,
                detail.get("username"),
                sorted(detail.keys()),
            )
        return {
            "name": detail.get("extra_details", {}).get("name"),
            "email": email,
        }

    def get_submissions(
        self,
        asset_uid: str,
        limit: int = 300,
        start: int = 0,
    ):
        """Fetch a page of submissions."""
        url = (
            f"{self.base_url}"
            f"/api/v2/assets/{asset_uid}/data.json"
        )
        resp = self.session.get(
            url,
            params={
                "limit": limit,
                "start": start,
                "sort": '{"_id": 1}',
            },
            timeout=self.timeout,
        )
        self._check_response(resp)
        return resp.json()

    def get_submissions_since(
        self,
        asset_uid: str,
        since_iso: str,
        limit: int = 300,
        start: int = 0,
    ):
        """Fetch submissions newer than a timestamp."""
        url = f"{self.base_url}" f"/api/v2/assets/{asset_uid}/data.json"
        query = '{"_submission_time":' f'{{"$gt":"{since_iso}"}}}}'
        resp = self.session.get(
            url,
            params={
                "query": query,
                "limit": limit,
                "start": start,
            },
            timeout=self.timeout,
        )
        self._check_response(resp)
        return resp.json()

    def get_asset_detail(self, asset_uid: str):
        """Fetch asset content (survey fields, choices)."""
        url = f"{self.base_url}" f"/api/v2/assets/{asset_uid}/"
        resp = self.session.get(
            url,
            params={"format": "json"},
            timeout=self.timeout,
        )
        self._check_response(resp)
        return resp.json()["content"]

    def update_validation_statuses(
        self,
        asset_uid: str,
        submission_ids: list,
        validation_status_uid: str,
    ):
        """Bulk-update validation statuses for
        submissions on KoboToolbox."""
        url = (
            f"{self.base_url}"
            f"/api/v2/assets/{asset_uid}"
            "/data/validation_statuses/"
        )
        payload = {
            "payload": {
                "submission_ids": submission_ids,
                "validation_status.uid": (validation_status_uid),
            }
        }
        resp = self.session.patch(
            url,
            json=payload,
            timeout=self.timeout,
        )
        self._check_response(resp)
        return resp.json()

    def update_submission_data(
        self,
        asset_uid: str,
        submission_id,
        data: dict,
    ):
        """Update a single submission's data
        via the bulk PATCH endpoint."""
        url = f"{self.base_url}" f"/api/v2/assets/{asset_uid}" f"/data/bulk/"
        payload = {
            "payload": {
                "submission_ids": [submission_id],
                "data": data,
            }
        }
        resp = self.session.patch(
            url,
            json=payload,
            timeout=self.timeout,
        )
        self._check_response(resp)
        return resp.json()

    def fetch_all_submissions(
        self,
        asset_uid: str,
    ):
        """Paginate through all submissions.

        Always fetches every submission so that
        edits and validation-status changes made
        on Kobo are picked up.  Sorted by _id for
        deterministic offset-based pagination.
        """
        all_results = []
        start = 0
        page_size = 300

        while True:
            data = self.get_submissions(
                asset_uid, page_size, start
            )
            results = data.get("results", [])
            all_results.extend(results)
            start += page_size

            if data.get("next") is None:
                break

        return all_results
