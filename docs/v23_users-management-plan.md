# Plan: Users Management — Approval Gate for Kobo-backed Login

## Context

Today, [`backend/api/v1/v1_users/views.py:60`](../backend/api/v1/v1_users/views.py#L60) auto-creates a `SystemUser` for any successful Kobo credential check. We need an admin approval gate so holding valid Kobo credentials is **necessary but not sufficient** to log in. Form-level visibility continues to defer to Kobo's ACL — no change there.

Detailed specs: [docs/users-management/](users-management/)
- [users-management-requirements.md](users-management/users-management-requirements.md)
- [users-management-design.md](users-management/users-management-design.md)
- [users-management-user-ac.md](users-management/users-management-user-ac.md)

---

## Step 1: Backend — Extend `SystemUser` with status fields

**Already in place:** [`backend/api/v1/v1_users/constants.py`](../backend/api/v1/v1_users/constants.py) defines:

```python
class UserStatus:
    PENDING = 0
    ACTIVE = 1
    SUSPENDED = 2

    fieldStr = {
        PENDING: "pending",
        ACTIVE: "active",
        SUSPENDED: "suspended",
    }
```

This mirrors the existing `JobStatus` / `JobTypes` pattern in `v1_jobs/constants.py`. The model imports from this file — do **not** redefine `UserStatus` inside `models.py`.

**File:** `backend/api/v1/v1_users/models.py`

Add four new fields and replace the unique constraint so `kobo_username` may be null on invite-only rows.

```python
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core import signing
from django.db import models
from django.db.models import Q

from api.v1.v1_users.constants import UserStatus
from utils.custom_manager import UserManager
from utils.soft_deletes_model import SoftDeletes


class SystemUser(AbstractBaseUser, PermissionsMixin, SoftDeletes):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)

    kobo_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="KoboToolbox server URL",
    )
    kobo_username = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="KoboToolbox username",
    )
    kobo_password = models.TextField(
        null=True,
        blank=True,
        help_text="Encrypted KoboToolbox password",
    )

    # `AbstractBaseUser` exposes `is_active` as a CLASS
    # ATTRIBUTE (not a field) defaulting to True, so without
    # an explicit model field it cannot be persisted or
    # queried. We need it persisted because the auth class
    # and admin ListFilter both read it.
    is_active = models.BooleanField(default=True)
    status = models.IntegerField(
        choices=UserStatus.fieldStr.items(),
        default=UserStatus.PENDING,
    )
    status_changed_at = models.DateTimeField(null=True, blank=True)
    status_changed_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    invited_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def delete(self, using=None, keep_parents=False, hard: bool = False):
        return super().delete(
            using=using, keep_parents=keep_parents, hard=hard
        )

    def get_sign_pk(self):
        return signing.dumps(self.pk)

    @property
    def is_staff(self):
        return self.is_superuser

    class Meta:
        db_table = "system_user"
        constraints = [
            models.UniqueConstraint(
                fields=["kobo_username", "kobo_url"],
                condition=Q(kobo_username__isnull=False),
                name="unique_kobo_identity_when_set",
            ),
        ]
```

---

## Step 2: Backend — Migration (schema + data)

**File (new):** `backend/api/v1/v1_users/migrations/0002_user_access_management.py`

```python
from django.db import migrations, models
from django.db.models import Q


def backfill_existing_users_to_active(apps, schema_editor):
    # UserStatus.ACTIVE = 1 (literal used here so future renames of
    # the constant cannot break this historical migration).
    SystemUser = apps.get_model("v1_users", "SystemUser")
    SystemUser.objects.update(status=1, is_active=True)


def revert_backfill(apps, schema_editor):
    # Data migration is intentionally not reversible safely.
    # The schema reverse will drop the status column anyway.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("v1_users", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="systemuser",
            name="kobo_username",
            field=models.CharField(
                blank=True, max_length=255, null=True,
                help_text="KoboToolbox username",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="systemuser",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "pending"),
                    (1, "active"),
                    (2, "suspended"),
                ],
                default=0,
            ),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="status_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="status_changed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="+",
                to="v1_users.systemuser",
            ),
        ),
        migrations.AddField(
            model_name="systemuser",
            name="invited_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="systemuser",
            constraint=models.UniqueConstraint(
                condition=Q(kobo_username__isnull=False),
                fields=("kobo_username", "kobo_url"),
                name="unique_kobo_identity_when_set",
            ),
        ),
        migrations.RunPython(
            backfill_existing_users_to_active,
            revert_backfill,
        ),
    ]
```

---

## Step 3: Backend — `StatusAwareJWTAuthentication`

**File (new):** `backend/api/v1/v1_users/auth.py`

```python
import logging

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from api.v1.v1_users.constants import UserStatus

logger = logging.getLogger(__name__)


class StatusAwareJWTAuthentication(JWTAuthentication):
    """JWT auth that rejects suspended or non-active users."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        if not user.is_active:
            raise AuthenticationFailed(
                "User access has been revoked.",
                code="user_inactive",
            )
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationFailed(
                "User access is not active.",
                code="user_not_active",
            )
        return user, validated_token
```

**Wire it up** in `backend/african_bamboo_dashboard/settings.py`:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.v1.v1_users.auth.StatusAwareJWTAuthentication",
    ],
    # ... rest unchanged
}
```

---

## Step 4: Backend — Email dispatch via the global helper

Emails are dispatched asynchronously via `django_q.tasks.async_task`. We reuse the existing global [`backend/utils/email_helper.py`](../backend/utils/email_helper.py) + the shared [`templates/email/main.html`](../backend/african_bamboo_dashboard/templates/email/main.html) — no per-template files and no dedicated `v1_users/services/emails.py`. Every transactional email flows through the helper; types are distinguished by `EmailTypes` + the `email_context()` branch.

The existing `v1_jobs` app is intentionally **not** used — it models user-initiated, downloadable, pollable work; email notifications are system-initiated fire-and-forget.

### 4.1 Fix the existing helper (bugs + extensions)

**File:** `backend/utils/email_helper.py`

- Replace `from eswatini.settings import EMAIL_FROM, WEBDOMAIN` → `from django.conf import settings`; reference `settings.EMAIL_FROM` / `settings.WEBDOMAIN` at call sites.
- Replace `print("Error", ex)` with a module-level `logger.warning(...)`.
- Extend `EmailTypes` to five entries; add a branch in `email_context()` for each. Each state-change branch appends a `_account_label()` suffix — e.g. `" for the KoboToolbox account `ab_admin`"` — to the body so recipients who own multiple Kobo accounts know which one was acted on. The label is empty when `kobo_username` is null (pure invite-only rows). Keep the single shared template (`email/main.html`):

```python
class EmailTypes:
    account_invited = "account_invited"
    account_approved = "account_approved"
    account_rejected = "account_rejected"
    account_deactivated = "account_deactivated"
    account_reactivated = "account_reactivated"
    # FieldStr mirroring the same keys — keep the pattern
```

- Append two new public callables at the bottom of the file:

```python
def send_email_by_user_id(
    user_id: int,
    type: str,
    extra_context: dict = None,
) -> None:
    """Task entry-point. Pickle-safe args for django_q."""
    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        logger.warning(
            "Email task: user %s no longer exists; skipping.",
            user_id,
        )
        return
    context = {
        "send_to": [user.email],
        "name": user.name or user.email,
        # kobo_username + kobo_url let email_context() name
        # the specific Kobo account in the body, which is
        # critical when a single email address is shared
        # across two Kobo identities.
        "kobo_username": user.kobo_username,
        "kobo_url": user.kobo_url,
    }
    if extra_context:
        context.update(extra_context)
    send_email(context=context, type=type)


def queue_email(
    user,
    type: str,
    extra_context: dict = None,
) -> None:
    """Caller-facing async wrapper. Returns instantly."""
    async_task(
        "utils.email_helper.send_email_by_user_id",
        user.id,
        type,
        extra_context or {},
    )
```

### 4.2 Flesh out the shared template

**File:** `backend/african_bamboo_dashboard/templates/email/main.html`

The existing file only renders `<title>`. Render `{{ body }}` and a conditional CTA button using `cta_url` + `cta_text`. All five email types populate these via `email_context()`.

### 4.3 Register the template dir

**File:** `backend/african_bamboo_dashboard/settings.py`

Project-root `templates/` is outside every app in `INSTALLED_APPS`, so `APP_DIRS=True` doesn't find it. Add it to `DIRS`:

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "african_bamboo_dashboard" / "templates",
        ],
        "APP_DIRS": True,
        # ... rest unchanged
    },
]
```

### 4.4 Callers

`services/approval.py` (next step) calls the helper directly — no v1_users-specific email module:

```python
from utils.email_helper import EmailTypes, queue_email

# in approve(): queue_email(user, EmailTypes.account_approved)
# in reject(): queue_email(user, EmailTypes.account_rejected)
# ... etc.
```

**Pickling rule**: `async_task` arguments are pickled to the django_q broker. Always pass `user.id` (int) and primitive types, never the `SystemUser` instance.

**Local dev**: no extra step. The existing `worker` container in [docker-compose.yml:40](../docker-compose.yml#L40) already runs `python manage.py qcluster` via [run_worker.sh](../backend/run_worker.sh).

**Failure visibility**: failed tasks land in `/admin/django_q/failure/`. The helper's `send_email` logs a warning on exception so the worker stdout shows the cause.

**No per-template files** under `v1_users/templates/v1_users/email/`. Everything routes through `templates/email/main.html`.

---

## Step 5: Backend — Approval service (invite + lifecycle)

**File (new):** `backend/api/v1/v1_users/services/approval.py`

```python
import enum
import logging
from typing import Optional, Tuple

from django.db import IntegrityError, transaction
from django.utils import timezone

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser
from utils.email_helper import EmailTypes, queue_email

logger = logging.getLogger(__name__)


class BindOutcome(str, enum.Enum):
    BOUND = "bound"
    SILENT_PENDING = "silent_pending"
    ALREADY_ACTIVE = "already_active"


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _synthesized_email(kobo_username: str, kobo_url: str) -> str:
    """Deterministic fallback address derived from the Kobo
    identity. Used when two distinct Kobo accounts share an
    email — the later-arriving row needs a disambiguated
    email so the UNIQUE constraint on SystemUser.email holds.
    """
    host = (kobo_url or "").split("//")[-1].split("/")[0]
    return f"{kobo_username}@{host}"


def create_invite(
    *,
    email: str,
    name: Optional[str],
    kobo_url: Optional[str],
    invited_by: SystemUser,
) -> SystemUser:
    """Create a pending row and send invitation email.

    Raises ValueError if a user with that email already exists.
    """
    normalized = _normalize_email(email)
    if SystemUser.objects.filter(email__iexact=normalized).exists():
        raise ValueError(
            f"A user with email {normalized} already exists."
        )
    user = SystemUser.objects.create(
        email=normalized,
        name=(name or "").strip() or normalized,
        kobo_url=kobo_url or None,
        status=UserStatus.PENDING,
        is_active=False,
        invited_at=timezone.now(),
        status_changed_at=timezone.now(),
        status_changed_by=invited_by,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    queue_email(
        user,
        EmailTypes.account_invited,
        extra_context={
            "inviter_name": (
                invited_by.name or invited_by.email
            ),
        },
    )
    return user


def bind_pending_login(
    *,
    email_from_kobo: str,
    kobo_username: str,
    kobo_url: str,
    encrypted_password: str,
    name_from_kobo: Optional[str],
    email_was_synthesized: bool,
) -> Tuple[SystemUser, BindOutcome]:
    """Match an invite by email or fall back to silent pending.

    - Real Kobo email + matching pending invite -> bind, approve.
    - Synthesized email -> never auto-bind.
    - No match -> create silent pending row.
    """
    normalized = _normalize_email(email_from_kobo)
    existing = SystemUser.objects.filter(
        kobo_username=kobo_username, kobo_url=kobo_url
    ).first()
    if existing is not None:
        existing.kobo_password = encrypted_password
        if name_from_kobo and existing.name == existing.email:
            existing.name = name_from_kobo
        existing.save()
        outcome = (
            BindOutcome.ALREADY_ACTIVE
            if existing.status == UserStatus.ACTIVE
            else BindOutcome.SILENT_PENDING
        )
        return existing, outcome

    if not email_was_synthesized:
        invite = SystemUser.objects.filter(
            email__iexact=normalized,
            status=UserStatus.PENDING,
            kobo_username__isnull=True,
        ).first()
        if invite is not None:
            invite.kobo_username = kobo_username
            invite.kobo_url = kobo_url
            invite.kobo_password = encrypted_password
            if name_from_kobo:
                invite.name = name_from_kobo
            invite.status = UserStatus.ACTIVE
            invite.is_active = True
            invite.status_changed_at = timezone.now()
            invite.save()
            queue_email(invite, EmailTypes.account_approved)
            return invite, BindOutcome.BOUND
    else:
        logger.warning(
            "Skipping invite auto-bind for %s: "
            "Kobo did not return a real email address.",
            kobo_username,
        )

    create_kwargs = {
        "email": normalized,
        "name": name_from_kobo or kobo_username,
        "kobo_username": kobo_username,
        "kobo_url": kobo_url,
        "kobo_password": encrypted_password,
        "status": UserStatus.PENDING,
        "is_active": False,
        "status_changed_at": timezone.now(),
    }
    try:
        with transaction.atomic():
            user = SystemUser.objects.create(**create_kwargs)
    except IntegrityError:
        # Real email already belongs to a different Kobo
        # identity (e.g. `ab_admin` and `ab_enumerator` sharing
        # `sidharth@african-bamboo.com`). SystemUser.email is
        # UNIQUE for admin-login reasons, but the authoritative
        # Kobo identity is (kobo_url, kobo_username). Fall back
        # to a synthesized email so the row can persist.
        synth = _synthesized_email(kobo_username, kobo_url)
        logger.warning(
            "Email collision on silent-pending: real email "
            "%s already used; storing synthesized email %s "
            "for kobo identity %s@%s.",
            normalized, synth, kobo_username, kobo_url,
        )
        create_kwargs["email"] = synth
        user = SystemUser.objects.create(**create_kwargs)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user, BindOutcome.SILENT_PENDING


def _transition(
    user: SystemUser,
    *,
    by: SystemUser,
    to_status: int,
    is_active: bool,
    email_type: str,
) -> None:
    user.status = to_status
    user.is_active = is_active
    user.status_changed_at = timezone.now()
    user.status_changed_by = by
    user.save(
        update_fields=[
            "status",
            "is_active",
            "status_changed_at",
            "status_changed_by",
        ]
    )
    queue_email(user, email_type)


def approve(user: SystemUser, by: SystemUser) -> None:
    # PENDING -> ACTIVE
    _transition(
        user,
        by=by,
        to_status=UserStatus.ACTIVE,
        is_active=True,
        email_type=EmailTypes.account_approved,
    )


def reject(user: SystemUser, by: SystemUser) -> None:
    # PENDING -> SUSPENDED
    _transition(
        user,
        by=by,
        to_status=UserStatus.SUSPENDED,
        is_active=False,
        email_type=EmailTypes.account_rejected,
    )


def deactivate(user: SystemUser, by: SystemUser) -> None:
    # ACTIVE -> SUSPENDED
    _transition(
        user,
        by=by,
        to_status=UserStatus.SUSPENDED,
        is_active=False,
        email_type=EmailTypes.account_deactivated,
    )


def reactivate(user: SystemUser, by: SystemUser) -> None:
    # SUSPENDED -> ACTIVE
    _transition(
        user,
        by=by,
        to_status=UserStatus.ACTIVE,
        is_active=True,
        email_type=EmailTypes.account_reactivated,
    )
```

---

## Step 6: Backend — Update login view

**File:** `backend/api/v1/v1_users/views.py`

Replace the `update_or_create` block with `bind_pending_login` and short-circuit non-approved users with 403.

```python
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    PendingLoginResponseSerializer,
    UpdateUserSerializer,
    UserSerializer,
)
from api.v1.v1_users.services.approval import bind_pending_login
from utils.custom_serializer_fields import validate_serializers_message
from utils.default_serializers import DefaultResponseSerializer
from utils.encryption import encrypt
from utils.kobo_client import KoboClient


_PENDING_MESSAGES = {
    UserStatus.PENDING: (
        "Your access is awaiting administrator approval."
    ),
    UserStatus.SUSPENDED: "Access denied.",
}


@extend_schema(
    request=LoginSerializer,
    responses={
        200: LoginResponseSerializer,
        401: DefaultResponseSerializer,
        403: PendingLoginResponseSerializer,
    },
    tags=["Auth"],
)
@api_view(["POST"])
def login(request, version):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    kobo_url = serializer.validated_data["kobo_url"]
    kobo_username = serializer.validated_data["kobo_username"]
    kobo_password = serializer.validated_data["kobo_password"]

    client = KoboClient(kobo_url, kobo_username, kobo_password)
    user_detail = client.verify_credentials()
    if not user_detail:
        return Response(
            {"message": "Invalid KoboToolbox credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    name_from_kobo = None
    email_from_kobo = None
    if isinstance(user_detail, dict):
        name_from_kobo = user_detail.get("name") or None
        email_from_kobo = user_detail.get("email") or None

    email_was_synthesized = email_from_kobo is None
    if email_was_synthesized:
        host = kobo_url.split("//")[-1].split("/")[0]
        email_from_kobo = f"{kobo_username}@{host}"

    user, _ = bind_pending_login(
        email_from_kobo=email_from_kobo,
        kobo_username=kobo_username,
        kobo_url=kobo_url,
        encrypted_password=encrypt(kobo_password),
        name_from_kobo=name_from_kobo,
        email_was_synthesized=email_was_synthesized,
    )

    if user.status != UserStatus.ACTIVE or not user.is_active:
        return Response(
            {
                "message": _PENDING_MESSAGES.get(
                    user.status, "Access denied."
                ),
                # Send the string label, not the raw integer,
                # so the frontend can switch on it.
                "status": UserStatus.fieldStr.get(
                    user.status, "suspended"
                ),
                "email": user.email,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    refresh = RefreshToken.for_user(user)
    expiration_time = datetime.fromtimestamp(refresh.access_token["exp"])
    expiration_time = timezone.make_aware(expiration_time)

    data = {
        "user": UserSerializer(instance=user).data,
        "token": str(refresh.access_token),
        "expiration_time": expiration_time,
    }
    response = Response(data, status=status.HTTP_200_OK)
    response.set_cookie(
        "AUTH_TOKEN",
        str(refresh.access_token),
        expires=expiration_time,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )
    return response


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    # ... unchanged
```

**File:** `backend/api/v1/v1_users/serializers.py`

Add the 403 response shape:

```python
class PendingLoginResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    status = serializers.CharField()
    email = serializers.EmailField()
```

---

## Step 7: Backend — Rebuild `SystemUserAdmin`

**File:** `backend/api/v1/v1_users/admin.py`

```python
from django import forms
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect, render

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser
from api.v1.v1_users.services import approval


class InviteUserForm(forms.Form):
    email = forms.EmailField()
    name = forms.CharField(required=False)
    kobo_url = forms.URLField(required=False)


@admin.register(SystemUser)
class SystemUserAdmin(admin.ModelAdmin):
    site_header = "Manage Users"
    list_display = (
        "email",
        "name",
        "kobo_username",
        "kobo_url",
        "status_label",
        "is_active",
        "status_changed_at",
        "last_login",
    )
    list_filter = ("status", "is_active", "is_superuser")
    search_fields = ("email", "name", "kobo_username")
    ordering = ("-status_changed_at",)
    readonly_fields = (
        "status_changed_at",
        "status_changed_by",
        "last_login",
        "invited_at",
    )
    fieldsets = (
        ("Identity", {"fields": ("email", "name")}),
        ("Kobo", {"fields": ("kobo_url", "kobo_username")}),
        (
            "Access",
            {
                "fields": (
                    "status",
                    "is_active",
                    "status_changed_at",
                    "status_changed_by",
                    "invited_at",
                )
            },
        ),
        ("Permissions", {"fields": ("is_superuser",)}),
    )
    actions = (
        "action_approve",
        "action_reject",
        "action_deactivate",
        "action_reactivate",
    )

    @admin.display(description="Status", ordering="status")
    def status_label(self, obj):
        # Render the human-readable label; column still sorts
        # on the underlying integer.
        return UserStatus.fieldStr.get(obj.status, "?")

    def has_module_permission(self, request):
        return bool(
            request.user.is_authenticated and request.user.is_superuser
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "invite/",
                self.admin_site.admin_view(self.invite_view),
                name="v1_users_systemuser_invite",
            ),
        ]
        return custom + urls

    def add_view(self, request, form_url="", extra_context=None):
        return redirect("admin:v1_users_systemuser_invite")

    def invite_view(self, request):
        if not request.user.is_superuser:
            messages.error(request, "Permission denied.")
            return redirect("admin:v1_users_systemuser_changelist")
        if request.method == "POST":
            form = InviteUserForm(request.POST)
            if form.is_valid():
                try:
                    approval.create_invite(
                        email=form.cleaned_data["email"],
                        name=form.cleaned_data.get("name") or None,
                        kobo_url=(
                            form.cleaned_data.get("kobo_url") or None
                        ),
                        invited_by=request.user,
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, "Invitation sent.")
                    return redirect(
                        "admin:v1_users_systemuser_changelist"
                    )
        else:
            form = InviteUserForm()
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Invite user",
            "opts": self.model._meta,
        }
        return render(
            request, "admin/v1_users/invite_user.html", context
        )

    def _bulk_action(
        self, request, queryset, *, allowed_from, fn, label
    ):
        ok, skipped = 0, 0
        for user in queryset:
            if user.status not in allowed_from:
                skipped += 1
                continue
            fn(user, by=request.user)
            ok += 1
        if ok:
            messages.success(
                request, f"{label} {ok} user(s)."
            )
        if skipped:
            messages.warning(
                request,
                f"Skipped {skipped} user(s) not eligible for {label}.",
            )

    @admin.action(description="Approve selected pending users")
    def action_approve(self, request, queryset):
        self._bulk_action(
            request, queryset,
            allowed_from={UserStatus.PENDING},
            fn=approval.approve, label="Approved",
        )

    @admin.action(description="Reject selected pending users")
    def action_reject(self, request, queryset):
        self._bulk_action(
            request, queryset,
            allowed_from={UserStatus.PENDING},
            fn=approval.reject, label="Rejected",
        )

    @admin.action(description="Deactivate selected active users")
    def action_deactivate(self, request, queryset):
        self._bulk_action(
            request, queryset,
            allowed_from={UserStatus.ACTIVE},
            fn=approval.deactivate, label="Deactivated",
        )

    @admin.action(description="Reactivate selected suspended users")
    def action_reactivate(self, request, queryset):
        self._bulk_action(
            request, queryset,
            allowed_from={UserStatus.SUSPENDED},
            fn=approval.reactivate, label="Reactivated",
        )
```

**Template (new):** `backend/api/v1/v1_users/templates/admin/v1_users/invite_user.html` — extends `admin/base_site.html`, renders `{{ form.as_p }}` inside an admin-styled form with submit button labelled "Send invitation".

---

## Step 7b: Expose `/admin` via the frontend host

The Django admin lives at `/admin/` on the backend (port 8000). We route it through the same origin as the frontend so admins access it at `https://<WEBDOMAIN>/admin/`. `/static/*` must also be routed because Django admin loads its CSS/JS from `/static/admin/*`.

### Dev — `frontend/next.config.mjs`

Add three entries to the `rewrites()` array. **Rule order matters**: the trailing-slash-preserving rule must come BEFORE the catchall. Without it, Next.js strips the trailing slash when forwarding `/admin/`, Django's `APPEND_SLASH` redirects back to `/admin/`, and you get a redirect loop.

```js
async rewrites() {
    return [
      // ... existing /api and /storage rewrites
      {
        // Trailing-slash preservation must be first.
        source: "/admin/:path*/",
        destination: "http://127.0.0.1:8000/admin/:path*/",
      },
      {
        source: "/admin/:path*",
        destination: "http://127.0.0.1:8000/admin/:path*",
      },
      {
        source: "/static/:path*",
        destination: "http://127.0.0.1:8000/static/:path*",
      },
    ];
  },
```

Keep `skipTrailingSlashRedirect: true` at the Next config root — without it, Next's own trailing-slash normalization conflicts with Django's.

### Prod — `nginx/conf.d/default.conf`

Add two `location` blocks above the catch-all `location /`:

```nginx
location /admin {
    proxy_pass              http://backend:8000;
    proxy_set_header        Host $host;
    proxy_set_header        X-Real-IP $remote_addr;
    proxy_set_header        X-Forwarded-Host $host;
    proxy_set_header        X-Forwarded-Proto $scheme;
    proxy_http_version      1.1;
}

location /static {
    proxy_pass              http://backend:8000;
    proxy_set_header        Host $host;
    proxy_set_header        X-Real-IP $remote_addr;
}
```

The `/admin` block mirrors the existing `/api` block's header set (`Host` / `X-Forwarded-Host` / `X-Forwarded-Proto`) so Django's CSRF host validation on admin form POSTs keeps working. `/static/*` can later be optimised by running `collectstatic` and serving it directly from nginx (same pattern as `/storage/attachments/`); proxying is fine for v1.

**Optional hardening**: IP-allowlist `/admin` in prod with `allow <cidr>; deny all;` inside the `location /admin` block. Flag for ops; not in this PR.

---

## Step 7c: Mount Django admin at `/admin/`

**File:** `backend/african_bamboo_dashboard/urls.py`

The project's root URL conf never included `admin.site.urls`, so `/admin/` returned 404. Add the mount:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # ... existing /api includes unchanged
]
```

This is a pre-existing configuration gap; without it, the rewrites above still 404.

---

## Step 7d: CSRF trusted origins

**File:** `backend/african_bamboo_dashboard/settings.py`

Django admin form POSTs come from the frontend origin (`http://localhost:3000` in dev, `settings.WEBDOMAIN` in prod). Django 4's CSRF middleware rejects these as `"Origin checking failed"` unless the origin is explicitly trusted:

```python
# CSRF trusted origins — Django admin form POSTs come from
# the frontend proxy host. Without this, Django's Origin
# check rejects the request with 403 "Origin checking failed".
CSRF_TRUSTED_ORIGINS = [WEBDOMAIN]
```

Single-entry list keyed on `WEBDOMAIN` scales across dev / stage / prod without per-environment overrides.

---

## Step 8: Backend tests

Create one test file per concern, following the [CLAUDE.md naming convention](../CLAUDE.md):

| File | Coverage |
|---|---|
| `tests_login_pending_endpoint.py` | PENDING user login → 403; response body has `{message, status:"pending", email}`; no JWT |
| `tests_login_suspended_endpoint.py` | SUSPENDED user login → 403; body has `status:"suspended"`; no JWT |
| `tests_invite_binding.py` | Email-match → status flips to ACTIVE + bind; synthesized-email path → silent pending + warning; **shared email across two Kobo identities** → second arriver gets a synthesized email row |
| `tests_admin_lifecycle_actions.py` | Each admin action only fires from its source state; emails reach `mail.outbox`; superuser permission gate |
| `tests_status_aware_jwt_auth.py` | Existing JWT for SUSPENDED user → 401; ACTIVE user → 200; `is_active=False` alone → 401 |
| `tests_email_notifications.py` | Each of the 5 types routed through `queue_email` lands in `mail.outbox`; **body names the `kobo_username`** when set; failure path swallows exceptions |
| `tests_users_model.py` (extend) | Default status=`UserStatus.PENDING` (0); `fieldStr` mapping intact |
| `tests_login_endpoint.py` (update) | Happy path needs pre-created ACTIVE user; fresh-user login → 403 PENDING |

**Test infrastructure updates required** in existing test helpers:

- `v1_users/tests/mixins.py` — `get_auth_token` now pre-creates an ACTIVE user before calling the login endpoint (approval gate would 403 otherwise).
- `v1_odk/tests/mixins.py` — `create_kobo_user` sets `status=UserStatus.ACTIVE, is_active=True` on the test superuser.
- **New** `v1_init/tests/mixins.py` — `V1InitTestHelperMixin.create_admin_user()` + `login()`; the telegram-group tests previously reimplemented login inline.
- `tests_submissions_endpoint.py` — one inline-created user marked ACTIVE.

**Conf.SYNC flip in async tests**: `@override_settings(TEST_ENV=True)` runs too late to affect the `Q_CLUSTER["sync"] = bool(TEST_ENV)` that settles at settings-import time. Tests that exercise `queue_email` should flip `django_q.conf.Conf.SYNC = True` in `setUp()` and restore it in `tearDown()`.

Mailjet is bypassed in tests via Django's `locmem` email backend. Add to `settings.py`:

```python
if TEST_ENV:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
```

Example test stub for `tests_login_pending_endpoint.py`:

```python
from django.test import TestCase

from api.v1.v1_users.constants import UserStatus
from api.v1.v1_users.models import SystemUser


class LoginPendingEndpointTestCase(TestCase):
    def test_pending_user_cannot_login(self):
        # Pending user is created via silent-pending flow on first
        # Kobo verification. We simulate the post-bind state directly.
        SystemUser.objects.create(
            email="alice@example.com",
            name="Alice",
            kobo_username="alice",
            kobo_url="https://kf.kobotoolbox.org",
            status=UserStatus.PENDING,
            is_active=False,
        )
        # ... mock KoboClient.verify_credentials -> dict
        # ... POST /api/v1/auth/login
        # ... assert 403, body["status"] == "pending"
```

---

## Step 9: Settings wiring

**File:** `backend/african_bamboo_dashboard/settings.py`

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.v1.v1_users.auth.StatusAwareJWTAuthentication",
    ],
    # ... rest unchanged
}

Q_IS_SYNC = bool(TEST_ENV)

Q_CLUSTER = {
    "name": "african_bamboo",
    "workers": 2,
    "timeout": 60,
    "retry": 120,
    "orm": "default",
    "sync": Q_IS_SYNC,  # NEW: run tasks inline in tests
}

# Use locmem backend in tests so Mailjet is not called.
if TEST_ENV:
    EMAIL_BACKEND = (
        "django.core.mail.backends.locmem.EmailBackend"
    )

# CSRF trusted origins — Django admin form POSTs come from
# the frontend proxy host. Without this, Django's Origin
# check rejects the request with 403 "Origin checking failed".
CSRF_TRUSTED_ORIGINS = [WEBDOMAIN]
```

Important: `Q_CLUSTER["sync"]` is evaluated at settings-import time. When tests use `@override_settings(TEST_ENV=True)`, the `Q_CLUSTER["sync"]` value has already settled to `False` (because the `TEST_ENV` env var isn't set when `manage.py test` launches). Tests that need inline task execution must flip `django_q.conf.Conf.SYNC = True` themselves — see test-infrastructure notes in Step 8.

---

## Step 10: Frontend handoff (out of scope, document only)

The login page must surface the new 403 body's `message` field instead of a generic auth error. One-line change in the login submit handler — flagged for a follow-up frontend task; **no work in this PR**.

---

## Files Modified/Created

| Action | File |
|---|---|
| Existing | `backend/api/v1/v1_users/constants.py` (already in place — `UserStatus` integer constants) |
| Modify | `backend/api/v1/v1_users/models.py` (import `UserStatus` from `constants`; add fields) |
| Create | `backend/api/v1/v1_users/migrations/0002_user_access_management.py` |
| Create | `backend/api/v1/v1_users/auth.py` |
| Create | `backend/api/v1/v1_users/services/__init__.py` |
| Create | `backend/api/v1/v1_users/services/approval.py` |
| Modify | `backend/api/v1/v1_users/views.py` |
| Modify | `backend/api/v1/v1_users/serializers.py` |
| Modify | `backend/api/v1/v1_users/admin.py` |
| Modify | `backend/utils/email_helper.py` (fix broken import, add `send_email_by_user_id` + `queue_email`, extend `EmailTypes` to 5 entries) |
| Modify | `backend/african_bamboo_dashboard/templates/email/main.html` (render body + CTA) |
| Create | `backend/api/v1/v1_users/templates/admin/v1_users/invite_user.html` |
| Modify | `backend/african_bamboo_dashboard/settings.py` (auth class + Q_CLUSTER sync + locmem email + TEMPLATES DIR + **CSRF_TRUSTED_ORIGINS**) |
| Modify | `backend/african_bamboo_dashboard/urls.py` (mount `path("admin/", admin.site.urls)` — previously missing) |
| Modify | `frontend/next.config.mjs` (trailing-slash rule first, then `/admin/:path*` + `/static/:path*`) |
| Modify | `nginx/conf.d/default.conf` (add `location /admin` + `location /static`) |
| Create | `backend/api/v1/v1_users/tests/tests_login_pending_endpoint.py` |
| Create | `backend/api/v1/v1_users/tests/tests_login_suspended_endpoint.py` |
| Create | `backend/api/v1/v1_users/tests/tests_invite_binding.py` |
| Create | `backend/api/v1/v1_users/tests/tests_admin_lifecycle_actions.py` |
| Create | `backend/api/v1/v1_users/tests/tests_status_aware_jwt_auth.py` |
| Create | `backend/api/v1/v1_users/tests/tests_email_notifications.py` |
| Modify | `backend/api/v1/v1_users/tests/tests_users_model.py` |
| Modify | `backend/api/v1/v1_users/tests/tests_login_endpoint.py` (happy path now pre-creates ACTIVE user; `test_creates_system_user` → `test_new_user_row_created_but_pending`) |
| Modify | `backend/api/v1/v1_users/tests/mixins.py` (pre-create ACTIVE user before login) |
| Modify | `backend/api/v1/v1_odk/tests/mixins.py` (`create_kobo_user` sets ACTIVE + is_active) |
| Create | `backend/api/v1/v1_init/tests/mixins.py` (`V1InitTestHelperMixin`) |
| Modify | `backend/api/v1/v1_init/tests/tests_settings_telegram_endpoint.py` (use new mixin) |
| Modify | `backend/api/v1/v1_init/tests/tests_telegram_groups_endpoint.py` (use new mixin) |
| Modify | `backend/api/v1/v1_odk/tests/tests_submissions_endpoint.py` (one ad-hoc user marked ACTIVE) |

## Verification

1. `cd backend && black . && isort . && flake8` — linting must be clean (max line length 80).
2. `python manage.py makemigrations --check` — confirms no missing migrations.
3. `python manage.py migrate` — runs schema + data migration cleanly.
4. `python manage.py test api.v1.v1_users` — all new and existing tests green.
5. Hit `POST /api/v1/auth/login` in Swagger UI as:
   - an existing active user → 200 + JWT (regression check)
   - a brand-new Kobo user → 403 with `{message, status: "pending", email}`
   - a suspended user (rejected or deactivated) → 403 with `{message, status: "suspended", email}`
6. Confirm the `worker` container is running: `docker compose ps worker` should show it healthy. It executes `python manage.py qcluster` via [run_worker.sh](../backend/run_worker.sh) — no separate action needed.
7. Open `http://localhost:3000/admin/` (same origin as the frontend — not the bare backend port). Confirm the page styles load (proves the `/static/admin/*` proxy works). In Django admin:
   - log in as a `createsuperuser` account
   - invite `someone@example.com` → admin response is **instant**; email arrives shortly after via the worker
   - approve, deactivate, reactivate flows each send the right email and update `status_changed_at`
8. Inspect `/admin/django_q/` for task history; `/admin/django_q/failure/` for any worker failures.
9. Hold a JWT for an active user → deactivate them via admin → next API call returns 401.
