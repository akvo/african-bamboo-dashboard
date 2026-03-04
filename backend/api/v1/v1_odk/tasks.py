import logging

from django.utils import timezone

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.export import (
    cleanup_old_exports,
    generate_geojson,
    generate_shapefile,
)
from api.v1.v1_jobs.constants import (
    JobStatus,
    JobTypes,
)
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_odk.models import Plot
from api.v1.v1_odk.models import (
    FormMetadata,
)
from utils.encryption import decrypt
from utils.kobo_client import KoboClient

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

        form = FormMetadata.objects.get(
            asset_uid=form_id
        )

        qs = Plot.objects.filter(form=form)

        # Apply status filter
        status_param = filters.get("status")
        if status_param:
            if status_param == "flagged":
                qs = qs.filter(
                    flagged_for_review=True
                )
            elif status_param == "pending":
                qs = qs.filter(
                    submission__approval_status__isnull=True,  # noqa: E501
                )
            elif status_param in STATUS_MAP:
                qs = qs.filter(
                    submission__approval_status=(
                        STATUS_MAP[status_param]
                    )
                )

        # Apply search filter
        search = filters.get("search")
        if search:
            qs = qs.filter(
                plot_name__icontains=search
            )

        # Exclude plots without geometry
        qs = qs.filter(
            polygon_wkt__isnull=False
        ).exclude(polygon_wkt="")

        filename = f"plots_{form_id}_{job_id}"

        if job.type == JobTypes.export_geojson:
            file_path, count = generate_geojson(
                qs, form, filename
            )
        else:
            file_path, count = (
                generate_shapefile(
                    qs, form, filename
                )
            )

        job.status = JobStatus.done
        job.info = {
            **info,
            "file_path": file_path,
            "record_count": count,
        }
        job.available = timezone.now()
        job.save()

        logger.info(
            "Export job %s completed: "
            "%d records, file=%s",
            job_id,
            count,
            file_path,
        )
    except Exception as e:
        logger.exception(
            "Export job %s failed", job_id
        )
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
):
    """Sync a local approval decision back to
    KoboToolbox as a validation status update.

    All arguments are primitives so the task is
    safe to serialise via the Django Q ORM broker.
    """
    status_uid = ApprovalStatusTypes.KoboStatusMap.get(
        approval_status
    )
    if not status_uid:
        logger.warning(
            "No Kobo status mapping for "
            "approval_status=%s — skipping sync",
            approval_status,
        )
        return

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
    except Exception:
        logger.exception(
            "Failed to sync validation status "
            "for kobo_ids=%s on asset %s",
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
    except Exception:
        logger.exception(
            "Failed to sync geometry "
            "for kobo_id=%s on asset %s",
            kobo_id,
            asset_uid,
        )
