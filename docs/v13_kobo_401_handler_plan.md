# V13: KoboToolbox 401 Unauthorized Handler — Implementation Plan

## Context

When a user's KoboToolbox credentials become invalid (e.g., password changed on Kobo side), the sync endpoint catches the resulting `HTTPError` as a generic `Exception` and returns HTTP 502 with:

```
Error syncing form questions: 401 Client Error: Unauthorized for url:
https://eu.kobotoolbox.org/api/v2/assets/aYRqYXmmPLFfbcwC2KAULa/?format=json
```

The frontend can't distinguish this from a real server error. The user's dashboard JWT is still valid, so redirecting to `/login` (which the frontend does for 401s) is also wrong.

**Goal:** Create a clear signal path from KoboToolbox 401 → backend 403 with `error_type: "kobo_unauthorized"` → frontend actionable error message telling the user to re-login with updated Kobo credentials.

---

## Summary of Changes

### Backend Files Modified

| File | Change |
|------|--------|
| `backend/utils/kobo_client.py` | Add `KoboUnauthorizedError` exception; add `_check_response()` method; replace 5 `raise_for_status()` calls |
| `backend/api/v1/v1_odk/views.py` | Import `KoboUnauthorizedError`; add 2 `except KoboUnauthorizedError` handlers in `sync()` returning 403 |
| `backend/api/v1/v1_odk/tasks.py` | Import `KoboUnauthorizedError`; add specific `except` in 3 async task functions |

### Frontend Files Modified

| File | Change |
|------|--------|
| `frontend/src/app/dashboard/forms/page.js` | Enhanced error display for `kobo_unauthorized` error type with re-login link |

### Test Files Modified/Created

| File | Changes |
|------|---------|
| `backend/api/v1/v1_odk/tests/tests_sync_endpoint.py` | Add test: Kobo 401 → response is 403 with `error_type: "kobo_unauthorized"` |

---

## Step 1: Add `KoboUnauthorizedError` and `_check_response()` to KoboClient

**File:** `backend/utils/kobo_client.py`

### 1a. Add custom exception (after imports, before class)

```python
from base64 import b64encode

import requests


class KoboUnauthorizedError(Exception):
    """Raised when KoboToolbox returns 401 Unauthorized.

    Signals that the stored Kobo credentials are
    invalid or expired.
    """

    pass
```

### 1b. Add `_check_response()` method to `KoboClient`

Add this method right after `__init__`:

```python
def _check_response(self, resp):
    """Raise KoboUnauthorizedError on 401,
    otherwise delegate to raise_for_status."""
    if resp.status_code == 401:
        raise KoboUnauthorizedError(
            "KoboToolbox credentials are invalid "
            "or expired. Please log in again with "
            "your updated Kobo password."
        )
    resp.raise_for_status()
```

### 1c. Replace all `resp.raise_for_status()` calls

Replace in 5 locations:

**`get_submissions` (line 54):**
```python
# Before
resp.raise_for_status()

# After
self._check_response(resp)
```

**`get_submissions_since` (line 76):**
```python
self._check_response(resp)
```

**`get_asset_detail` (line 87):**
```python
self._check_response(resp)
```

**`update_validation_statuses` (line 116):**
```python
self._check_response(resp)
```

**`update_submission_data` (line 145):**
```python
self._check_response(resp)
```

---

## Step 2: Handle `KoboUnauthorizedError` in sync view

**File:** `backend/api/v1/v1_odk/views.py`

### 2a. Update imports

```python
from utils.kobo_client import (
    KoboClient,
    KoboUnauthorizedError,
)
```

### 2b. Add handler around `get_asset_detail` (lines 433–449)

Add `except KoboUnauthorizedError` **before** the existing `except Exception`:

```python
# Sync form questions and options
questions_synced = 0
try:
    content = client.get_asset_detail(
        form.asset_uid
    )
    questions_synced = sync_form_questions(
        form, content
    )
except KoboUnauthorizedError:
    return Response(
        {
            "message": (
                "KoboToolbox credentials are "
                "invalid or expired. Please "
                "log in again."
            ),
            "error_type": "kobo_unauthorized",
        },
        status=status.HTTP_403_FORBIDDEN,
    )
except Exception as e:
    return Response(
        {
            "message": (
                f"Error syncing form "
                f"questions: {str(e)}"
            )
        },
        status=status.HTTP_502_BAD_GATEWAY,
    )
```

### 2c. Wrap `fetch_all_submissions` (lines 458–460)

Currently unwrapped — add try/except:

```python
try:
    results = client.fetch_all_submissions(
        form.asset_uid, since_iso
    )
except KoboUnauthorizedError:
    return Response(
        {
            "message": (
                "KoboToolbox credentials are "
                "invalid or expired. Please "
                "log in again."
            ),
            "error_type": "kobo_unauthorized",
        },
        status=status.HTTP_403_FORBIDDEN,
    )
```

### Why HTTP 403 (not 401 or 502)

- **401 is wrong:** Would trigger the frontend Axios interceptor which redirects to `/login` — the dashboard JWT is still valid.
- **502 is vague:** Indistinguishable from actual server errors.
- **403 is correct:** User is authenticated (JWT valid) but the stored Kobo credentials lack authorization. The `error_type` field provides machine-readable differentiation.

---

## Step 3: Handle `KoboUnauthorizedError` in async tasks

**File:** `backend/api/v1/v1_odk/tasks.py`

### 3a. Update imports

```python
from utils.kobo_client import (
    KoboClient,
    KoboUnauthorizedError,
)
```

### 3b. `sync_kobo_validation_status` (line 260)

Add `except KoboUnauthorizedError` **before** `except Exception`:

```python
try:
    password = decrypt(kobo_password_enc)
    client = KoboClient(
        kobo_url, kobo_username, password
    )
    client.update_validation_statuses(
        asset_uid, kobo_ids, status_uid
    )
    logger.info(
        "Synced validation status %s for "
        "kobo_ids=%s on asset %s",
        status_uid,
        kobo_ids,
        asset_uid,
    )
except KoboUnauthorizedError:
    logger.error(
        "Kobo credentials expired for user "
        "%s — cannot sync validation status "
        "for kobo_ids=%s on asset %s",
        kobo_username,
        kobo_ids,
        asset_uid,
    )
except Exception:
    logger.exception(
        "Failed to sync validation status "
        "for kobo_ids=%s on asset %s",
        kobo_ids,
        asset_uid,
    )
```

### 3c. `sync_kobo_submission_geometry` (line 300)

Same pattern:

```python
try:
    password = decrypt(kobo_password_enc)
    client = KoboClient(
        kobo_url, kobo_username, password
    )
    client.update_submission_data(
        asset_uid,
        kobo_id,
        {polygon_field_name: odk_geoshape_str},
    )
    logger.info(
        "Synced geometry for kobo_id=%s "
        "on asset %s",
        kobo_id,
        asset_uid,
    )
except KoboUnauthorizedError:
    logger.error(
        "Kobo credentials expired for user "
        "%s — cannot sync geometry "
        "for kobo_id=%s on asset %s",
        kobo_username,
        kobo_id,
        asset_uid,
    )
except Exception:
    logger.exception(
        "Failed to sync geometry "
        "for kobo_id=%s on asset %s",
        kobo_id,
        asset_uid,
    )
```

### 3d. `download_submission_attachments` (lines 676–698)

Catch `KoboUnauthorizedError` in the inner URL loop and return early (if credentials are bad, all URLs will fail):

```python
for url in urls:
    try:
        resp = client.session.get(
            url,
            timeout=client.timeout,
        )
        if resp.status_code == 401:
            raise KoboUnauthorizedError(
                "Kobo credentials expired"
            )
        resp.raise_for_status()
        img = Image.open(
            BytesIO(resp.content)
        )
        fmt = img.format
        img = ImageOps.exif_transpose(img)
        img.save(dest_file, format=fmt)
        logger.info(
            "Downloaded attachment %s "
            "for submission %s from %s",
            att_uid,
            submission_uuid,
            url,
        )
        downloaded = True
        break
    except KoboUnauthorizedError:
        logger.error(
            "Kobo credentials expired for "
            "%s — aborting attachment "
            "downloads for submission %s",
            kobo_username,
            submission_uuid,
        )
        return
    except Exception:
        logger.warning(
            "Failed %s for "
            "attachment %s, "
            "trying next URL",
            url,
            att_uid,
        )
```

---

## Step 4: Frontend — enhanced error display on sync

**File:** `frontend/src/app/dashboard/forms/page.js`

The existing error handler at lines 142–148 already shows `err.response?.data?.message`. Enhance it to detect `kobo_unauthorized` and show a styled warning with a re-login link:

```javascript
} catch (err) {
  const isKoboAuth =
    err.response?.data?.error_type === "kobo_unauthorized";
  setStatus({
    type: isKoboAuth ? "kobo_unauthorized" : "error",
    message:
      err.response?.data?.message ||
      err.response?.data?.detail ||
      "Failed to sync form.",
  });
}
```

Then in the JSX where `status` is rendered, add a condition for the new type:

```jsx
{status?.type === "kobo_unauthorized" && (
  <Alert variant="destructive">
    <AlertDescription>
      {status.message}{" "}
      <a
        href="/login"
        className="underline font-medium hover:text-foreground"
      >
        Go to login
      </a>
    </AlertDescription>
  </Alert>
)}
```

---

## Step 5: Tests

### 5a. Test sync endpoint returns 403 on Kobo 401

**File:** `backend/api/v1/v1_odk/tests/tests_sync_endpoint.py` (add to existing or create)

```python
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from utils.kobo_client import KoboUnauthorizedError


class SyncKoboUnauthorizedTest(APITestCase):
    """sync/ returns 403 when Kobo rejects
    stored credentials."""

    def test_sync_returns_403_on_kobo_401(self):
        """When KoboClient raises
        KoboUnauthorizedError, the sync endpoint
        returns 403 with error_type."""
        with patch.object(
            KoboClient,
            "get_asset_detail",
            side_effect=KoboUnauthorizedError(
                "Credentials expired"
            ),
        ):
            url = (
                f"/api/v1/odk/forms/"
                f"{self.form.asset_uid}/sync/"
            )
            resp = self.client.post(
                url, **self.auth_header
            )
            self.assertEqual(
                resp.status_code,
                status.HTTP_403_FORBIDDEN,
            )
            self.assertEqual(
                resp.data["error_type"],
                "kobo_unauthorized",
            )

    def test_sync_returns_403_on_fetch_401(self):
        """When fetch_all_submissions raises
        KoboUnauthorizedError, the sync endpoint
        returns 403."""
        with patch.object(
            KoboClient,
            "get_asset_detail",
            return_value={"survey": [], "choices": []},
        ), patch.object(
            KoboClient,
            "fetch_all_submissions",
            side_effect=KoboUnauthorizedError(
                "Credentials expired"
            ),
        ):
            url = (
                f"/api/v1/odk/forms/"
                f"{self.form.asset_uid}/sync/"
            )
            resp = self.client.post(
                url, **self.auth_header
            )
            self.assertEqual(
                resp.status_code,
                status.HTTP_403_FORBIDDEN,
            )
```

### 5b. Test `_check_response` in KoboClient

Can be added inline in existing task tests or a new utils test file:

```python
from unittest.mock import Mock

from utils.kobo_client import (
    KoboClient,
    KoboUnauthorizedError,
)


class CheckResponseTest(TestCase):
    def setUp(self):
        self.client = KoboClient(
            "https://example.com",
            "user",
            "pass",
        )

    def test_401_raises_kobo_unauthorized(self):
        resp = Mock(status_code=401)
        with self.assertRaises(
            KoboUnauthorizedError
        ):
            self.client._check_response(resp)

    def test_200_passes(self):
        resp = Mock(status_code=200)
        resp.raise_for_status = Mock()
        self.client._check_response(resp)
        resp.raise_for_status.assert_called_once()

    def test_500_raises_http_error(self):
        resp = Mock(status_code=500)
        resp.raise_for_status.side_effect = (
            requests.exceptions.HTTPError()
        )
        with self.assertRaises(
            requests.exceptions.HTTPError
        ):
            self.client._check_response(resp)
```

---

## Verification

1. **Run backend tests:** `docker-compose exec backend python manage.py test api.v1.v1_odk`
2. **Run backend linting:** `docker-compose exec backend bash -c "black . && isort . && flake8"`
3. **Manual test:** Change Kobo password, trigger sync from UI → verify 403 + clear error message with re-login link
4. **Verify normal sync** still works with valid credentials
5. **Verify frontend 401 interceptor** still redirects to `/login` on JWT expiry (unchanged behavior)
