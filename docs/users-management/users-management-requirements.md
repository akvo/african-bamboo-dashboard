# Users Management — Requirements

## Problem Statement

Today, anyone with valid KoboToolbox credentials can log in to the platform. The login view at [backend/api/v1/v1_users/views.py:60](../../backend/api/v1/v1_users/views.py#L60) auto-creates a `SystemUser` on every successful Kobo credential check, with no platform-side allowlist. Form-level visibility is implicitly governed by Kobo's own ACL.

We need to gate platform access so that holding valid Kobo credentials is **necessary but not sufficient** to log in. An admin must approve each Kobo identity (`kobo_username` + `kobo_url`) before the user gains access. Form-level visibility continues to defer to Kobo's own ACL — no change there.

## Decisions Log

| # | Question | Decision |
|---|---|---|
| 1 | Access gate model | **Approval queue** — anyone may attempt login; first-time login creates a `pending` row; admin must approve. |
| 2 | Roles | **Binary** — allowed / not allowed. No reviewer/viewer split in v1. |
| 3 | First-admin bootstrap | `python manage.py createsuperuser` |
| 4 | Form-level access | **Defer to Kobo** entirely. No platform-side per-form ACL. |
| 5 | Lifecycle actions | invite, approve, reject, deactivate (no hard delete) |
| 6 | Existing users on rollout | All auto-approved via data migration |
| 7 | Audit log | **Out of scope** — only the latest transition is recorded |
| 8 | Notifications | **Email only** (Mailjet, already configured) |
| 9 | Invite matching | **Auto-match by Kobo-returned email**; if Kobo returns no email (synthesized fallback), skip auto-bind, log warning, leave as silent pending |
| 10 | JWT revocation | **Lightweight** — status check in the SimpleJWT auth class |
| 11 | Self-service request | **Silent pending** — no justification message; row is created and admins see it in the list |
| 12 | Admin UI scope | **Django admin only** for v1; no Next.js dashboard work |
| 13 | Email dispatch mode | **Async via `django_q.async_task`** so lifecycle actions return instantly. The existing `v1_jobs` app is **not** used (it models user-initiated, downloadable, pollable jobs — wrong fit for fire-and-forget notifications). |
| 14 | Status enum | **3 integer states** in `backend/api/v1/v1_users/constants.py`: `PENDING=0`, `ACTIVE=1`, `SUSPENDED=2`. Mirrors the existing `JobStatus` / `JobTypes` pattern in `v1_jobs/constants.py`. The 4 admin actions (approve/reject/deactivate/reactivate) remain distinct — `reject` and `deactivate` both target `SUSPENDED`, distinguished by source-state precondition and email template. |
| 15 | Shared-email Kobo accounts | Kobo allows two distinct `(kobo_url, kobo_username)` identities to share one email address. **Authoritative identity is the Kobo pair**, not email. When the second identity tries to log in and collides on `SystemUser.email` UNIQUE, the row is stored with a synthesized email `{kobo_username}@{kobo_url_host}` so both accounts can be administered independently. |
| 16 | Kobo account disambiguation in emails | All state-change emails (approved / rejected / deactivated / reactivated) **must name the `kobo_username`** in the body so shared-email recipients know which of their accounts was acted on. Invite emails do not yet have a Kobo identity, so the disambiguator is omitted there. |

## Functional Requirements

### FR-1 — Login becomes a two-step gate

- Kobo credential check still runs first.
- If credentials are valid AND `status = ACTIVE` AND `is_active = true` → JWT issued (current behavior).
- If credentials are valid but `status = PENDING` → 403 with message "Awaiting administrator approval."
- If `status = SUSPENDED` → 403 with message "Access denied."
- If first-ever login with valid Kobo creds → row created in `PENDING`, login refused.

### FR-2 — Admin user list

- Filter by status (pending / approved / rejected / deactivated).
- Search by name, email, kobo_username.
- Only `is_superuser = true` accounts may access.

### FR-3 — Lifecycle actions (admin-only)

| Action | From state | To state | Side effect |
|---|---|---|---|
| Invite | (none) | `PENDING` | Email sent to invitee |
| Approve | `PENDING` | `ACTIVE` | Email sent: "Access granted" |
| Reject | `PENDING` | `SUSPENDED` | Email sent: "Access denied" |
| Deactivate | `ACTIVE` | `SUSPENDED` | Email sent; existing JWTs become invalid on next request |
| Reactivate | `SUSPENDED` | `ACTIVE` | Email sent: "Access restored" |

`Reject` and `Deactivate` both land at `SUSPENDED` but are kept as distinct admin actions because their source-state preconditions differ and they send different emails. `Reactivate` is allowed only from `SUSPENDED`.

No hard delete via this UI — soft delete only (existing `SoftDeletes` mixin already supports this).

### FR-4 — Invite flow (Option A — auto-match by email)

- Admin enters: **email** (required) + optional name + optional `kobo_url`. No `kobo_username` needed at invite time.
- System creates a `pending` row with `invited_at` set.
- Invitee receives Mailjet email with login link.
- On their first successful Kobo login:
  - If Kobo returns a real email → look up pending invite by **case-insensitive normalized email**. If found → bind `kobo_username` + `kobo_url`, flip status → `ACTIVE`, send "approved" email.
  - If Kobo returns no email (synthesized fallback path in [views.py:55](../../backend/api/v1/v1_users/views.py#L55)) → do **not** auto-bind; create silent pending row; log warning.
  - If no matching invite exists → standard silent pending flow.

### FR-5 — Form-level access

**Out of scope.** Platform continues to delegate per-form ACL to Kobo (no change to current behavior).

### FR-6 — Bootstrap

- First admin created via `python manage.py createsuperuser`.
- Subsequent admins promoted by another admin (toggle `is_superuser` via Django admin only — no public endpoint).

### FR-7 — Migration / rollout

- Data migration: every existing `SystemUser` is set to `status = ACTIVE` (integer `1`), `is_active = true`. No one is locked out.

### FR-8 — Email notifications

- Five templates: invitation, approved, rejected, deactivated, reactivated.
- Email-only; no Telegram or in-app notification.
- **Dispatched asynchronously** via `django_q.tasks.async_task`. Lifecycle actions enqueue the email and return immediately; the qcluster worker performs the Mailjet call.
- Failed email send must NOT block the lifecycle action — failure is logged by django_q (visible at `/admin/django_q/failure/`) and by the worker's logger; the lifecycle transition remains committed.
- In tests (`TEST_ENV=true`), `Q_CLUSTER["sync"] = True` runs tasks inline so `mail.outbox` assertions still work.

## Non-Functional Requirements

- **Security**: Approval/lifecycle endpoints require `is_superuser`; non-admin requests get 403. Pending/rejected/deactivated users cannot obtain a JWT, and existing JWTs for deactivated users must be rejected on the next request.
- **Backwards compatibility**: Existing approved users continue to log in seamlessly post-migration.
- **Auditability**: Out of scope (per decision 7). Only the most recent state transition is stored.
- **i18n**: Email templates should be translatable (use Django's `gettext`).
- **Testing**: Per CLAUDE.md, each new endpoint gets its own test file.

## User Stories

- **US-1** — As an admin, I see a list of pending users so that I can quickly approve or reject newcomers.
- **US-2** — As an admin, I can invite a known Kobo user by email so that they can self-onboard without a separate approval step.
- **US-3** — As an admin, I can deactivate a user without losing their history so that access is revocable.
- **US-4** — As a Kobo user, when I log in for the first time, I get a clear message that my access is awaiting approval — not a generic auth failure.
- **US-5** — As a deactivated user, my next API request is rejected even if my JWT has not expired.
- **US-6** — As an existing approved user, the rollout does not interrupt my access.

## Out of Scope (v1)

- Next.js dashboard UI for user management (Django admin only).
- Audit log table (only latest transition stored).
- Telegram notifications.
- Platform-level form ACL changes (defer to Kobo).
- Roles beyond superuser/binary-allowed.
- Self-service "request access with justification" form.
