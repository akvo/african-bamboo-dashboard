import re
import time
from datetime import datetime
from datetime import timezone as tz

from django.conf import settings as django_settings
from django.db.models import Count, Q
from django.http import HttpResponse
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
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

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
    check_and_flag_overlaps,
    dispatch_kobo_geometry_sync,
    rederive_plots,
    sync_form_questions,
    validate_and_check_plot,
)
from api.v1.v1_odk.models import (
    Farmer,
    FarmerFieldMapping,
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
    resolve_value,
)
from api.v1.v1_odk.export import _wkt_to_kml
from api.v1.v1_odk.utils.area_calc import (
    calculate_area_ha,
)
from api.v1.v1_odk.utils.farmer_sync import (
    sync_farmers_for_form,
)
from api.v1.v1_odk.utils.warning_rules import (
    evaluate_warnings,
)
from utils.encryption import decrypt
from utils.kobo_client import KoboClient
from utils.polygon import (
    extract_plot_data,
    wkt_to_odk_geoshape,
)


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
        parameters=[
            OpenApiParameter(
                name="is_filter",
                required=False,
                default=False,
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
            ),
        ],
    )
    @action(detail=True, methods=["get"])
    def form_fields(self, request, asset_uid=None):
        """List locally-stored form questions.

        Questions are populated during sync; no
        Kobo API call is needed.
        """
        form = self.get_object()
        qs = FormQuestion.objects.filter(
            form=form
        ).order_by("pk")

        if (
            request.query_params.get("is_filter")
            == "true"
        ):
            excluded = set()
            for spec in [
                form.region_field,
                form.sub_region_field,
                form.plot_name_field,
            ]:
                if spec:
                    for f in spec.split(","):
                        s = f.strip()
                        if s:
                            excluded.add(s)
            if excluded:
                qs = qs.exclude(
                    name__in=excluded
                )

        fields = [
            {
                "name": q.name,
                "type": q.type,
                "label": q.label,
                "full_path": q.name,
            }
            for q in qs
        ]
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
        tags=["Forms"],
        summary=(
            "Get or update farmer field mapping"
        ),
    )
    @action(
        detail=True,
        methods=["get", "put"],
        url_path="farmer-field-mapping",
    )
    def farmer_field_mapping(
        self, request, asset_uid=None
    ):
        """GET: return current mapping.
        PUT: create or update mapping."""
        form = self.get_object()
        if request.method == "GET":
            mapping = FarmerFieldMapping.objects.filter(
                form=form
            ).first()
            if not mapping:
                return Response(
                    {
                        "unique_fields": [],
                        "values_fields": [],
                    }
                )
            return Response(
                {
                    "unique_fields": [
                        f.strip()
                        for f in (
                            mapping.unique_fields
                            .split(",")
                        )
                        if f.strip()
                    ],
                    "values_fields": [
                        f.strip()
                        for f in (
                            mapping.values_fields
                            .split(",")
                        )
                        if f.strip()
                    ],
                }
            )

        # PUT
        raw_unique = request.data.get(
            "unique_fields", []
        )
        raw_values = request.data.get(
            "values_fields", []
        )

        # Validate: must be lists of strings
        if not isinstance(raw_unique, list):
            return Response(
                {
                    "detail": (
                        "unique_fields must be "
                        "a list"
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )
        if not isinstance(raw_values, list):
            return Response(
                {
                    "detail": (
                        "values_fields must be "
                        "a list"
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        # Strip and deduplicate
        unique = list(
            dict.fromkeys(
                s.strip()
                for s in raw_unique
                if isinstance(s, str)
                and s.strip()
            )
        )
        values = list(
            dict.fromkeys(
                s.strip()
                for s in raw_values
                if isinstance(s, str)
                and s.strip()
            )
        )

        if not unique:
            return Response(
                {
                    "detail": (
                        "unique_fields is required"
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        unique_str = ",".join(unique)
        values_str = ",".join(values)

        mapping, _ = (
            FarmerFieldMapping.objects
            .update_or_create(
                form=form,
                defaults={
                    "unique_fields": unique_str,
                    "values_fields": (
                        values_str or unique_str
                    ),
                },
            )
        )
        return Response(
            {
                "unique_fields": [
                    f.strip()
                    for f in (
                        mapping.unique_fields
                        .split(",")
                    )
                    if f.strip()
                ],
                "values_fields": [
                    f.strip()
                    for f in (
                        mapping.values_fields
                        .split(",")
                    )
                    if f.strip()
                ],
            }
        )

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
            # Map Kobo validation status
            vs = item.get(
                "_validation_status", {}
            )
            kobo_uid = (
                vs.get("uid") if vs else None
            )
            approval = (
                ApprovalStatusTypes
                .ReverseKoboStatusMap
                .get(kobo_uid)
                if kobo_uid
                else None
            )

            sub, is_new = (
                Submission.objects.update_or_create(
                    form=form,
                    kobo_id=str(item["_id"]),
                    defaults={
                        "uuid": item["_uuid"],
                        "submission_time": (
                            sub_time_ms
                        ),
                        "submitted_by": item.get(
                            "_submitted_by"
                        ),
                        "instance_name": item.get(
                            "meta/instanceName"
                        ),
                        "approval_status": (
                            approval
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

            # Run warning rules for valid geometry
            warnings = []
            if plot_data["polygon_wkt"]:
                warnings = evaluate_warnings(
                    raw_polygon, area
                )

            # Merge geometry errors + warnings
            all_flags = []
            if plot_data["flagged_reason"]:
                all_flags.extend(
                    plot_data["flagged_reason"]
                )
            if warnings:
                all_flags.extend(warnings)

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
            # Set flags: geometry errors and/or
            # warnings; preserve tri-state when
            # no flags at all.
            if all_flags:
                defaults["flagged_for_review"] = (
                    True
                )
                defaults["flagged_reason"] = (
                    all_flags
                )
            elif plot_data["flagged_for_review"]:
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

        # Sync farmer records from submissions
        farmer_result = sync_farmers_for_form(form)

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
                "farmers_created": (
                    farmer_result["created"]
                ),
                "farmers_updated": (
                    farmer_result["updated"]
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
                Q(type__in=EXCLUDED_QUESTION_TYPES) |
                Q(name__startswith="validate_")
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
                Q(plot_name__icontains=search) |
                Q(submission__instance_name__icontains=search)
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
        summary="Download plot polygon as KML",
    )
    @action(
        detail=True,
        methods=["get"],
        permission_classes=[AllowAny],
    )
    def kml(self, request, uuid=None):
        """Return KML file for a plot polygon.

        Authenticated via ?key=STORAGE_SECRET."""
        key = request.query_params.get("key", "")
        if key != django_settings.STORAGE_SECRET:
            return Response(
                {"detail": "Invalid key"},
                status=status.HTTP_403_FORBIDDEN,
            )
        plot = self.get_object()
        if not plot.polygon_wkt:
            return Response(
                {"detail": "No polygon data"},
                status=(
                    status.HTTP_404_NOT_FOUND
                ),
            )
        name = (
            plot.plot_name
            or str(plot.uuid)
        )
        kml_content = _wkt_to_kml(
            plot.polygon_wkt, name=name
        )
        if not kml_content:
            return Response(
                {"detail": "Invalid geometry"},
                status=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
            )
        # Sanitize filename for header safety
        safe_name = re.sub(
            r'[^\w\s\-.]', '', name
        )[:100].strip() or "plot"
        resp = HttpResponse(
            kml_content,
            content_type=(
                "application/vnd"
                ".google-earth.kml+xml"
            ),
        )
        resp["Content-Disposition"] = (
            "attachment; "
            f'filename="{safe_name}.kml"'
        )
        return resp

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
            "xlsx": JobTypes.export_xlsx,
        }
        if fmt not in valid_formats:
            return Response(
                {
                    "message": (
                        "Invalid format. Use "
                        "'shp', 'geojson', "
                        "or 'xlsx'"
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


@extend_schema(tags=["Farmers"])
class FarmerViewSet(
    ListModelMixin,
    GenericViewSet,
):
    """List farmers with search and plot count."""

    queryset = Farmer.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        form_id = (
            self.request.query_params.get(
                "form_id"
            )
        )
        if form_id:
            qs = qs.filter(
                plots__form__asset_uid=form_id
            ).distinct()
            qs = qs.annotate(
                plot_count=Count(
                    "plots",
                    filter=Q(
                        plots__form__asset_uid=(
                            form_id
                        )
                    ),
                )
            )
        else:
            qs = qs.annotate(
                plot_count=Count("plots")
            )
        search = (
            self.request.query_params.get(
                "search"
            )
        )
        if search:
            qs = qs.filter(
                lookup_key__icontains=search
            )
        return qs.order_by("uid")

    def list(self, request, *args, **kwargs):
        form_id = request.query_params.get(
            "form_id"
        )

        # Get allowed fields from form's
        # FarmerFieldMapping
        allowed_fields = None
        q_labels = {}
        if form_id:
            mapping = (
                FarmerFieldMapping.objects.filter(
                    form__asset_uid=form_id
                ).first()
            )
            if mapping:
                unique = [
                    f.strip()
                    for f in (
                        mapping.unique_fields
                        .split(",")
                    )
                    if f.strip()
                ]
                values = [
                    f.strip()
                    for f in (
                        mapping.values_fields
                        .split(",")
                    )
                    if f.strip()
                ]
                seen = set(unique)
                allowed_fields = list(unique)
                for v in values:
                    if v not in seen:
                        allowed_fields.append(v)
                        seen.add(v)

                # Resolve field labels
                q_labels = dict(
                    FormQuestion.objects.filter(
                        form__asset_uid=form_id,
                        name__in=allowed_fields,
                    ).values_list(
                        "name", "label"
                    )
                )

        qs = self.filter_queryset(
            self.get_queryset()
        )
        page = self.paginate_queryset(qs)
        items = page if page is not None else qs
        data = []
        for f in items:
            all_vals = f.values or {}
            if allowed_fields is not None:
                # Build leaf-name lookup for
                # cross-form key matching
                leaf_map = {}
                for vk in all_vals:
                    leaf = vk.rsplit("/", 1)[-1]
                    leaf_map[leaf] = vk

                vals = {}
                for k in allowed_fields:
                    label = q_labels.get(k, k)
                    leaf = k.rsplit("/", 1)[-1]
                    # Try exact key first, then
                    # match by leaf name
                    val = all_vals.get(k)
                    if val is None:
                        full = leaf_map.get(leaf)
                        if full:
                            val = all_vals.get(
                                full
                            )
                    vals[label] = (
                        val
                        if val is not None
                        else ""
                    )
            else:
                vals = all_vals
            data.append(
                {
                    "id": f.pk,
                    "uid": f.uid,
                    "farmer_id": f"AB{f.uid}",
                    "name": f.lookup_key,
                    "values": vals,
                    "plot_count": f.plot_count,
                }
            )
        if page is not None:
            return self.get_paginated_response(
                data
            )
        return Response(data)


@extend_schema(tags=["Enumerators"])
class EnumeratorViewSet(
    ListModelMixin,
    GenericViewSet,
):
    """List unique enumerators from submissions.

    Enumerators are derived from the enumerator_id
    field in submission raw_data, resolved via
    form question options."""

    queryset = Submission.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = None

    def list(self, request, *args, **kwargs):
        form_id = request.query_params.get(
            "form_id"
        )
        search = request.query_params.get(
            "search"
        )

        qs = Submission.objects.all()
        if form_id:
            qs = qs.filter(
                form__asset_uid=form_id
            )

        # Get unique enumerator_id values
        qs = qs.filter(
            raw_data__enumerator_id__isnull=(
                False
            )
        ).exclude(
            raw_data__enumerator_id=""
        )

        seen = {}
        forms_cache = {}

        for sub in qs.select_related(
            "form"
        ).iterator():
            raw = sub.raw_data or {}
            raw_val = raw.get("enumerator_id")
            if not raw_val:
                continue

            form = sub.form
            form_pk = form.pk
            if form_pk not in forms_cache:
                om, tm = build_option_lookup(
                    form
                )
                forms_cache[form_pk] = (om, tm)
            om, tm = forms_cache[form_pk]

            opts = om.get("enumerator_id")
            if opts:
                resolved = resolve_value(
                    raw_val,
                    opts,
                    tm.get("enumerator_id"),
                )
            else:
                resolved = raw_val

            label = str(resolved).strip()
            key = str(raw_val).strip()
            if key and key not in seen:
                seen[key] = {
                    "code": key,
                    "name": label,
                    "submission_count": 1,
                }
            elif key in seen:
                seen[key][
                    "submission_count"
                ] += 1

        results = sorted(
            seen.values(),
            key=lambda x: x["name"].lower(),
        )

        if search:
            q = search.lower()
            results = [
                r
                for r in results
                if q in r["name"].lower()
            ]

        # Manual pagination
        try:
            limit = max(
                1,
                int(
                    request.query_params.get(
                        "limit", 10
                    )
                ),
            )
        except (ValueError, TypeError):
            limit = 10
        try:
            offset = max(
                0,
                int(
                    request.query_params.get(
                        "offset", 0
                    )
                ),
            )
        except (ValueError, TypeError):
            offset = 0
        total = len(results)
        page = results[offset: offset + limit]

        return Response(
            {
                "count": total,
                "results": page,
            }
        )
