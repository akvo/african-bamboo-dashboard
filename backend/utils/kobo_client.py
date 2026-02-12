from base64 import b64encode

import requests


class KoboClient:
    """Server-side client for KoboToolbox API v2."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        credentials = b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers["Authorization"] = f"Basic {credentials}"

    def verify_credentials(self) -> bool:
        """Validate credentials with a lightweight
        API call."""
        try:
            url = f"{self.base_url}" "/api/v2/assets.json"
            resp = self.session.get(url, params={"limit": 0})
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def get_submissions(
        self,
        asset_uid: str,
        limit: int = 300,
        start: int = 0,
    ):
        """Fetch a page of submissions."""
        url = f"{self.base_url}" f"/api/v2/assets/{asset_uid}/data.json"
        resp = self.session.get(
            url,
            params={"limit": limit, "start": start},
        )
        resp.raise_for_status()
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
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_all_submissions(
        self,
        asset_uid: str,
        since_iso: str = None,
    ):
        """Paginate through all submissions."""
        all_results = []
        start = 0
        page_size = 300

        while True:
            if since_iso:
                data = self.get_submissions_since(
                    asset_uid,
                    since_iso,
                    page_size,
                    start,
                )
            else:
                data = self.get_submissions(asset_uid, page_size, start)

            all_results.extend(data["results"])
            start += page_size

            if data.get("next") is None:
                break

        return all_results
