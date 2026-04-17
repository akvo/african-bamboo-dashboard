# Users Management — Acceptance Criteria

**Source**: [users-management-requirements.md](users-management-requirements.md)
**Design**: [users-management-design.md](users-management-design.md)

## User AC

### As an admin (Django admin)

- [ ] I can invite a user by email; an invitation email is sent.
- [ ] I see a list of all users filterable by status (`PENDING`, `ACTIVE`, `SUSPENDED`).
- [ ] I can approve or reject a `PENDING` user; the user receives an email (approve → `ACTIVE`, reject → `SUSPENDED`).
- [ ] I can deactivate an `ACTIVE` user (→ `SUSPENDED`); the user is logged out on their next request and receives an email.
- [ ] I can reactivate a `SUSPENDED` user (→ `ACTIVE`); the user receives an email.
- [ ] Lifecycle action buttons only appear when the action is valid for the user's current status.

### As a Kobo user (login)

- [ ] If I own two Kobo accounts (e.g. `ab_admin` and `ab_enumerator`) that share the **same email address**, both accounts can still log in independently — the second arriver gets a disambiguated row with a synthesized email; neither blocks the other.
- [ ] Any approval / rejection / deactivation / reactivation email I receive **names the specific Kobo account** (`ab_admin` vs `ab_enumerator`) being acted on, so I know which of my accounts changed state.
- [ ] If my Kobo credentials are valid AND I am `ACTIVE` AND `is_active=true` → I log in and receive a JWT (current behavior preserved).
- [ ] If my Kobo credentials are valid but I am `PENDING` → I see "Your access is awaiting administrator approval." (HTTP 403, no token; body has `status: "pending"`).
- [ ] If I am `SUSPENDED` → I see "Access denied." (HTTP 403, no token; body has `status: "suspended"`).
- [ ] If my Kobo credentials are invalid → I see "Invalid KoboToolbox credentials." (HTTP 401, current behavior preserved).
- [ ] If I was invited by email and log in via Kobo with the same email → I am auto-activated on first login and receive the "approved" email.
- [ ] If I am suspended while holding a valid JWT → my next API request returns 401.

### As an existing user (rollout day)

- [ ] I can log in normally after the migration without any manual approval step.

## Tech AC

### Data model

- [ ] `UserStatus` lives in [backend/api/v1/v1_users/constants.py](../../backend/api/v1/v1_users/constants.py) as a plain class with integer constants (`PENDING=0`, `ACTIVE=1`, `SUSPENDED=2`) and a `fieldStr` map — same convention as `v1_jobs/constants.py`.
- [ ] `SystemUser` gains: `is_active` (`BooleanField(default=True)` — explicit field because `AbstractBaseUser` only provides a class attribute), `status` (`IntegerField`, choices=`UserStatus.fieldStr.items()`, default=`UserStatus.PENDING`), `status_changed_at`, `status_changed_by` (FK self), `invited_at`.
- [ ] `kobo_username` is now nullable; uniqueness enforced only when not null via a conditional `UniqueConstraint` on `(kobo_username, kobo_url)`.
- [ ] Data migration sets every existing row to `status=UserStatus.ACTIVE` (integer `1`), `is_active=True`.
- [ ] Shared-email Kobo identities are handled: `bind_pending_login` catches `IntegrityError` on `SystemUser.email` UNIQUE and stores a synthesized `{kobo_username}@{kobo_url_host}` email on the later arriver; the Kobo `(kobo_url, kobo_username)` pair remains the authoritative identity key.

### Auth

- [ ] New `StatusAwareJWTAuthentication` class wired into `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`.
- [ ] JWTs for users where `status != UserStatus.ACTIVE` OR `is_active = False` are rejected on the next request.

### Login endpoint

- [ ] `/api/v1/auth/login` no longer auto-creates active users; new users land in `PENDING`.
- [ ] On invite-email match, `kobo_username` + `kobo_url` are bound to the existing pending row and status flips to `ACTIVE`.
- [ ] If Kobo returns no real email (synthesized fallback path), no auto-bind occurs; warning is logged.
- [ ] 403 response body includes `{message, status, email}` where `status` is the **string label** from `UserStatus.fieldStr` (`"pending"` or `"suspended"`), never the raw integer.

### Django admin

- [ ] Admin is reachable at `https://<WEBDOMAIN>/admin/` (same origin as frontend):
  - Dev: trailing-slash-preserving `/admin/:path*/` rule (before the catchall), `/admin/:path*`, and `/static/:path*` rewrites added to [frontend/next.config.mjs](../../frontend/next.config.mjs)
  - Prod: `location /admin` + `location /static` blocks added to [nginx/conf.d/default.conf](../../nginx/conf.d/default.conf)
  - Root URL conf mounts `path("admin/", admin.site.urls)` in [backend/african_bamboo_dashboard/urls.py](../../backend/african_bamboo_dashboard/urls.py) (was missing).
  - `CSRF_TRUSTED_ORIGINS = [WEBDOMAIN]` in [settings.py](../../backend/african_bamboo_dashboard/settings.py) so admin login form POSTs pass the Origin check.
- [ ] `SystemUserAdmin` rebuilt with: list filters by `status` and `is_active`; columns include the human-readable status label and `status_changed_at`.
- [ ] Custom add form is an "Invite user by email" form (no local password field).
- [ ] Bulk + per-row actions: Approve, Reject, Deactivate, Reactivate — each validates source state and skips invalid rows with a warning message:
  - Approve / Reject: source state must be `PENDING`.
  - Deactivate: source state must be `ACTIVE`.
  - Reactivate: source state must be `SUSPENDED`.
- [ ] All admin actions require `is_superuser`.

### Email (reuse global helper + shared template)

- [ ] [`backend/utils/email_helper.py`](../../backend/utils/email_helper.py) bug fixed: `from eswatini.settings import …` replaced with `from django.conf import settings`; `print(...)` replaced with `logger.warning(...)`.
- [ ] `EmailTypes` in the helper extended to 5 entries: `account_invited`, `account_approved`, `account_rejected`, `account_deactivated`, `account_reactivated`. Each has a matching branch in `email_context()` that sets `subject`, `body`, `cta_text`, `cta_url`.
- [ ] Shared template [`email/main.html`](../../backend/african_bamboo_dashboard/templates/email/main.html) renders `{{ body }}` and a conditional `{{ cta_url }}` / `{{ cta_text }}` button.
- [ ] `TEMPLATES[0]["DIRS"]` in settings includes `BASE_DIR / "african_bamboo_dashboard" / "templates"` so the shared template is discoverable.
- [ ] All emails sent via `EmailMultiAlternatives` (no custom Mailjet client).
- [ ] `cta_url` in types that carry a login CTA uses `settings.WEBDOMAIN`.
- [ ] Email `context` includes `kobo_username` and `kobo_url` (populated from `user.kobo_username` / `user.kobo_url` by `send_email_by_user_id`).
- [ ] A `_account_label()` helper in `email_helper.py` appends `" for the KoboToolbox account ``<kobo_username>``"` to every state-change email body when `kobo_username` is set, so recipients who own multiple Kobo accounts can disambiguate the action. Empty string when `kobo_username` is null (invite-only rows).
- [ ] No per-template files under `v1_users/templates/v1_users/email/` (does not exist).

### Async dispatch (django_q)

- [ ] `utils/email_helper.py` exposes `send_email_by_user_id(user_id, type, extra_context=None)` (task entry-point) and `queue_email(user, type, extra_context=None)` (async wrapper calling `async_task`). Both are generic across email types.
- [ ] `services/approval.py` lifecycle helpers call `queue_email(user, EmailTypes.<value>)`; admin actions return without waiting for Mailjet.
- [ ] `Q_CLUSTER["sync"] = bool(TEST_ENV)` so tests run tasks inline and `mail.outbox` assertions still work.
- [ ] `async_task` arguments are pickle-friendly (`user.id` int + `str` + `dict`, never the `SystemUser` instance).
- [ ] Email send failures are logged but do **not** raise; lifecycle transition remains committed; failures appear at `/admin/django_q/failure/`.
- [ ] `send_email_by_user_id` gracefully skips if the user has been deleted between enqueue and execution (`user = User.objects.filter(pk=...).first()` returns `None` → warning logged).
- [ ] No new operational change: the existing `worker` container in [docker-compose.yml:40](../../docker-compose.yml#L40) already runs `python manage.py qcluster` via [run_worker.sh](../../backend/run_worker.sh). Verified by `docker compose ps worker` before smoke test.
- [ ] The existing `v1_jobs` app is **not** modified — email notifications do not create `Jobs` rows.

### Code organisation & style

- [ ] New files: `v1_users/auth.py`, `v1_users/services/__init__.py`, `v1_users/services/approval.py`. **No** `v1_users/services/emails.py` — email plumbing lives in the global [`backend/utils/email_helper.py`](../../backend/utils/email_helper.py) instead (modified, not created), per decision to reuse the shared helper across modules.
- [ ] Each new file ≤ 400 lines; passes `black`, `isort`, `flake8` (80 char max).
- [ ] All imports at top of file; no inline imports.

### Tests (one file per endpoint/concern, per CLAUDE.md)

- [ ] `tests_login_pending_endpoint.py`
- [ ] `tests_login_suspended_endpoint.py`
- [ ] `tests_invite_binding.py` — covers email-match + synthesized-email fallback
- [ ] `tests_admin_lifecycle_actions.py` — covers all 4 actions and their source-state preconditions
- [ ] `tests_status_aware_jwt_auth.py`
- [ ] `tests_email_notifications.py` — uses `django.core.mail.outbox`
- [ ] `tests_users_model.py` extended for new fields + data migration (existing rows backfilled to `ACTIVE`)
- [ ] All tests green; `python manage.py test` passes.

## Out of Scope (call out in Asana to prevent scope creep)

- [ ] No Next.js dashboard work (Django admin only for v1).
- [ ] No audit-log table (only latest transition stored).
- [ ] No Telegram notifications.
- [ ] No platform-level form ACL changes (defer to Kobo).
