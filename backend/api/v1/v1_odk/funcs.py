import logging

from django_q.tasks import async_task

from api.v1.v1_odk.models import (
    FormOption,
    FormQuestion,
    Plot,
)
from utils.polygon import (
    append_overlap_reason,
    build_overlap_reason,
    compute_bbox,
    extract_plot_data,
    find_overlapping_plots,
    parse_wkt_polygon,
    validate_polygon,
    wkt_to_odk_geoshape,
)

logger = logging.getLogger(__name__)

SKIP_FIELD_TYPES = {
    "start",
    "end",
    "calculate",
    "note",
    "begin_group",
    "end_group",
    "begin_repeat",
    "end_repeat",
}

MAPPING_FIELDS = {
    "polygon_field",
    "region_field",
    "sub_region_field",
    "plot_name_field",
}


def sync_form_questions(form, content):
    """Sync survey questions and choices from
    KoboToolbox asset content into FormQuestion
    and FormOption records.

    Deletes existing questions (cascades to options)
    then bulk-creates from the asset content.
    """
    FormQuestion.objects.filter(form=form).delete()

    survey = content.get("survey", [])
    choices = content.get("choices", [])

    # Build {list_name: [{name, label}, ...]}
    choices_by_list = {}
    for ch in choices:
        ln = ch.get("list_name", "")
        if not ln:
            continue
        label_list = ch.get("label", [])
        label = (
            label_list[0]
            if label_list
            else ch.get("name", "")
        )
        choices_by_list.setdefault(ln, []).append(
            {
                "name": ch.get("name", ""),
                "label": label,
            }
        )

    questions = []
    # Map question object -> list_name for selects
    select_list_map = []

    for item in survey:
        field_type = item.get("type", "")
        if field_type in SKIP_FIELD_TYPES:
            continue

        name = item.get(
            "$xpath", item.get("name", "")
        )
        label_list = item.get("label", [])
        label = (
            label_list[0]
            if label_list
            else item.get("name", "")
        )

        # Determine select list_name
        list_name = item.get(
            "select_from_list_name", ""
        )
        q_type = field_type
        if (
            not list_name
            and field_type.startswith("select_")
        ):
            # Fallback: "select_one list_name"
            parts = field_type.split(" ", 1)
            if len(parts) == 2:
                q_type = parts[0]
                list_name = parts[1]

        q = FormQuestion(
            form=form,
            name=name,
            label=label,
            type=q_type,
        )
        questions.append(q)
        if list_name:
            select_list_map.append(
                (len(questions) - 1, list_name)
            )

    created_qs = (
        FormQuestion.objects.bulk_create(questions)
    )

    # Bulk-create options for select questions
    options = []
    for idx, list_name in select_list_map:
        q = created_qs[idx]
        for ch in choices_by_list.get(
            list_name, []
        ):
            options.append(
                FormOption(
                    question=q,
                    name=ch["name"],
                    label=ch["label"],
                )
            )

    if options:
        FormOption.objects.bulk_create(options)

    return len(created_qs)


def check_and_flag_overlaps(plot):
    """Run overlap detection for a single plot.

    Sets flagged_for_review and flagged_reason
    based on overlap results. Also flags any
    existing overlapping plots. Saves to DB.
    Returns True if overlaps were found.
    """
    if not plot.polygon_wkt:
        return False

    bbox = compute_bbox(
        [
            (plot.min_lon, plot.min_lat),
            (plot.max_lon, plot.max_lat),
        ]
    )
    overlaps = find_overlapping_plots(
        plot.polygon_wkt,
        bbox,
        plot.form_id,
        exclude_pk=plot.pk,
    )
    if overlaps:
        reason = build_overlap_reason(overlaps)
        plot.flagged_for_review = True
        plot.flagged_reason = reason
        plot.save(
            update_fields=[
                "flagged_for_review",
                "flagged_reason",
            ]
        )
        inst = (
            plot.submission.instance_name
            if plot.submission
            else None
        ) or str(plot.uuid)
        to_update = []
        for op in overlaps:
            op.flagged_for_review = True
            op.flagged_reason = (
                append_overlap_reason(
                    op.flagged_reason,
                    plot.plot_name or inst,
                    inst,
                )
            )
            to_update.append(op)
        Plot.objects.bulk_update(
            to_update,
            [
                "flagged_for_review",
                "flagged_reason",
            ],
        )
        return True
    else:
        plot.flagged_for_review = False
        plot.flagged_reason = None
        plot.save(
            update_fields=[
                "flagged_for_review",
                "flagged_reason",
            ]
        )
        return False


def validate_and_check_plot(plot):
    """Validate edited polygon and check overlaps.

    Parses the plot's polygon_wkt, validates
    geometry, updates bbox and flags, then runs
    overlap detection. Call after saving a plot
    with new polygon_wkt.
    """
    wkt = plot.polygon_wkt
    if not wkt:
        plot.flagged_for_review = True
        plot.flagged_reason = (
            "No polygon data found in submission."
        )
        plot.min_lat = None
        plot.max_lat = None
        plot.min_lon = None
        plot.max_lon = None
        plot.save(
            update_fields=[
                "flagged_for_review",
                "flagged_reason",
                "min_lat",
                "max_lat",
                "min_lon",
                "max_lon",
            ]
        )
        return

    coords = parse_wkt_polygon(wkt)
    if coords is None:
        plot.flagged_for_review = True
        plot.flagged_reason = (
            "Failed to parse polygon geometry."
        )
        plot.save(
            update_fields=[
                "flagged_for_review",
                "flagged_reason",
            ]
        )
        return

    is_valid, error_msg = validate_polygon(coords)
    if not is_valid:
        plot.flagged_for_review = True
        plot.flagged_reason = error_msg
        plot.save(
            update_fields=[
                "flagged_for_review",
                "flagged_reason",
            ]
        )
        return

    bbox = compute_bbox(coords)
    plot.min_lat = bbox["min_lat"]
    plot.max_lat = bbox["max_lat"]
    plot.min_lon = bbox["min_lon"]
    plot.max_lon = bbox["max_lon"]
    plot.save(
        update_fields=[
            "min_lat",
            "max_lat",
            "min_lon",
            "max_lon",
        ]
    )
    check_and_flag_overlaps(plot)


def rederive_plots(form):
    """Re-derive plot fields from raw submission
    data when field mappings change."""
    plots = list(
        Plot.objects.filter(form=form)
        .select_related("submission")
    )
    updated = []
    for plot in plots:
        if not plot.submission:
            continue
        data = extract_plot_data(
            plot.submission.raw_data, form
        )
        plot.plot_name = data["plot_name"]
        plot.region = data["region"]
        plot.sub_region = data["sub_region"]
        plot.polygon_wkt = data["polygon_wkt"]
        plot.polygon_source_field = data[
            "polygon_source_field"
        ]
        plot.min_lat = data["min_lat"]
        plot.max_lat = data["max_lat"]
        plot.min_lon = data["min_lon"]
        plot.max_lon = data["max_lon"]
        plot.flagged_for_review = data[
            "flagged_for_review"
        ]
        plot.flagged_reason = data[
            "flagged_reason"
        ]
        updated.append(plot)
    if updated:
        Plot.objects.bulk_update(
            updated,
            [
                "plot_name",
                "region",
                "sub_region",
                "polygon_wkt",
                "polygon_source_field",
                "min_lat",
                "max_lat",
                "min_lon",
                "max_lon",
                "flagged_for_review",
                "flagged_reason",
            ],
        )
    # Re-run overlap detection for plots
    # with valid geometry
    for plot in updated:
        if plot.polygon_wkt:
            check_and_flag_overlaps(plot)
    logger.info(
        "Re-derived %d plots for form %s",
        len(updated),
        form.asset_uid,
    )
    return len(updated)


def dispatch_kobo_geometry_sync(
    user, plot, polygon_wkt
):
    """Dispatch an async task to sync polygon
    geometry back to KoboToolbox."""
    if (
        not user.kobo_url
        or not user.kobo_username
        or not user.kobo_password
    ):
        return
    if not plot.submission:
        return
    form = plot.form
    if not form or not form.polygon_field:
        return
    if not polygon_wkt:
        return

    polygon_field_name = (
        plot.polygon_source_field
        or form.polygon_field.split(",")[0].strip()
    )
    if not polygon_field_name:
        return

    odk_geoshape = wkt_to_odk_geoshape(
        polygon_wkt
    )
    if not odk_geoshape:
        return

    async_task(
        "api.v1.v1_odk.tasks"
        ".sync_kobo_submission_geometry",
        user.kobo_url,
        user.kobo_username,
        user.kobo_password,
        form.asset_uid,
        int(plot.submission.kobo_id),
        polygon_field_name,
        odk_geoshape,
    )
