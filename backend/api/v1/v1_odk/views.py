import logging
import time
from datetime import datetime
from datetime import timezone as tz

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.mixins import (
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from django_q.tasks import async_task

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    FormOption,
    FormQuestion,
    Plot,
    Submission,
)
from api.v1.v1_odk.serializers import (
    FormMetadataSerializer,
    PlotOverlapQuerySerializer,
    PlotSerializer,
    SubmissionDetailSerializer,
    SubmissionListSerializer,
    SubmissionUpdateSerializer,
    SyncTriggerSerializer,
    build_option_lookup,
)
from utils.encryption import decrypt
from utils.kobo_client import KoboClient
from utils.polygon import (
    append_overlap_reason,
    build_overlap_reason,
    compute_bbox,
    extract_plot_data,
    find_overlapping_plots,
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


def _sync_form_questions(form, content):
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
        label = label_list[0] if label_list else ch.get("name", "")
        choices_by_list.setdefault(ln, []).append(
            {"name": ch.get("name", ""), "label": label}
        )

    questions = []
    # Map question object -> list_name for selects
    select_list_map = []

    for item in survey:
        field_type = item.get("type", "")
        if field_type in SKIP_FIELD_TYPES:
            continue

        name = item.get("$xpath", item.get("name", ""))
        label_list = item.get("label", [])
        label = label_list[0] if label_list else item.get("name", "")

        # Determine select list_name
        list_name = item.get("select_from_list_name", "")
        q_type = field_type
        if not list_name and field_type.startswith("select_"):
            # Fallback: "select_one list_name" format
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
            select_list_map.append((len(questions) - 1, list_name))

    created_qs = FormQuestion.objects.bulk_create(questions)

    # Bulk-create options for select questions
    options = []
    for idx, list_name in select_list_map:
        q = created_qs[idx]
        for ch in choices_by_list.get(list_name, []):
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


MAPPING_FIELDS = {
    "polygon_field",
    "region_field",
    "sub_region_field",
    "plot_name_field",
}


def _rederive_plots(form):
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
        plot.min_lat = data["min_lat"]
        plot.max_lat = data["max_lat"]
        plot.min_lon = data["min_lon"]
        plot.max_lon = data["max_lon"]
        plot.flagged_for_review = data[
            "flagged_for_review"
        ]
        plot.flagged_reason = data["flagged_reason"]
        updated.append(plot)
    if updated:
        Plot.objects.bulk_update(
            updated,
            [
                "plot_name",
                "region",
                "sub_region",
                "polygon_wkt",
                "min_lat",
                "max_lat",
                "min_lon",
                "max_lon",
                "flagged_for_review",
                "flagged_reason",
            ],
        )
    logger.info(
        "Re-derived %d plots for form %s",
        len(updated),
        form.asset_uid,
    )
    return len(updated)


@extend_schema(tags=["Forms"])
class FormMetadataViewSet(viewsets.ModelViewSet):
    queryset = FormMetadata.objects.all()
    serializer_class = FormMetadataSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "asset_uid"

    def _make_kobo_client(self, user):
        if (
            not user.kobo_url
            or not user.kobo_username
            or not user.kobo_password
        ):
            return None
        return KoboClient(
            user.kobo_url,
            user.kobo_username,
            decrypt(user.kobo_password),
        )

    def perform_update(self, serializer):
        form = self.get_object()
        old = {
            f: getattr(form, f)
            for f in MAPPING_FIELDS
        }
        instance = serializer.save()
        changed = any(
            getattr(instance, f) != old[f]
            for f in MAPPING_FIELDS
        )
        if changed:
            _rederive_plots(instance)

    @extend_schema(
        tags=["ODK"],
        summary="List available form fields",
    )
    @action(detail=True, methods=["get"])
    def form_fields(self, request, asset_uid=None):
        """Proxy KoboToolbox asset detail to list
        available survey fields."""
        self.get_object()  # 404 if form missing
        client = self._make_kobo_client(request.user)
        if client is None:
            return Response(
                {"message": "No Kobo credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            content = client.get_asset_detail(asset_uid)
        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        survey = content.get("survey", [])
        fields = []
        for item in survey:
            field_type = item.get("type", "")
            if field_type in SKIP_FIELD_TYPES:
                continue
            label_list = item.get("label", [])
            label = (
                " ".join(
                    lbl
                    for lbl in label_list if lbl
                )
                if label_list else item.get("name", "")
            )
            fields.append(
                {
                    "name": item.get("name", ""),
                    "type": field_type,
                    "label": label,
                    "full_path": item.get(
                        "$xpath",
                        item.get("name", ""),
                    ),
                }
            )

        return Response({"fields": fields})

    @extend_schema(
        request=SyncTriggerSerializer,
        tags=["ODK"],
        summary="Trigger sync from KoboToolbox",
    )
    @action(detail=True, methods=["post"])
    def sync(self, request, asset_uid=None):
        """Fetch submissions from KoboToolbox
        and upsert into local DB."""
        form = self.get_object()
        client = self._make_kobo_client(request.user)
        if client is None:
            return Response(
                {"message": "No Kobo credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sync form questions and options
        questions_synced = 0
        try:
            content = client.get_asset_detail(form.asset_uid)
            questions_synced = _sync_form_questions(form, content)
        except Exception:
            pass  # Continue sync even if this fails

        since_iso = None
        if form.last_sync_timestamp > 0:
            since_iso = datetime.fromtimestamp(
                form.last_sync_timestamp / 1000,
                tz=tz.utc,
            ).strftime("%Y-%m-%dT%H:%M:%S")

        results = client.fetch_all_submissions(form.asset_uid, since_iso)

        created = 0
        plots_created = 0
        plots_updated = 0
        plots_flagged = 0

        for item in results:
            sub_time_str = item.get(
                "_submission_time", ""
            )
            sub_time_ms = int(
                datetime.fromisoformat(
                    sub_time_str
                ).timestamp()
                * 1000
            )
            sub, is_new = (
                Submission.objects.update_or_create(
                    uuid=item["_uuid"],
                    defaults={
                        "form": form,
                        "kobo_id": str(item["_id"]),
                        "submission_time": sub_time_ms,
                        "submitted_by": item.get(
                            "_submitted_by"
                        ),
                        "instance_name": item.get(
                            "meta/instanceName"
                        ),
                        "raw_data": item,
                        "system_data": {
                            "_geolocation": (
                                item.get(
                                    "_geolocation"
                                )
                            ),
                            "_tags": item.get(
                                "_tags", []
                            ),
                        },
                    },
                )
            )
            if is_new:
                created += 1

            # Auto-generate plot
            plot_data = extract_plot_data(item, form)
            now_ms = int(time.time() * 1000)
            defaults = {
                "form": form,
                "plot_name": (
                    plot_data["plot_name"]
                ),
                "instance_name": (
                    item.get(
                        "meta/instanceName",
                        "",
                    )
                ),
                "polygon_wkt": (
                    plot_data["polygon_wkt"]
                ),
                "min_lat": (
                    plot_data["min_lat"]
                ),
                "max_lat": (
                    plot_data["max_lat"]
                ),
                "min_lon": (
                    plot_data["min_lon"]
                ),
                "max_lon": (
                    plot_data["max_lon"]
                ),
                "region": (
                    plot_data["region"]
                ),
                "sub_region": (
                    plot_data["sub_region"]
                ),
                "created_at": now_ms,
            }
            # Only set flag fields when geometry
            # is invalid; preserve DB value for
            # valid polygons so tri-state works
            # (None=unchecked, False=clean).
            if plot_data["flagged_for_review"]:
                defaults["flagged_for_review"] = (
                    True
                )
                defaults["flagged_reason"] = (
                    plot_data["flagged_reason"]
                )
            plot, plot_is_new = (
                Plot.objects.update_or_create(
                    submission=sub,
                    defaults=defaults,
                )
            )
            if plot_is_new:
                plots_created += 1
            else:
                plots_updated += 1

            # Overlap detection (unchecked only)
            if (
                plot_data["polygon_wkt"]
                and plot.flagged_for_review is None
            ):
                bbox = compute_bbox(
                    [
                        (
                            plot_data["min_lon"],
                            plot_data["min_lat"],
                        ),
                        (
                            plot_data["max_lon"],
                            plot_data["max_lat"],
                        ),
                    ]
                )
                overlaps = (
                    find_overlapping_plots(
                        plot_data["polygon_wkt"],
                        bbox,
                        form.pk,
                        exclude_pk=plot.pk,
                    )
                )
                if overlaps:
                    reason = (
                        build_overlap_reason(
                            overlaps
                        )
                    )
                    plot.flagged_for_review = True
                    plot.flagged_reason = reason
                    plot.save(
                        update_fields=[
                            "flagged_for_review",
                            "flagged_reason",
                        ]
                    )
                    # Flag existing plots
                    to_update = []
                    for op in overlaps:
                        op.flagged_for_review = (
                            True
                        )
                        op.flagged_reason = (
                            append_overlap_reason(
                                op.flagged_reason,
                                plot_data[
                                    "plot_name"
                                ],
                                item.get(
                                    "meta/"
                                    "instanceName",
                                    "",
                                ),
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
                else:
                    # Checked, no overlaps
                    plot.flagged_for_review = False
                    plot.save(
                        update_fields=[
                            "flagged_for_review",
                        ]
                    )

            if plot.flagged_for_review:
                plots_flagged += 1

        if results:
            latest = max(r["_submission_time"] for r in results)
            form.last_sync_timestamp = int(
                datetime.fromisoformat(latest).timestamp() * 1000
            )
            form.save()

        return Response(
            {
                "synced": len(results),
                "created": created,
                "plots_created": plots_created,
                "plots_updated": plots_updated,
                "plots_flagged": plots_flagged,
                "questions_synced": (
                    questions_synced
                ),
            }
        )


@extend_schema(tags=["Submissions"])
class SubmissionViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    queryset = Submission.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SubmissionDetailSerializer
        if self.action in (
            "update",
            "partial_update",
        ):
            return SubmissionUpdateSerializer
        return SubmissionListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.action == "list":
            asset_uid = self.request.query_params.get("asset_uid")
            if asset_uid:
                try:
                    form = FormMetadata.objects.get(asset_uid=asset_uid)
                    om, tm = build_option_lookup(form)
                    ctx["option_lookup"] = om
                    ctx["type_map"] = tm
                except FormMetadata.DoesNotExist:
                    pass
        return ctx

    STATUS_MAP = {
        "approved": ApprovalStatusTypes.APPROVED,
        "rejected": ApprovalStatusTypes.REJECTED,
    }

    def get_queryset(self):
        qs = super().get_queryset()
        asset_uid = self.request.query_params.get(
            "asset_uid"
        )
        if asset_uid:
            qs = qs.filter(form__asset_uid=asset_uid)
        status_param = (
            self.request.query_params.get("status")
        )
        if status_param is not None:
            if status_param == "pending":
                qs = qs.filter(
                    approval_status__isnull=True
                )
            elif status_param in self.STATUS_MAP:
                qs = qs.filter(
                    approval_status=(
                        self.STATUS_MAP[status_param]
                    )
                )
        return qs

    def perform_update(self, serializer):
        instance = serializer.save()
        approval = instance.approval_status
        kobo_uid = (
            ApprovalStatusTypes.KoboStatusMap.get(
                approval
            )
        )
        if not kobo_uid:
            return
        user = self.request.user
        if (
            not user.kobo_url
            or not user.kobo_username
            or not user.kobo_password
        ):
            return
        async_task(
            "api.v1.v1_odk.tasks"
            ".sync_kobo_validation_status",
            user.kobo_url,
            user.kobo_username,
            user.kobo_password,
            instance.form.asset_uid,
            [int(instance.kobo_id)],
            approval,
        )

    @extend_schema(tags=["ODK"])
    @action(detail=False, methods=["get"])
    def latest_sync_time(self, request):
        """Get latest submission_time
        for a form."""
        asset_uid = request.query_params.get("asset_uid")
        if not asset_uid:
            return Response(
                {"message": ("asset_uid is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        latest = (
            Submission.objects.filter(form__asset_uid=asset_uid)
            .order_by("-submission_time")
            .values_list("submission_time", flat=True)
            .first()
        )
        return Response({"latest_submission_time": latest})


@extend_schema(tags=["Plots"])
class PlotViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    queryset = Plot.objects.all()
    serializer_class = PlotSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"

    STATUS_MAP = {
        "approved": ApprovalStatusTypes.APPROVED,
        "rejected": ApprovalStatusTypes.REJECTED,
    }

    def get_queryset(self):
        qs = super().get_queryset()
        form_id = self.request.query_params.get(
            "form_id"
        )
        status_param = (
            self.request.query_params.get("status")
        )
        if form_id:
            qs = qs.filter(
                form__asset_uid=form_id
            )
        if status_param is not None:
            if status_param == "flagged":
                qs = qs.filter(
                    flagged_for_review=True
                )
            elif status_param == "pending":
                qs = qs.filter(
                    submission__approval_status__isnull=True,  # noqa: E501
                )
            elif status_param in self.STATUS_MAP:
                qs = qs.filter(
                    submission__approval_status=(
                        self.STATUS_MAP[status_param]
                    )
                )
        return qs

    @extend_schema(
        request=PlotOverlapQuerySerializer,
        tags=["ODK"],
        summary="Find overlapping plots",
    )
    @action(detail=False, methods=["post"])
    def overlap_candidates(self, request):
        """Find plots whose bounding boxes overlap
        with the given bounds."""
        serializer = PlotOverlapQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        plots = Plot.objects.filter(
            min_lon__lte=d["max_lon"],
            max_lon__gte=d["min_lon"],
            min_lat__lte=d["max_lat"],
            max_lat__gte=d["min_lat"],
        )
        if d.get("exclude_uuid"):
            plots = plots.exclude(uuid=d["exclude_uuid"])

        return Response(PlotSerializer(plots, many=True).data)

    @extend_schema(
        tags=["ODK"],
        summary="Reset polygon to original from Kobo",
    )
    @action(detail=True, methods=["post"])
    def reset_polygon(self, request, uuid=None):
        """Re-derive polygon geometry from the linked
        submission's raw_data."""
        plot = self.get_object()
        if not plot.submission:
            return Response(
                {"message": "No linked submission"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        plot_data = extract_plot_data(
            plot.submission.raw_data, plot.form
        )
        plot.polygon_wkt = plot_data["polygon_wkt"]
        plot.min_lat = plot_data["min_lat"]
        plot.max_lat = plot_data["max_lat"]
        plot.min_lon = plot_data["min_lon"]
        plot.max_lon = plot_data["max_lon"]
        plot.flagged_for_review = plot_data[
            "flagged_for_review"
        ]
        plot.flagged_reason = plot_data[
            "flagged_reason"
        ]
        plot.save()
        return Response(PlotSerializer(plot).data)
