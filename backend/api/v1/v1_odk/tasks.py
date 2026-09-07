import logging
import os
import re
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape
from django_q.tasks import async_task
from PIL import Image, ImageOps

from api.v1.v1_init.helpers import (get_telegram_config,
                                    migrate_telegram_group_id)
from api.v1.v1_jobs.constants import JobStatus, JobTypes
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_odk.constants import (ATTACHMENTS_FOLDER, PREFIX_FARM_ID,
                                     PREFIX_SUBM_ID, ApprovalStatusTypes,
                                     SyncStatus)
from api.v1.v1_odk.export import (build_export_filename,
                                  cleanup_old_exports, generate_geojson,
                                  generate_shapefile, generate_xlsx)
from api.v1.v1_odk.models import FormMetadata, Plot, RejectionAudit, Submission
from api.v1.v1_odk.serializers import build_option_lookup, resolve_value
from api.v1.v1_odk.utils.farmer_sync import sync_farmers_for_form
from api.v1.v1_odk.utils.plot_id import get_plot_uid
from utils.encryption import decrypt
from utils.kobo_client import KoboClient, KoboUnauthorizedError
from utils.telegram_client import TelegramClient, TelegramSendError

logger = logging.getLogger(__name__)


STATUS_MAP = {
    "approved": ApprovalStatusTypes.APPROVED,
    "rejected": ApprovalStatusTypes.REJECTED,
}


def _set_stage(job, info, stage):
    """Record which phase an export is in.

    The client already polls the job endpoint, so
    this is what distinguishes a slow export from a
    stuck one without adding another endpoint.
    """
    info = {**info, "stage": stage}
    job.info = info
    job.save(update_fields=["info"])
    return info


def generate_export_file(job_id):
    """Generate export file (Shapefile or GeoJSON)
    for the given job.

    Called asynchronously via Django-Q2 worker.
    """
    try:
        job = Jobs.objects.get(pk=job_id)
    except Jobs.DoesNotExist:
        logger.error("Job %s not found", job_id)
        return

    job.status = JobStatus.on_progress
    job.save()

    try:
        cleanup_old_exports()

        info = job.info or {}
        form_id = info.get("form_id")
        filters = info.get("filters", {})

        form = FormMetadata.objects.get(asset_uid=form_id)

        qs = Plot.objects.filter(form=form)

        # Apply status filter
        status_param = filters.get("status")
        if status_param:
            if status_param == "flagged":
                qs = qs.filter(flagged_for_review=True)
            elif status_param == "pending":
                qs = qs.filter(
                    submission__approval_status__isnull=True,  # noqa: E501
                )
            elif status_param in STATUS_MAP:
                qs = qs.filter(
                    submission__approval_status=(STATUS_MAP[status_param])
                )

        # Apply search filter
        search = filters.get("search")
        if search:
            qs = qs.filter(plot_name__icontains=search)

        # Region / sub-region filters
        region = filters.get("region")
        if region:
            qs = qs.filter(region=region)
        sub_region = filters.get("sub_region")
        if sub_region:
            qs = qs.filter(sub_region=sub_region)

        # Date range filters
        start_date = filters.get("start_date")
        if start_date:
            qs = qs.filter(submission__submission_time__gte=(int(start_date)))
        end_date = filters.get("end_date")
        if end_date:
            qs = qs.filter(submission__submission_time__lte=(int(end_date)))

        # Dynamic raw_data filters
        dynamic = filters.get("dynamic_filters", {})
        allowed = form.filter_fields or []
        for field, val in dynamic.items():
            if field in allowed:
                qs = qs.filter(**{"submission__" "raw_data__" f"{field}": val})

        filename = build_export_filename(form, job_id)

        if job.type == JobTypes.export_xlsx:
            # XLSX carries a Farmer sheet, so refresh
            # the Farmer rows first. A sync failure
            # should leave the export with stale
            # farmer data, not kill it outright.
            info = _set_stage(job, info, "syncing_farmers")
            try:
                sync_farmers_for_form(form)
            except Exception as e:
                logger.exception(
                    "Farmer sync failed for form %s "
                    "during export job %s — "
                    "continuing with existing "
                    "farmer data",
                    form.asset_uid,
                    job_id,
                )
                info["farmer_sync_error"] = str(e)

            info = _set_stage(job, info, "building_file")
            file_path, count = generate_xlsx(qs, form, filename)
        else:
            # SHP/GeoJSON require geometry
            qs = qs.filter(polygon_wkt__isnull=False).exclude(polygon_wkt="")

            info = _set_stage(job, info, "building_file")
            if job.type == (JobTypes.export_geojson):
                file_path, count = generate_geojson(qs, form, filename)
            else:
                file_path, count = generate_shapefile(qs, form, filename)

        job.status = JobStatus.done
        job.info = {
            **info,
            "file_path": file_path,
            "download_name": os.path.basename(file_path),
            "record_count": count,
            "stage": "done",
        }
        job.available = timezone.now()
        job.save()

        logger.info(
            "Export job %s completed: " "%d records, file=%s",
            job_id,
            count,
            file_path,
        )
    except Exception as e:
        logger.exception("Export job %s failed", job_id)
        job.status = JobStatus.failed
        job.result = str(e)
        job.save()


def _short_body(response):
    """One-line, length-capped response body.

    Kobo answers a missing asset with a full HTML
    page; dumping it raw buries the useful signal.
    """
    if response is None:
        return "n/a"
    text = " ".join(
        str(getattr(response, "text", "")).split()
    )
    return text[:200] or "n/a"


def sync_kobo_validation_status(
    kobo_url,
    kobo_username,
    kobo_password_enc,
    asset_uid,
    kobo_ids,
    approval_status,
    **kwargs,
):
    """Sync a local approval decision back to
    KoboToolbox as a validation status update.

    All arguments are primitives so the task is
    safe to serialise via the Django Q ORM broker.
    """
    status_uid = ApprovalStatusTypes.KoboStatusMap.get(approval_status)
    if not status_uid:
        logger.warning(
            "No Kobo status mapping for " "approval_status=%s — skipping sync",
            approval_status,
        )
        return

    try:
        password = decrypt(kobo_password_enc)
        client = KoboClient(kobo_url, kobo_username, password)
        client.update_validation_statuses(asset_uid, kobo_ids, status_uid)
        logger.info(
            "Synced validation status %s for " "kobo_ids=%s on asset %s",
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
        # Re-raise so django_q records the task as
        # failed. on_kobo_sync_complete gates the
        # Telegram notification on task.success, so
        # swallowing here would notify an enumerator
        # about an update that never reached Kobo.
        raise
    except Exception as e:
        logger.exception(
            "Failed to sync validation status for "
            "kobo_ids=%s on asset %s (status=%s, "
            "body=%s). The form may have been "
            "deleted or renamed in KoboToolbox.",
            kobo_ids,
            asset_uid,
            getattr(
                getattr(e, "response", None),
                "status_code",
                "n/a",
            ),
            _short_body(getattr(e, "response", None)),
        )
        raise


def sync_kobo_submission_geometry(
    kobo_url,
    kobo_username,
    kobo_password_enc,
    asset_uid,
    kobo_id,
    polygon_field_name,
    odk_geoshape_str,
):
    """Sync edited polygon geometry back to
    KoboToolbox as a submission data update.

    All arguments are primitives so the task is
    safe to serialise via the Django Q ORM broker.
    """
    try:
        password = decrypt(kobo_password_enc)
        client = KoboClient(kobo_url, kobo_username, password)
        client.update_submission_data(
            asset_uid,
            kobo_id,
            {polygon_field_name: odk_geoshape_str},
        )
        logger.info(
            "Synced geometry for kobo_id=%s " "on asset %s",
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
            "Failed to sync geometry " "for kobo_id=%s on asset %s",
            kobo_id,
            asset_uid,
        )


def sync_kobo_submission_data(
    kobo_url,
    kobo_username,
    kobo_password_enc,
    asset_uid,
    kobo_id,
    data,
):
    """Sync edited field data back to
    KoboToolbox via bulk update.

    All arguments are primitives/dicts so the
    task is safe to serialise via Django Q broker.
    """
    try:
        password = decrypt(kobo_password_enc)
        client = KoboClient(
            kobo_url, kobo_username, password
        )
        client.update_submission_data(
            asset_uid, kobo_id, data
        )
        logger.info(
            "Synced field data for kobo_id=%s "
            "on asset %s: %s",
            kobo_id,
            asset_uid,
            list(data.keys()),
        )
    except KoboUnauthorizedError:
        logger.error(
            "Kobo credentials expired for "
            "user %s — cannot sync field data "
            "for kobo_id=%s on asset %s",
            kobo_username,
            kobo_id,
            asset_uid,
        )
    except Exception:
        logger.exception(
            "Failed to sync field data "
            "for kobo_id=%s on asset %s",
            kobo_id,
            asset_uid,
        )


def on_kobo_sync_complete(task):
    """Django-Q2 hook called after
    sync_kobo_validation_status completes.

    Updates RejectionAudit sync status and
    queues Telegram notification on success.
    """
    audit_id = task.kwargs.get("audit_id")
    if not audit_id:
        logger.warning("on_kobo_sync_complete called " "without audit_id")
        return

    try:
        audit = RejectionAudit.objects.get(pk=audit_id)
    except RejectionAudit.DoesNotExist:
        logger.error(
            "RejectionAudit %s not found",
            audit_id,
        )
        return

    if task.success:
        audit.sync_status = SyncStatus.SYNCED
        audit.synced_at = timezone.now()
        audit.save(
            update_fields=[
                "sync_status",
                "synced_at",
            ]
        )
        tg_config = get_telegram_config()
        if tg_config["enabled"]:
            async_task(
                "api.v1.v1_odk.tasks"
                ".send_telegram_rejection" "_notification",
                audit_id,
            )
        else:
            logger.info(
                "Telegram disabled, skipping "
                "notification for audit %s",
                audit_id,
            )
    else:
        audit.sync_status = SyncStatus.FAILED
        audit.save(update_fields=["sync_status"])
        logger.warning(
            "Kobo sync FAILED for audit %s — "
            "suppressing the Telegram rejection "
            "notification. The enumerator is not "
            "told, because the rejection never "
            "reached KoboToolbox. See the "
            "sync_kobo_validation_status traceback "
            "above for the cause.",
            audit_id,
        )


def _telegram_targets(tg_config):
    """Chat ids to notify, de-duplicated, in order.

    Both group ids routinely point at the same chat;
    sending twice would double-post.
    """
    targets = []
    for key in (
        "supervisor_group_id",
        "enumerator_group_id",
    ):
        chat_id = tg_config.get(key)
        if chat_id and chat_id not in targets:
            targets.append(chat_id)
    return targets


def _resolve_field_spec(raw_data, field_spec, option_map, type_map):
    """Resolve a comma-separated field spec to
    human-readable labels using option_map."""
    fields = [f.strip() for f in field_spec.split(",") if f.strip()]
    parts = []
    for field_name in fields:
        raw_val = raw_data.get(field_name)
        if raw_val is None:
            continue
        opts = option_map.get(field_name)
        if opts:
            resolved = resolve_value(
                raw_val,
                opts,
                type_map.get(field_name),
            )
        else:
            resolved = raw_val
        val = str(resolved).strip()
        if val:
            parts.append(val)
    return " - ".join(parts) if parts else None


def _resolve_plot_location(submission, plot):
    """Resolve plot location to human-readable
    labels using the form's option lookup.

    Falls back to plot.region / plot.sub_region
    when raw_data resolution yields nothing."""
    form = submission.form
    raw_data = submission.raw_data or {}
    option_map, type_map = build_option_lookup(form)

    region_spec = form.region_field or "region"
    sub_region_spec = form.sub_region_field or "sub_region"

    region = _resolve_field_spec(raw_data, region_spec, option_map, type_map)
    sub_region = _resolve_field_spec(
        raw_data,
        sub_region_spec,
        option_map,
        type_map,
    )

    # Fall back to stored plot values
    if not region:
        region = plot.region or None
    else:
        region = re.sub(r"^not in list\s*-\s*", "", region)
    if not sub_region:
        sub_region = plot.sub_region or None
    else:
        sub_region = re.sub(r"^not in list\s*-\s*", "", sub_region)

    if region and sub_region:
        return f"{region} - {sub_region}"
    return region or sub_region or "Unknown Location"


def _deliver_to_chat(client, chat_id, message, audit):
    """Send to one chat, following a supergroup move.

    Returns (chat_id_used, message_id). Raises
    TelegramSendError -- including for transport faults,
    which TelegramClient now normalises -- so the caller
    records the failure and lets the sweep retry.

    There is deliberately no plain-text retry here. A
    blind resend is wrong for every failure mode it can
    see: for 429 it lengthens Telegram's progressive
    flood-wait, for 403 it is a second guaranteed
    refusal, and for a timeout that fired *after*
    delivery it double-posts.
    """
    try:
        return chat_id, client.send_message(
            chat_id, message
        )
    except TelegramSendError as e:
        if not e.migrate_to_chat_id:
            raise
        # The group became a supergroup and Telegram
        # issued a new id. Persist it, or every future
        # send fails permanently.
        new_chat_id = str(e.migrate_to_chat_id)
        logger.warning(
            "Chat %s migrated to supergroup %s — "
            "persisting the new id and retrying "
            "(audit %s)",
            chat_id,
            new_chat_id,
            audit.pk,
        )
        migrate_telegram_group_id(
            chat_id, new_chat_id
        )
        return new_chat_id, client.send_message(
            new_chat_id, message
        )


def _build_rejection_message(audit):
    """Render the notification body as Telegram HTML.

    HTML needs exactly three characters escaped and
    django.utils.html.escape covers all three -- unlike
    legacy Markdown, whose incomplete escape set used to
    lose messages containing "]" or "(".
    """
    plot = audit.plot
    submission = audit.submission
    validator_name = (
        audit.validator.name
        if audit.validator
        else "Unknown"
    )
    category_display = (
        audit.get_reason_category_display()
    )
    reason = category_display
    if audit.reason_text:
        reason = (
            f"{category_display}: "
            f"{audit.reason_text}"
        )

    rejected_at_str = (
        audit.rejected_at.strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        if audit.rejected_at
        else "N/A"
    )
    location = _resolve_plot_location(
        submission, plot
    )

    plot_id = get_plot_uid(submission) or "N/A"
    submission_id = "N/A"
    if submission.kobo_id:
        submission_id = (
            f"{PREFIX_SUBM_ID}{submission.kobo_id}"
        )
    farm_id = "N/A"
    if plot.farmer and plot.farmer.uid:
        farm_id = (
            f"{PREFIX_FARM_ID}{plot.farmer.uid}"
        )

    return (
        f"<b>Plot Rejected</b>\n\n"
        f"<b>Plot ID:</b> {escape(plot_id)}\n"
        f"<b>Submission ID:</b> "
        f"{escape(submission_id)}\n"
        f"<b>Farm ID:</b> {escape(farm_id)}\n"
        f"<b>Location:</b> {escape(location)}\n"
        f"<b>Reason:</b> {escape(reason)}\n"
        f"<b>Validated by:</b> "
        f"{escape(validator_name)}\n"
        f"<b>Time:</b> "
        f"{escape(rejected_at_str)}\n\n"
        f"<i>Please review and recollect "
        f"if needed.</i>"
    )


def send_telegram_rejection_notification(audit_id):
    """Send Telegram notification for a
    rejected plot submission.

    Idempotent: telegram_chat_ids is the delivery
    ledger, so a chat already in it is never sent to
    again. That is what makes the retry sweep and the
    manual resend safe.

    Never raises. A failed attempt is recorded state,
    not an exception -- the sweep owns recovery, and an
    exception here would only be swallowed by
    Q_CLUSTER's max_attempts=1.
    """
    try:
        audit = RejectionAudit.objects.select_related(
            "plot",
            "submission",
            "submission__form",
            "validator",
        ).get(pk=audit_id)
    except RejectionAudit.DoesNotExist:
        logger.error(
            "RejectionAudit %s not found",
            audit_id,
        )
        return

    tg_config = get_telegram_config()
    if not tg_config["enabled"]:
        logger.info(
            "Telegram disabled, skipping "
            "notification for audit %s",
            audit_id,
        )
        return

    bot_token = tg_config["bot_token"]
    if not bot_token:
        logger.warning(
            "No Telegram bot token configured "
            "(neither TELEGRAM_BOT_TOKEN nor the "
            "'telegram' SystemSetting) — skipping "
            "notification for audit %s",
            audit_id,
        )
        return

    targets = _telegram_targets(tg_config)
    if not targets:
        logger.warning(
            "No Telegram group ID configured — no "
            "notification sent for audit %s",
            audit_id,
        )
        return

    delivered = list(audit.telegram_chat_ids or [])
    outstanding = [
        c for c in targets if c not in delivered
    ]
    if not outstanding:
        logger.info(
            "Audit %s already delivered to every "
            "configured group — nothing to send",
            audit_id,
        )
        return

    message_ids = [
        m
        for m in (
            audit.telegram_message_id or ""
        ).split(",")
        if m
    ]

    audit.telegram_attempts += 1
    audit.telegram_last_attempt_at = timezone.now()
    audit.save(
        update_fields=[
            "telegram_attempts",
            "telegram_last_attempt_at",
        ]
    )

    client = TelegramClient(bot_token)
    message = _build_rejection_message(audit)
    last_error = None
    retry_after = None

    for chat_id in outstanding:
        try:
            used_id, msg_id = _deliver_to_chat(
                client, chat_id, message, audit
            )
        except TelegramSendError as e:
            last_error = f"{chat_id}: {e}"
            if e.retry_after:
                # Telegram lengthens the flood-wait every
                # time it is ignored, so honour the longest
                # value it gave us this round.
                retry_after = max(
                    retry_after or 0, e.retry_after
                )
            logger.warning(
                "Telegram send failed for group %s "
                "(audit %s): %s — will retry on the "
                "next sweep%s",
                chat_id,
                audit_id,
                e,
                (
                    f" (not before {e.retry_after}s, per "
                    f"Telegram)"
                    if e.retry_after
                    else ""
                ),
            )
            continue

        # Saved per chat, not once at the end: a crash
        # between two sends must not lose the record of
        # the first, or the retry would double-post.
        delivered.append(used_id)
        message_ids.append(str(msg_id))
        audit.telegram_chat_ids = delivered
        audit.telegram_message_id = ",".join(
            message_ids
        )
        audit.save(
            update_fields=[
                "telegram_chat_ids",
                "telegram_message_id",
            ]
        )
        logger.info(
            "Sent Telegram notification to group %s "
            "for audit %s",
            used_id,
            audit_id,
        )

    audit.telegram_last_error = last_error
    audit.telegram_next_attempt_at = (
        timezone.now() + timedelta(seconds=retry_after)
        if retry_after
        else None
    )
    if all(c in delivered for c in targets):
        audit.telegram_sent_at = timezone.now()
    audit.save(
        update_fields=[
            "telegram_last_error",
            "telegram_next_attempt_at",
            "telegram_sent_at",
        ]
    )


def retry_pending_telegram_notifications():
    """Re-enqueue notifications that never fully
    delivered.

    This is the only retry path. Q_CLUSTER pins
    max_attempts=1, so a task that fails is never
    redelivered; and an in-process retry would not
    survive a worker restart. A scheduled sweep does
    both.
    """
    # The kill switch is read here, not at schedule
    # registration: "enabled" lives in SystemSetting
    # and can be toggled at any time, so a schedule
    # registered while off must still work once it is
    # turned on -- and vice versa.
    tg_config = get_telegram_config()
    if (
        not tg_config["enabled"]
        or not tg_config["bot_token"]
    ):
        logger.debug(
            "Telegram disabled or unconfigured — "
            "skipping retry sweep"
        )
        return

    cutoff = timezone.now() - timedelta(
        minutes=settings.TELEGRAM_RETRY_COOLDOWN_MINUTES
    )

    # sync_status=SYNCED is essential: it preserves the
    # rule that a rejection which never reached Kobo
    # must not notify the enumerator.
    now = timezone.now()
    stuck = (
        RejectionAudit.objects.filter(
            sync_status=SyncStatus.SYNCED,
            telegram_sent_at__isnull=True,
            telegram_attempts__lt=(
                settings.TELEGRAM_MAX_ATTEMPTS
            ),
        )
        .filter(
            Q(telegram_last_attempt_at__isnull=True)
            | Q(telegram_last_attempt_at__lt=cutoff)
        )
        # Telegram's own backoff wins when it is longer than
        # our cooldown. Retrying inside a flood-wait just
        # extends it, so both conditions must hold.
        .filter(
            Q(telegram_next_attempt_at__isnull=True)
            | Q(telegram_next_attempt_at__lte=now)
        )
    )
    for audit in stuck:
        logger.info(
            "Retrying Telegram notification for "
            "audit %s (attempt %s of %s)",
            audit.pk,
            audit.telegram_attempts + 1,
            settings.TELEGRAM_MAX_ATTEMPTS,
        )
        async_task(
            "api.v1.v1_odk.tasks"
            ".send_telegram_rejection_notification",
            audit.pk,
        )

    # django_q's call_hook swallows every exception the
    # hook raises, so a failed on_kobo_sync_complete
    # leaves sync_status at "pending" forever. These
    # must NOT be notified -- nothing recorded whether
    # Kobo accepted the update -- but they must not
    # stay invisible either.
    stale_pending = RejectionAudit.objects.filter(
        sync_status=SyncStatus.PENDING,
        rejected_at__lt=cutoff,
    ).count()
    if stale_pending:
        logger.warning(
            "%s rejection audit(s) stuck at "
            "sync_status=pending — the "
            "on_kobo_sync_complete hook probably "
            "failed; see the django_q ERROR log. No "
            "notification is sent for these.",
            stale_pending,
        )


def download_submission_attachments(
    kobo_url,
    kobo_username,
    kobo_password_enc,
    submission_uuid,
):
    """Download image attachments from Kobo
    and store them locally.

    Files are saved to:
    storage/attachments/{submission_uuid}/
    {att_uid}.{ext}
    """
    try:
        sub = Submission.objects.get(uuid=submission_uuid)
    except Submission.DoesNotExist:
        logger.error(
            "Submission %s not found",
            submission_uuid,
        )
        return

    raw = sub.raw_data or {}
    attachments = raw.get("_attachments", [])
    if not attachments:
        return

    image_atts = [
        a
        for a in attachments
        if a.get("mimetype", "").startswith("image/")
        and a.get("download_medium_url")
        and a.get("uid")
    ]
    if not image_atts:
        return

    password = decrypt(kobo_password_enc)
    client = KoboClient(kobo_url, kobo_username, password)

    dest_dir = (
        Path(settings.STORAGE_PATH) / ATTACHMENTS_FOLDER / str(submission_uuid)
    )
    dest_dir.mkdir(parents=True, exist_ok=True)

    for att in image_atts:
        att_uid = att["uid"]
        basename = att.get("media_file_basename", "img.jpg")
        ext = basename.rsplit(".", 1)[-1] or "jpg"
        dest_file = dest_dir / f"{att_uid}.{ext}"
        if dest_file.exists():
            continue

        urls = [
            att.get("download_url"),
            att.get("download_large_url"),
            att.get("download_medium_url"),
            att.get("download_small_url"),
        ]
        urls = [u for u in urls if u]

        downloaded = False
        for url in urls:
            try:
                resp = client.session.get(
                    url,
                    timeout=client.timeout,
                )
                if resp.status_code == 401:
                    raise KoboUnauthorizedError("Kobo credentials expired")
                resp.raise_for_status()
                img = Image.open(BytesIO(resp.content))
                fmt = img.format
                img = ImageOps.exif_transpose(img)
                img.save(dest_file, format=fmt)
                logger.info(
                    "Downloaded attachment %s " "for submission %s from %s",
                    att_uid,
                    submission_uuid,
                    url,
                )
                downloaded = True
                break
            except KoboUnauthorizedError:
                logger.error(
                    "Kobo credentials expired "
                    "for %s — aborting "
                    "attachment downloads "
                    "for submission %s",
                    kobo_username,
                    submission_uuid,
                )
                return
            except Exception:
                logger.warning(
                    "Failed %s for " "attachment %s, " "trying next URL",
                    url,
                    att_uid,
                )
        if not downloaded:
            logger.error(
                "All URLs failed for " "attachment %s " "submission %s",
                att_uid,
                submission_uuid,
            )
