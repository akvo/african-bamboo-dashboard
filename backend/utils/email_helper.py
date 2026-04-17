import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django_q.tasks import async_task

logger = logging.getLogger(__name__)


class EmailTypes:
    account_invited = "account_invited"
    account_approved = "account_approved"
    account_rejected = "account_rejected"
    account_deactivated = "account_deactivated"
    account_reactivated = "account_reactivated"

    FieldStr = {
        account_invited: "account_invited",
        account_approved: "account_approved",
        account_rejected: "account_rejected",
        account_deactivated: "account_deactivated",
        account_reactivated: "account_reactivated",
    }


def _account_label(context: dict) -> str:
    """Build a 'for account <kobo_username>' suffix so users
    who own multiple Kobo accounts know which one is affected.
    When no kobo_username is set (pure invite-only row), this
    returns an empty string."""
    username = context.get("kobo_username")
    if not username:
        return ""
    return f" for the KoboToolbox account `{username}`"


def email_context(context: dict, type: str):
    account = _account_label(context)
    if type == EmailTypes.account_invited:
        inviter = context.get("inviter_name") or "An admin"
        context["subject"] = (
            "You've been invited to African Bamboo Dashboard"
        )
        context["body"] = (
            f"{inviter} has invited you to access the African "
            "Bamboo Dashboard. Log in with your KoboToolbox "
            "credentials to complete onboarding."
        )
        context["cta_text"] = "Log in to the dashboard"
        context["cta_url"] = f"{settings.WEBDOMAIN}/login"
    elif type == EmailTypes.account_approved:
        context["subject"] = (
            "Your African Bamboo Dashboard access has been "
            "approved"
        )
        context["body"] = (
            f"Your access to African Bamboo Dashboard has "
            f"been approved{account}. You can now log in and "
            "start using it."
        )
        context["cta_text"] = "Log in to the dashboard"
        context["cta_url"] = f"{settings.WEBDOMAIN}/login"
    elif type == EmailTypes.account_rejected:
        context["subject"] = (
            "African Bamboo Dashboard access denied"
        )
        context["body"] = (
            f"Your access request to African Bamboo "
            f"Dashboard has been denied{account}. Contact "
            "the administrator if you believe this is a "
            "mistake."
        )
        context["cta_text"] = None
        context["cta_url"] = None
    elif type == EmailTypes.account_deactivated:
        context["subject"] = (
            "Your African Bamboo Dashboard access has been "
            "revoked"
        )
        context["body"] = (
            f"Your access to African Bamboo Dashboard has "
            f"been revoked{account}. Contact the "
            "administrator if you need it restored."
        )
        context["cta_text"] = None
        context["cta_url"] = None
    elif type == EmailTypes.account_reactivated:
        context["subject"] = (
            "Your African Bamboo Dashboard access has been "
            "restored"
        )
        context["body"] = (
            f"Your access to African Bamboo Dashboard has "
            f"been restored{account}. You can log in with "
            "your KoboToolbox credentials again."
        )
        context["cta_text"] = "Log in to the dashboard"
        context["cta_url"] = f"{settings.WEBDOMAIN}/login"
    return context


def send_email(
    context: dict,
    type: str,
    path=None,
    content_type=None,
    send=True,
):
    context = email_context(context=context, type=type)
    try:

        email_html_message = render_to_string(
            "email/main.html", context
        )
        msg = EmailMultiAlternatives(
            "EDM - {0}".format(context.get("subject")),
            "Email plain text",
            settings.EMAIL_FROM,
            context.get("send_to"),
        )
        msg.attach_alternative(email_html_message, "text/html")
        if path:
            # Django reads the file in binary mode internally,
            # closes the handle, and infers the mimetype from
            # the filename when content_type is None.
            msg.attach_file(path, mimetype=content_type)
        if send:
            msg.send()
        if not send:
            return email_html_message
    except Exception as ex:
        logger.warning("Failed to send email: %s", ex)


def send_email_by_user_id(
    user_id: int,
    type: str,
    extra_context: dict = None,
) -> None:
    """Task entry-point for async email dispatch.

    Resolves the user lazily so that users deleted between
    enqueue and execution are skipped with a warning.
    """
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
    """Enqueue a transactional email on the django_q worker.

    Returns instantly; Mailjet is contacted asynchronously.
    Arguments must be pickle-safe: pass user.id (int), never
    the user instance.
    """
    async_task(
        "utils.email_helper.send_email_by_user_id",
        user.id,
        type,
        extra_context or {},
    )
