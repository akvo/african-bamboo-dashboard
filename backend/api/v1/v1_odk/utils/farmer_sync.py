import logging

from django.db import IntegrityError
from django.db.models import IntegerField, Max
from django.db.models.functions import Cast

from api.v1.v1_odk.models import (
    Farmer,
    FarmerFieldMapping,
)
from api.v1.v1_odk.serializers import (
    build_option_lookup,
    resolve_value,
)

logger = logging.getLogger(__name__)


def resolve_field_value(
    raw_data,
    field_name,
    option_map,
    type_map,
):
    """Resolve a raw_data field name to its
    display value.

    Reads directly from raw_data using field_name
    as the key. Resolves select options to labels
    when applicable.

    Args:
        raw_data: submission.raw_data dict
        field_name: raw_data key (question name)
        option_map: {question_name: {opt: label}}
        type_map: {question_name: question_type}

    Returns:
        str or None
    """
    raw_val = raw_data.get(field_name)
    if raw_val is None:
        return None
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
    return val if val else None


def build_farmer_lookup_key(
    raw_data,
    unique_fields,
    option_map,
    type_map,
):
    """Build a lookup key from unique_fields values.

    Args:
        raw_data: submission.raw_data dict
        unique_fields: list of raw_data keys
        option_map: {question_name: {opt: label}}
        type_map: {question_name: question_type}

    Returns:
        str like "Dara - Hora - Daye" or None
    """
    parts = []
    for field_name in unique_fields:
        val = resolve_field_value(
            raw_data,
            field_name,
            option_map,
            type_map,
        )
        if val:
            parts.append(val)
    return " - ".join(parts) if parts else None


def generate_next_farmer_uid():
    """Generate the next sequential farmer UID.

    Uses numeric Cast + Max to avoid lexicographic
    ordering issues with string UIDs (e.g. "99999"
    sorting after "100000").

    Returns zero-padded string with minimum 5 digits.

    Returns:
        str: e.g. "00001", "00042", "100000"
    """
    result = Farmer.objects.aggregate(
        max_uid=Max(
            Cast("uid", IntegerField())
        )
    )
    max_uid = result["max_uid"]
    if max_uid is None:
        return "00001"
    return str(max_uid + 1).zfill(5)


def build_farmer_values(
    raw_data,
    values_fields,
    option_map,
    type_map,
):
    """Build farmer values dict from values_fields.

    Args:
        raw_data: submission.raw_data dict
        values_fields: list of raw_data keys
        option_map: {question_name: {opt: label}}
        type_map: {question_name: question_type}

    Returns:
        dict: {field_name: resolved_value}
    """
    result = {}
    for field_name in values_fields:
        val = resolve_field_value(
            raw_data,
            field_name,
            option_map,
            type_map,
        )
        result[field_name] = val
    return result


def sync_farmers_for_form(form):
    """Sync Farmer records for all submissions
    in a given form.

    Reads FarmerFieldMapping config, resolves field
    values directly from raw_data, creates/updates
    Farmer records, and links plots.

    Args:
        form: FormMetadata instance

    Returns:
        dict: {"created": N, "updated": N, "linked": N}
    """
    mapping = FarmerFieldMapping.objects.filter(
        form=form
    ).first()
    if not mapping:
        logger.info(
            "No FarmerFieldMapping for form %s",
            form.asset_uid,
        )
        return {
            "created": 0,
            "updated": 0,
            "linked": 0,
        }

    unique_fields = [
        f.strip()
        for f in mapping.unique_fields.split(",")
        if f.strip()
    ]
    values_fields = [
        f.strip()
        for f in mapping.values_fields.split(",")
        if f.strip()
    ]

    option_map, type_map = build_option_lookup(form)

    created = 0
    updated = 0
    linked = 0

    submissions = form.submissions.select_related(
        "plot"
    ).all()

    for submission in submissions:
        raw_data = submission.raw_data or {}

        lookup_key = build_farmer_lookup_key(
            raw_data,
            unique_fields,
            option_map,
            type_map,
        )
        if not lookup_key:
            continue

        # Store both unique_fields and
        # values_fields in farmer.values
        all_fields = list(
            dict.fromkeys(
                unique_fields + values_fields
            )
        )
        values = build_farmer_values(
            raw_data,
            all_fields,
            option_map,
            type_map,
        )

        try:
            farmer = Farmer.objects.get(
                lookup_key=lookup_key
            )
            farmer.values = values
            farmer.save(update_fields=["values"])
            updated += 1
        except Farmer.DoesNotExist:
            # Retry on IntegrityError to handle
            # concurrent UID generation races
            for attempt in range(3):
                uid = generate_next_farmer_uid()
                try:
                    farmer = (
                        Farmer.objects.create(
                            uid=uid,
                            lookup_key=lookup_key,
                            values=values,
                        )
                    )
                    created += 1
                    break
                except IntegrityError:
                    if attempt == 2:
                        raise
                    continue

        try:
            plot = submission.plot
        except Exception:
            plot = None

        if plot and plot.farmer_id != farmer.pk:
            plot.farmer = farmer
            plot.save(update_fields=["farmer"])
            linked += 1

    logger.info(
        "sync_farmers_for_form %s: "
        "created=%d updated=%d linked=%d",
        form.asset_uid,
        created,
        updated,
        linked,
    )
    return {
        "created": created,
        "updated": updated,
        "linked": linked,
    }
