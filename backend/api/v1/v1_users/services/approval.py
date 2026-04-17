import enum
import logging
import secrets
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
    """Build a deterministic fallback email from the Kobo
    identity. Used when two Kobo accounts share the same real
    email — since SystemUser.email is UNIQUE, the later
    arriver needs a disambiguated address to store its row."""
    host = (kobo_url or "").split("//")[-1].split("/")[0]
    return f"{kobo_username}@{host}"


def create_invite(
    *,
    email: str,
    name: Optional[str],
    kobo_url: Optional[str],
    invited_by: SystemUser,
) -> SystemUser:
    """Create a PENDING row and enqueue the invitation email.

    Raises ValueError if a user with that email already exists
    (the model enforces unique email).
    """
    normalized = _normalize_email(email)
    if SystemUser.objects.filter(
        email__iexact=normalized
    ).exists():
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
    """Match an invite by email or fall back to silent PENDING.

    - Real Kobo email + matching PENDING invite (no kobo_username
      yet) -> bind and flip to ACTIVE, enqueue approved email.
    - Synthesized email -> never auto-bind; log warning and
      create a silent PENDING row.
    - No invite match -> create silent PENDING row.
    - Existing kobo_username + kobo_url row -> refresh password
      (and name when previously synthesized) and return the row
      as-is.
    """
    normalized = _normalize_email(email_from_kobo)
    existing = SystemUser.objects.filter(
        kobo_username=kobo_username, kobo_url=kobo_url
    ).first()
    if existing is not None:
        existing.kobo_password = encrypted_password
        if (
            name_from_kobo
            and existing.name == existing.email
        ):
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

    # Try the real email first. If another SystemUser already
    # owns it (distinct Kobo identities sharing an email, e.g.
    # `ab_admin` and `ab_enumerator` both using the same
    # address), fall back to the deterministic synthesized
    # form. If THAT is also taken (e.g. an invite row already
    # uses the literal `<kobo_username>@<host>` form), keep
    # trying short random-suffixed variants before giving up.
    # The earlier `(kobo_username, kobo_url)` lookup already
    # returned ALREADY_ACTIVE / SILENT_PENDING for matching
    # identities, so any IntegrityError here is necessarily
    # an email-UNIQUE collision — we don't mask other bugs.
    user = None
    for candidate in _email_candidates(normalized, kobo_username, kobo_url):
        create_kwargs["email"] = candidate
        try:
            with transaction.atomic():
                user = SystemUser.objects.create(**create_kwargs)
            if candidate != normalized:
                logger.warning(
                    "Email collision on silent-pending: "
                    "real email %s already used; stored as "
                    "%s for kobo identity %s@%s.",
                    normalized,
                    candidate,
                    kobo_username,
                    kobo_url,
                )
            break
        except IntegrityError:
            continue
    if user is None:
        raise IntegrityError(
            "Exhausted email candidates for kobo identity "
            f"{kobo_username}@{kobo_url}. "
            "SystemUser.email UNIQUE constraint is blocking "
            "every synthesized variant — inspect the table."
        )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user, BindOutcome.SILENT_PENDING


def _email_candidates(
    real_email: str, kobo_username: str, kobo_url: str
):
    """Yield the email addresses to try for a silent-PENDING
    row, in order: the real email, then the deterministic
    synthesized form, then a small number of random-suffixed
    variants of the synthesized form.

    Random suffix uses 3 bytes (6 hex chars, ~16M space) —
    with 5 attempts the probability of total collision is
    cosmologically small.
    """
    yield real_email
    synth = _synthesized_email(kobo_username, kobo_url)
    yield synth
    local, _, host = synth.partition("@")
    for _ in range(5):
        yield f"{local}+{secrets.token_hex(3)}@{host}"


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
