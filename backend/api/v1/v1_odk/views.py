import time
from datetime import datetime
from datetime import timezone as tz

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
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

from api.v1.v1_jobs.constants import (
    JobStatus,
    JobTypes,
)
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_jobs.serializers import (
    JobSerializer,
)
from api.v1.v1_odk.constants import (
    EXCLUDED_QUESTION_TYPES,
    ApprovalStatusTypes,
)
from api.v1.v1_odk.funcs import (
    MAPPING_FIELDS,
    SKIP_FIELD_TYPES,
    check_and_flag_overlaps,
    dispatch_kobo_geometry_sync,
    rederive_plots,
    sync_form_questions,
    validate_and_check_plot,
)
from api.v1.v1_odk.models import (
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormQuestion,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.serializers import (
    FieldMappingSerializer,
    FieldSettingsSerializer,
    FormMetadataSerializer,
    PlotOverlapQuerySerializer,
    PlotSerializer,
    SubmissionDetailSerializer,
    SubmissionListSerializer,
    SubmissionUpdateSerializer,
    SyncTriggerSerializer,
    build_option_lookup,
)
from api.v1.v1_odk.utils.area_calc import (
    calculate_area_ha,
)
from utils.encryption import decrypt
from utils.kobo_client import KoboClient
from utils.polygon import extract_plot_data


def _parse_date_param(params, name):
    """Parse an integer timestamp query param.

    Returns None when the param is absent.
    Raises ValidationError for non-integer values.
    """
    raw = params.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        raise ValidationError(
            {name: "Must be an integer timestamp."}
        )


def _parse_date_range(params):
    """Return (start, end) integer timestamps.

    Raises ValidationError when values are not
    integers or when start_date > end_date.
    """
    start = _parse_date_param(params, "start_date")
    end = _parse_date_param(params, "end_date")
    if (
        start is not None
        and end is not None
        and start > end
    ):
        raise ValidationError(
            {
                "start_date": (
                    "start_date must be <= end_date."
                )
            }
        )
    return start, end


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
            rederive_plots(instance)

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
            content = client.get_asset_detail(
                asset_uid
            )
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
                if label_list
                else item.get("name", "")
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
        tags=["ODK"],
        summary="List local form questions with IDs",
    )
    @action(detail=True, methods=["get"])
    def form_questions(
        self, request, asset_uid=None
    ):
        """Return FormQuestion records stored in DB
        for a given form, including their IDs."""
        form = self.get_object()
        qs = FormQuestion.objects.filter(
            form=form
        ).order_by("pk")
        data = [
            {
                "id": q.pk,
                "name": q.name,
                "label": q.label,
                "type": q.type,
            }
            for q in qs
        ]
        return Response(data)

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
            content = client.get_asset_detail(
                form.asset_uid
            )
            questions_synced = sync_form_questions(
                form, content
            )
        except Exception as e:
            return Response(
                {
                    "message": (
                        f"Error syncing form "
                        f"questions: {str(e)}"
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        since_iso = None
        if form.last_sync_timestamp > 0:
            since_iso = datetime.fromtimestamp(
                form.last_sync_timestamp / 1000,
                tz=tz.utc,
            ).strftime("%Y-%m-%dT%H:%M:%S")

        results = client.fetch_all_submissions(
            form.asset_uid, since_iso
        )

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
                        "kobo_id": str(
                            item["_id"]
                        ),
                        "submission_time": (
                            sub_time_ms
                        ),
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
            # Compute area from raw polygon
            raw_polygon = plot_data.get(
                "raw_polygon_string"
            )
            area = calculate_area_ha(raw_polygon)

            defaults = {
                "form": form,
                "plot_name": (
                    plot_data["plot_name"]
                ),
                "polygon_source_field": (
                    plot_data[
                        "polygon_source_field"
                    ]
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
                "area_ha": area,
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

            # Overlap detection for valid geometry
            if plot_data["polygon_wkt"]:
                check_and_flag_overlaps(plot)

            if plot.flagged_for_review:
                plots_flagged += 1

            # Queue attachment download
            has_images = any(
                a.get("mimetype", "").startswith(
                    "image/"
                )
                for a in item.get(
                    "_attachments", []
                )
            )
            if has_images:
                async_task(
                    "api.v1.v1_odk.tasks"
                    ".download_submission"
                    "_attachments",
                    request.user.kobo_url,
                    request.user.kobo_username,
                    request.user.kobo_password,
                    str(sub.uuid),
                )

        if results:
            latest = max(
                r["_submission_time"]
                for r in results
            )
            form.last_sync_timestamp = int(
                datetime.fromisoformat(
                    latest
                ).timestamp()
                * 1000
            )
            form.save()

        # Post-sync sweep: re-check plots whose
        # flags were cleared by old buggy code
        unchecked = Plot.objects.filter(
            form=form,
            flagged_for_review__isnull=True,
            polygon_wkt__isnull=False,
        )
        for plot in unchecked.iterator():
            check_and_flag_overlaps(plot)
            if plot.flagged_for_review:
                plots_flagged += 1

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
            asset_uid = (
                self.request.query_params.get(
                    "asset_uid"
                )
            )
            if asset_uid:
                try:
                    form = (
                        FormMetadata.objects.get(
                            asset_uid=asset_uid
                        )
                    )
                    om, tm = build_option_lookup(
                        form
                    )
                    ctx["option_lookup"] = om
                    ctx["type_map"] = tm
                    ctx["question_names"] = {
                        q["name"]
                        for q in (
                            self._get_form_questions(
                                asset_uid
                            )
                        )
                    }
                except FormMetadata.DoesNotExist:
                    pass
        return ctx

    def _get_form_questions(self, asset_uid):
        try:
            form = FormMetadata.objects.get(
                asset_uid=asset_uid
            )
        except FormMetadata.DoesNotExist:
            return []
        mapped_fields = set()
        for spec in [
            form.region_field,
            form.sub_region_field,
            form.plot_name_field,
        ]:
            if spec:
                for f in spec.split(","):
                    stripped = f.strip()
                    if stripped:
                        mapped_fields.add(stripped)
        qs = (
            FormQuestion.objects.filter(form=form)
            .exclude(
                type__in=EXCLUDED_QUESTION_TYPES
            )
            .order_by("pk")
        )
        return [
            {
                "name": q.name,
                "label": q.label,
                "type": q.type,
            }
            for q in qs
            if q.name not in mapped_fields
        ]

    def list(self, request, *args, **kwargs):
        response = super().list(
            request, *args, **kwargs
        )
        asset_uid = request.query_params.get(
            "asset_uid"
        )
        if asset_uid:
            response.data["questions"] = (
                self._get_form_questions(asset_uid)
            )
        else:
            response.data["questions"] = []
        return response

    STATUS_MAP = {
        "approved": ApprovalStatusTypes.APPROVED,
        "rejected": ApprovalStatusTypes.REJECTED,
    }

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        asset_uid = params.get("asset_uid")
        if asset_uid:
            qs = qs.filter(
                form__asset_uid=asset_uid
            )
        status_param = params.get("status")
        if status_param is not None:
            if status_param == "pending":
                qs = qs.filter(
                    approval_status__isnull=True
                )
            elif status_param in self.STATUS_MAP:
                qs = qs.filter(
                    approval_status=(
                        self.STATUS_MAP[
                            status_param
                        ]
                    )
                )
        region = params.get("region")
        if region:
            qs = qs.filter(plot__region=region)
        sub_region = params.get("sub_region")
        if sub_region:
            qs = qs.filter(
                plot__sub_region=sub_region
            )
        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(
                    plot__plot_name__icontains=search
                )
                | Q(
                    instance_name__icontains=search
                )
            )
        start_date, end_date = _parse_date_range(
            params
        )
        if start_date is not None:
            qs = qs.filter(
                submission_time__gte=start_date
            )
        if end_date is not None:
            qs = qs.filter(
                submission_time__lte=end_date
            )
        # Dynamic raw_data filters
        if asset_uid:
            qs = self._apply_dynamic_filters(
                qs, params, asset_uid
            )
        return qs

    def _apply_dynamic_filters(
        self, qs, params, asset_uid
    ):
        filter_keys = [
            k
            for k in params
            if k.startswith("filter__")
        ]
        if not filter_keys:
            return qs
        try:
            form = FormMetadata.objects.get(
                asset_uid=asset_uid
            )
        except FormMetadata.DoesNotExist:
            return qs
        allowed = form.filter_fields or []
        for key in filter_keys:
            field_name = key[len("filter__"):]
            if field_name in allowed:
                qs = qs.filter(
                    **{
                        f"raw_data__{field_name}": (
                            params[key]
                        )
                    }
                )
        return qs

    def perform_update(self, serializer):
        reason_category = (
            serializer.validated_data.get(
                "reason_category"
            )
        )
        reason_text = (
            serializer.validated_data.get(
                "reason_text", ""
            )
        )
        instance = serializer.save(
            updated_by=self.request.user,
            updated_at=timezone.now(),
        )
        approval = instance.approval_status

        # Re-check polygon & overlaps on revert
        if approval is None:
            plot = getattr(
                instance, "plot", None
            )
            if plot:
                validate_and_check_plot(plot)

        # Create RejectionAudit for rejections
        audit = None
        if (
            approval
            == ApprovalStatusTypes.REJECTED
            and reason_category
        ):
            plot = getattr(
                instance, "plot", None
            )
            if plot:
                audit = (
                    RejectionAudit.objects.create(
                        plot=plot,
                        submission=instance,
                        validator=(
                            self.request.user
                        ),
                        reason_category=(
                            reason_category
                        ),
                        reason_text=reason_text,
                    )
                )

        kobo_key = (
            approval
            if approval is not None
            else ApprovalStatusTypes.PENDING
        )
        kobo_uid = (
            ApprovalStatusTypes.KoboStatusMap.get(
                kobo_key
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

        task_kwargs = {}
        if audit:
            task_kwargs["hook"] = (
                "api.v1.v1_odk.tasks"
                ".on_kobo_sync_complete"
            )
            task_kwargs["audit_id"] = audit.pk

        async_task(
            "api.v1.v1_odk.tasks"
            ".sync_kobo_validation_status",
            user.kobo_url,
            user.kobo_username,
            user.kobo_password,
            instance.form.asset_uid,
            [instance.kobo_id],
            kobo_key,
            **task_kwargs,
        )

    @extend_schema(tags=["ODK"])
    @action(detail=False, methods=["get"])
    def latest_sync_time(self, request):
        """Get latest submission_time
        for a form."""
        asset_uid = request.query_params.get(
            "asset_uid"
        )
        if not asset_uid:
            return Response(
                {
                    "message": (
                        "asset_uid is required"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        latest = (
            Submission.objects.filter(
                form__asset_uid=asset_uid
            )
            .order_by("-submission_time")
            .values_list(
                "submission_time", flat=True
            )
            .first()
        )
        return Response(
            {"latest_submission_time": latest}
        )


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
        qs = (
            super()
            .get_queryset()
            .select_related("submission")
        )
        params = self.request.query_params
        form_id = params.get("form_id")
        status_param = params.get("status")
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
                        self.STATUS_MAP[
                            status_param
                        ]
                    )
                )
        search = params.get("search")
        if search:
            qs = qs.filter(
                plot_name__icontains=search
            )
        region = params.get("region")
        if region:
            qs = qs.filter(region=region)
        sub_region = params.get("sub_region")
        if sub_region:
            qs = qs.filter(sub_region=sub_region)
        start_date, end_date = _parse_date_range(
            params
        )
        if start_date is not None:
            qs = qs.filter(
                submission__submission_time__gte=(
                    start_date
                )
            )
        if end_date is not None:
            qs = qs.filter(
                submission__submission_time__lte=(
                    end_date
                )
            )
        sort = params.get("sort")
        if sort == "name":
            qs = qs.order_by("plot_name")
        elif sort == "date":
            qs = qs.order_by("-created_at")
        # Dynamic raw_data filters
        if form_id:
            filter_keys = [
                k
                for k in params
                if k.startswith("filter__")
            ]
            if filter_keys:
                try:
                    form = (
                        FormMetadata.objects.get(
                            asset_uid=form_id
                        )
                    )
                    allowed = (
                        form.filter_fields or []
                    )
                    for key in filter_keys:
                        field = key[
                            len("filter__"):
                        ]
                        if field in allowed:
                            qs = qs.filter(
                                **{
                                    "submission__"
                                    "raw_data__"
                                    f"{field}": (
                                        params[key]
                                    )
                                }
                            )
                except FormMetadata.DoesNotExist:
                    pass
        return qs

    def perform_update(self, serializer):
        instance = serializer.save()
        if (
            "polygon_wkt"
            in serializer.validated_data
        ):
            # Recompute area from new WKT
            from utils.polygon import (
                wkt_to_odk_geoshape,
            )

            odk_str = wkt_to_odk_geoshape(
                instance.polygon_wkt
            )
            instance.area_ha = calculate_area_ha(
                odk_str
            )
            instance.save(
                update_fields=["area_ha"]
            )
            validate_and_check_plot(instance)
            dispatch_kobo_geometry_sync(
                self.request.user,
                instance,
                instance.polygon_wkt,
            )

    @extend_schema(
        request=PlotOverlapQuerySerializer,
        tags=["ODK"],
        summary="Find overlapping plots",
    )
    @action(detail=False, methods=["post"])
    def overlap_candidates(self, request):
        """Find plots whose bounding boxes overlap
        with the given bounds."""
        serializer = PlotOverlapQuerySerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        plots = Plot.objects.filter(
            min_lon__lte=d["max_lon"],
            max_lon__gte=d["min_lon"],
            min_lat__lte=d["max_lat"],
            max_lat__gte=d["min_lat"],
        )
        if d.get("exclude_uuid"):
            plots = plots.exclude(
                uuid=d["exclude_uuid"]
            )

        return Response(
            PlotSerializer(plots, many=True).data
        )

    @extend_schema(
        tags=["ODK"],
        summary=(
            "Reset polygon to original from Kobo"
        ),
    )
    @action(detail=True, methods=["post"])
    def reset_polygon(self, request, uuid=None):
        """Re-derive polygon geometry from the
        linked submission's raw_data."""
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
        plot.polygon_source_field = plot_data[
            "polygon_source_field"
        ]
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
        raw_polygon = plot_data.get(
            "raw_polygon_string"
        )
        plot.area_ha = calculate_area_ha(
            raw_polygon
        )
        plot.save()
        # Re-run overlap detection for valid
        # geometry
        if plot_data["polygon_wkt"]:
            check_and_flag_overlaps(plot)
        dispatch_kobo_geometry_sync(
            request.user, plot, plot.polygon_wkt
        )
        return Response(PlotSerializer(plot).data)

    @extend_schema(
        tags=["Plots"],
        summary="Filter options for dropdowns",
    )
    @action(detail=False, methods=["get"])
    def filter_options(self, request):
        """Return distinct regions, sub_regions, and
        configured dynamic filter options."""
        form_id = request.query_params.get(
            "form_id"
        )
        if not form_id:
            return Response(
                {
                    "detail": (
                        "form_id is required"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            form = FormMetadata.objects.get(
                asset_uid=form_id
            )
        except FormMetadata.DoesNotExist:
            return Response(
                {"detail": "Form not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = Plot.objects.filter(
            form__asset_uid=form_id
        )

        # Build option lookups for region and
        # sub_region fields to resolve raw codes
        option_map, _ = build_option_lookup(form)

        def _resolve_label(raw_val, field_spec):
            """Resolve a raw joined value to
            labels using option lookups."""
            if not raw_val:
                return raw_val
            fields = [
                f.strip()
                for f in (field_spec or "").split(
                    ","
                )
                if f.strip()
            ]
            parts = raw_val.split(" - ")
            resolved = []
            for i, part in enumerate(parts):
                if i < len(fields):
                    opts = option_map.get(
                        fields[i], {}
                    )
                    resolved.append(
                        opts.get(part, part)
                    )
                else:
                    resolved.append(part)
            return " - ".join(resolved)

        raw_regions = list(
            qs.exclude(region="")
            .values_list("region", flat=True)
            .distinct()
            .order_by("region")
        )
        regions = [
            {
                "value": r,
                "label": _resolve_label(
                    r, form.region_field
                ),
            }
            for r in raw_regions
        ]

        sub_region_qs = qs.exclude(sub_region="")
        region = request.query_params.get(
            "region"
        )
        if region:
            sub_region_qs = sub_region_qs.filter(
                region=region
            )
        raw_sub_regions = list(
            sub_region_qs.values_list(
                "sub_region", flat=True
            )
            .distinct()
            .order_by("sub_region")
        )
        sub_regions = [
            {
                "value": w,
                "label": _resolve_label(
                    w, form.sub_region_field
                ),
            }
            for w in raw_sub_regions
        ]

        dynamic_filters = []
        filter_field_names = (
            form.filter_fields or []
        )
        if filter_field_names:
            questions = (
                FormQuestion.objects.filter(
                    form=form,
                    name__in=filter_field_names,
                ).prefetch_related("options")
            )
            for q in questions:
                dynamic_filters.append(
                    {
                        "name": q.name,
                        "label": q.label,
                        "type": q.type,
                        "options": [
                            {
                                "name": o.name,
                                "label": o.label,
                            }
                            for o in (
                                q.options.all()
                            )
                        ],
                    }
                )

        return Response(
            {
                "regions": regions,
                "sub_regions": sub_regions,
                "dynamic_filters": (
                    dynamic_filters
                ),
            }
        )

    @extend_schema(
        tags=["Plots"],
        summary=(
            "Export plots as Shapefile or GeoJSON"
        ),
    )
    @action(detail=False, methods=["post"])
    def export(self, request):
        """Initiate async export of filtered
        plots as Shapefile or GeoJSON."""
        form_id = request.data.get("form_id")
        if not form_id:
            return Response(
                {
                    "message": (
                        "form_id is required"
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        if not FormMetadata.objects.filter(
            asset_uid=form_id
        ).exists():
            return Response(
                {"message": "Form not found"},
                status=(
                    status.HTTP_404_NOT_FOUND
                ),
            )

        fmt = request.data.get("format", "shp")
        valid_formats = {
            "shp": JobTypes.export_shapefile,
            "geojson": JobTypes.export_geojson,
        }
        if fmt not in valid_formats:
            return Response(
                {
                    "message": (
                        "Invalid format. "
                        "Use 'shp' or 'geojson'"
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        filters = {}
        status_param = request.data.get(
            "status"
        )
        if status_param and status_param != "all":
            filters["status"] = status_param
        search = request.data.get("search")
        if search:
            filters["search"] = search
        for f in [
            "region",
            "sub_region",
            "start_date",
            "end_date",
        ]:
            val = request.data.get(f)
            if val:
                filters[f] = val
        dynamic = request.data.get(
            "dynamic_filters"
        )
        if dynamic and isinstance(dynamic, dict):
            filters["dynamic_filters"] = dynamic

        job = Jobs.objects.create(
            type=valid_formats[fmt],
            status=JobStatus.pending,
            created_by=request.user,
            info={
                "form_id": form_id,
                "filters": filters,
            },
        )

        task_id = async_task(
            "api.v1.v1_odk.tasks"
            ".generate_export_file",
            job.id,
            timeout=300,
        )
        job.task_id = task_id
        job.save()

        return Response(
            JobSerializer(job).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Field Settings"])
class FieldSettingsViewSet(
    ListModelMixin,
    GenericViewSet,
):
    """Read-only list of standardized fields."""

    queryset = FieldSettings.objects.all().order_by(
        "pk"
    )
    serializer_class = FieldSettingsSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


@extend_schema(tags=["Field Mappings"])
class FieldMappingViewSet(
    ListModelMixin,
    GenericViewSet,
):
    """List and bulk-upsert field mappings."""

    queryset = FieldMapping.objects.all()
    serializer_class = FieldMappingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        form_id = (
            self.request.query_params.get(
                "form_id"
            )
        )
        if form_id:
            qs = qs.filter(
                form__asset_uid=form_id
            )
        return qs.select_related(
            "field", "form_question"
        )

    @extend_schema(
        summary="Bulk upsert field mappings",
    )
    @action(
        detail=False,
        methods=["put"],
        url_path=r"(?P<asset_uid>[^/.]+)",
    )
    def bulk_upsert(
        self, request, asset_uid=None
    ):
        """Bulk upsert mappings for a form.

        Body: { "field_name": question_id, ... }
        Set question_id to null to delete.
        """
        try:
            form = FormMetadata.objects.get(
                asset_uid=asset_uid
            )
        except FormMetadata.DoesNotExist:
            return Response(
                {"detail": "Form not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data
        if not isinstance(data, dict):
            return Response(
                {
                    "detail": (
                        "Expected a JSON object"
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        errors = {}
        for field_name, q_id in data.items():
            try:
                field_setting = (
                    FieldSettings.objects.get(
                        name=field_name
                    )
                )
            except FieldSettings.DoesNotExist:
                errors[field_name] = (
                    "Unknown field setting"
                )
                continue

            if q_id is None:
                FieldMapping.objects.filter(
                    field=field_setting,
                    form=form,
                ).delete()
                continue

            try:
                question = (
                    FormQuestion.objects.get(
                        pk=q_id, form=form
                    )
                )
            except FormQuestion.DoesNotExist:
                errors[field_name] = (
                    f"Question {q_id} not found"
                )
                continue

            FieldMapping.objects.update_or_create(
                field=field_setting,
                form=form,
                defaults={
                    "form_question": question,
                },
            )

        if errors:
            return Response(
                {"errors": errors},
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        mappings = FieldMapping.objects.filter(
            form=form
        ).select_related(
            "field", "form_question"
        )
        return Response(
            FieldMappingSerializer(
                mappings, many=True
            ).data
        )
