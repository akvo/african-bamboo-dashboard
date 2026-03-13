class ApprovalStatusTypes:
    PENDING = 0
    APPROVED = 1
    REJECTED = 2

    KoboStatusMap = {
        PENDING: "validation_status_on_hold",
        APPROVED: "validation_status_approved",
        REJECTED: "validation_status_not_approved",
    }

    ReverseKoboStatusMap = {
        "validation_status_on_hold": None,
        "validation_status_approved": APPROVED,
        "validation_status_not_approved": REJECTED,
    }


class SyncStatus:
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


ATTACHMENTS_FOLDER = "attachments"

EXCLUDED_QUESTION_TYPES = [
    "geoshape",
    "geotrace",
    "geopoint",
]


class RejectionCategory:
    POLYGON_ERROR = "polygon_error"
    OVERLAP = "overlap"
    DUPLICATE = "duplicate"
    OTHER = "other"

    CHOICES = [
        (POLYGON_ERROR, "Polygon Error"),
        (OVERLAP, "Overlap"),
        (DUPLICATE, "Duplicate Submission"),
        (OTHER, "Other"),
    ]
