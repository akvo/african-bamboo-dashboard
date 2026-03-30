import logging
import re
import time
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django_q.tasks import async_task
from PIL import Image, ImageOps

from api.v1.v1_init.helpers import get_telegram_config
from api.v1.v1_jobs.constants import JobStatus, JobTypes
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_odk.constants import (ATTACHMENTS_FOLDER, PREFIX_FARM_ID,
                                     PREFIX_SUBM_ID, ApprovalStatusTypes,
                                     SyncStatus)
from api.v1.v1_odk.export import (cleanup_old_exports, generate_geojson,
                                  generate_shapefile, generate_xlsx)
from api.v1.v1_odk.models import FormMetadata, Plot, RejectionAudit, Submission
from api.v1.v1_odk.serializers import build_option_lookup, resolve_value
from api.v1.v1_odk.utils.farmer_sync import sync_farmers_for_form
from utils.encryption import decrypt
from utils.kobo_client import KoboClient, KoboUnauthorizedError
from utils.telegram_client import TelegramClient, TelegramSendError

logger = logging.getLogger(__name__)


STATUS_MAP = {
    "approved": ApprovalStatusTypes.APPROVED,
    "rejected": ApprovalStatusTypes.REJECTED,
}


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

        filename = f"plots_{form_id}_{job_id}"

        if job.type == JobTypes.export_xlsx:
            # XLSX: all plots, run farmer sync
            sync_farmers_for_form(form)
            ts = int(time.time())
            safe_name = re.sub(r"[^\w\-.]", "_", form.name)[:80].strip("_") \
                or "export"
            xlsx_filename = f"{safe_name}_{ts}"
            file_path, count = generate_xlsx(qs, form, xlsx_filename)
        else:
            # SHP/GeoJSON require geometry
            qs = qs.filter(polygon_wkt__isnull=False).exclude(polygon_wkt="")

            if job.type == (JobTypes.export_geojson):
                file_path, count = generate_geojson(qs, form, filename)
            else:
                file_path, count = generate_shapefile(qs, form, filename)

        job.status = JobStatus.done
        job.info = {
            **info,
            "file_path": file_path,
            "record_count": count,
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
    except Exception:
        logger.exception(
            "Failed to sync validation status " "for kobo_ids=%s on asset %s",
            kobo_ids,
            asset_uid,
        )


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
                "Telegram disabled, skipping " "notification for audit %s",
                audit_id,
            )
    else:
        audit.sync_status = SyncStatus.FAILED
        audit.save(update_fields=["sync_status"])
        logger.warning(
            "Kobo sync failed for audit %s",
            audit_id,
        )


def _escape_markdown(text):
    """Escape Telegram MarkdownV1 special chars."""
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


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


def send_telegram_rejection_notification(audit_id):
    """Send Telegram notification for a
    rejected plot submission.

    Called asynchronously after successful
    Kobo validation sync.
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
            "Telegram disabled, skipping " "notification for audit %s",
            audit_id,
        )
        return

    bot_token = tg_config["bot_token"]
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, " "skipping notification")
        return

    plot = audit.plot
    submission = audit.submission
    validator_name = audit.validator.name if audit.validator else "Unknown"
    category_display = audit.get_reason_category_display()
    reason = category_display
    if audit.reason_text:
        reason = f"{category_display}: " f"{audit.reason_text}"

    rejected_at_str = (
        audit.rejected_at.strftime("%Y-%m-%d %H:%M UTC")
        if audit.rejected_at else "N/A"
    )
    plot_location = _resolve_plot_location(submission, plot)

    esc = _escape_markdown
    submission_id = "N/A"
    if submission.kobo_id:
        submission_id = f"{PREFIX_SUBM_ID}{submission.kobo_id}"
    farm_id = "N/A"
    if plot.farmer and plot.farmer.uid:
        farm_id = f"{PREFIX_FARM_ID}{plot.farmer.uid}"
    message = (
        f"*Plot Rejected*\n\n"
        f"*Submission ID:* {esc(submission_id)}\n"
        f"*Farm ID:* {esc(farm_id)}\n"
        f"*Location:* {esc(plot_location)}\n"
        f"*Reason:* {esc(reason)}\n"
        f"*Validated by:* "
        f"{esc(validator_name)}\n"
        f"*Time:* {esc(rejected_at_str)}\n\n"
        f"_Please review and recollect "
        f"if needed._"
    )

    client = TelegramClient(bot_token)
    chat_ids = []
    message_ids = []
    groups = [
        (
            "supervisor",
            tg_config["supervisor_group_id"],
        ),
        (
            "enumerator",
            tg_config["enumerator_group_id"],
        ),
    ]
    seen = set()

    for label, chat_id in groups:
        if not chat_id or chat_id in seen:
            logger.info(
                "No %s group ID configured, " "skipping",
                label,
            )
            continue
        seen.add(chat_id)
        try:
            msg_id = client.send_message(chat_id, message)
            chat_ids.append(chat_id)
            message_ids.append(str(msg_id))
            logger.info(
                "Sent Telegram notification to " "%s group %s for audit %s",
                label,
                chat_id,
                audit_id,
            )
        except TelegramSendError:
            logger.exception(
                "Failed to send Telegram "
                "notification to %s group %s "
                "for audit %s",
                label,
                chat_id,
                audit_id,
            )

    if chat_ids:
        audit.telegram_sent_at = timezone.now()
        audit.telegram_chat_ids = chat_ids
        audit.telegram_message_id = ",".join(message_ids)
        audit.save(
            update_fields=[
                "telegram_sent_at",
                "telegram_chat_ids",
                "telegram_message_id",
            ]
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
