import logging

from api.v1.v1_odk.constants import ApprovalStatusTypes
from utils.encryption import decrypt
from utils.kobo_client import KoboClient

logger = logging.getLogger(__name__)


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
