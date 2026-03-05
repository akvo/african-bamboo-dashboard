class ApprovalStatusTypes:
    PENDING = 0
    APPROVED = 1
    REJECTED = 2

    KoboStatusMap = {
        PENDING: "validation_status_on_hold",
        APPROVED: "validation_status_approved",
        REJECTED: "validation_status_not_approved",
    }


class SyncStatus:
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


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
