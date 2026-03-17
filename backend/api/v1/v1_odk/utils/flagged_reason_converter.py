from api.v1.v1_odk.constants import (
    FlagSeverity,
    FlagType,
)


def convert_flagged_reason(reason):
    """Convert legacy string flagged_reason to JSON.

    Returns list of {type, severity, note} dicts,
    or None if input is None/empty.
    Skips values that are already lists (idempotent).
    """
    if reason is None:
        return None
    if isinstance(reason, list):
        return reason
    if not isinstance(reason, str):
        return None
    reason = reason.strip()
    if not reason:
        return None

    lower = reason.lower()
    if "overlap" in lower:
        flag_type = FlagType.OVERLAP
    elif "too few vertices" in lower:
        flag_type = FlagType.GEOMETRY_TOO_FEW_VERTICES
    elif "intersect" in lower:
        flag_type = FlagType.GEOMETRY_SELF_INTERSECT
    elif "too small" in lower:
        flag_type = FlagType.GEOMETRY_AREA_TOO_SMALL
    elif "no polygon data" in lower:
        flag_type = FlagType.GEOMETRY_NO_DATA
    elif "failed to parse" in lower:
        flag_type = FlagType.GEOMETRY_PARSE_FAIL
    else:
        flag_type = FlagType.GEOMETRY_PARSE_FAIL

    return [
        {
            "type": flag_type,
            "severity": FlagSeverity.ERROR,
            "note": reason,
        }
    ]
