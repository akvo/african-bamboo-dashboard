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


class FlagType:
    """Validation flag type codes."""

    # Geometry errors (existing)
    GEOMETRY_NO_DATA = "GEOMETRY_NO_DATA"
    GEOMETRY_PARSE_FAIL = "GEOMETRY_PARSE_FAIL"
    GEOMETRY_TOO_FEW_VERTICES = (
        "GEOMETRY_TOO_FEW_VERTICES"
    )
    GEOMETRY_SELF_INTERSECT = (
        "GEOMETRY_SELF_INTERSECT"
    )
    GEOMETRY_AREA_TOO_SMALL = (
        "GEOMETRY_AREA_TOO_SMALL"
    )

    # Overlap (existing)
    OVERLAP = "OVERLAP"

    # Warnings (new — W1–W5)
    GPS_ACCURACY_LOW = "GPS_ACCURACY_LOW"
    POINT_GAP_LARGE = "POINT_GAP_LARGE"
    POINT_SPACING_UNEVEN = "POINT_SPACING_UNEVEN"
    AREA_TOO_LARGE = "AREA_TOO_LARGE"
    VERTICES_TOO_FEW_ROUGH = (
        "VERTICES_TOO_FEW_ROUGH"
    )


class FlagSeverity:
    ERROR = "error"
    WARNING = "warning"


class WarningThresholds:
    """Configurable thresholds for warning rules.

    Agreed with African Bamboo, January 2026.
    """

    GPS_ACCURACY_MAX_M = 15.0
    POINT_GAP_MAX_M = 50.0
    SPACING_CV_MAX = 0.5
    AREA_MAX_HA = 20.0
    VERTICES_ROUGH_MIN = 6
    VERTICES_ROUGH_MAX = 10


DEFAULT_FIELDS = [
    "enumerator",
    "farmer",
    "father_name",
    "grandfather_name",
    "age_of_farmer",
    "phone_number",
    "title_deed_1",
    "title_deed_2",
]
