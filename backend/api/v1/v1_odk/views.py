import logging
import time
from datetime import datetime
from datetime import timezone as tz

from django.db.models import (
    Exists,
    F,
    OuterRef,
    Q,
    Subquery,
)
from django.db.models.fields.json import (
    KeyTextTransform,
)
from django.utils import timezone
from django_q.tasks import async_task
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)
from requests.exceptions import RequestException
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.mixins import (
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
    EXCLUDED_QUESTION_TYPES,
    STATUS_MAP,
    ALLOWED_ORDERINGS,
)
from api.v1.v1_odk.funcs import (
    MAPPING_FIELDS,
    check_and_flag_overlaps,
    parse_date_range,
    parse_field_spec,
    rederive_plots,
    strip_id_prefix,
    sync_form_questions,
    validate_and_check_plot,
)
from api.v1.v1_odk.models import (
    FarmerFieldMapping,
    FieldMapping,
    FieldSettings,
    FormMetadata,
    FormOption,
    FormQuestion,
    MainPlotSubmission,
    Plot,
    RejectionAudit,
    Submission,
)
from api.v1.v1_odk.serializers import (
    FieldMappingSerializer,
    FieldSettingsSerializer,
    FormMetadataSerializer,
    SubmissionDetailSerializer,
    SubmissionEditDataSerializer,
    SubmissionListSerializer,
    SubmissionUpdateSerializer,
    SyncTriggerSerializer,
    build_option_lookup,
)
from api.v1.v1_odk.utils.area_calc import (
    calculate_area_ha,
)
from api.v1.v1_odk.utils.farmer_sync import (
    update_farmer_for_submission,
)
from api.v1.v1_odk.utils.plot_id import (
    create_main_plot_for_submission,
    unlink_main_plot_submission,
)
from api.v1.v1_odk.utils.warning_rules import (
    evaluate_warnings,
)
from utils.encryption import decrypt
from utils.kobo_client import (
    KoboClient,
    KoboUnauthorizedError,
)
from utils.polygon import extract_plot_data

logger = logging.getLogger(__name__)


def _has_kobo_credentials(user):
    """Check if user has Kobo credentials."""
    return (
        user.kobo_url
        and user.kobo_username
        and user.kobo_password
    )


@extend_schema(tags=["Forms"])
class FormMetadataViewSet(viewsets.ModelViewSet):
    queryset = FormMetadata.objects.all()
    serializer_class = FormMetadataSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "asset_uid"

    def _make_kobo_client(self, user):
        if not _has_kobo_credentials(user):
            return None
        return KoboClient(
            user.kobo_url,
            user.kobo_username,
            decrypt(user.kobo_password),
        )

    def _try_sync_questions(self, form, user):
        """Fetch form structure from Kobo and
        populate FormQuestion/FormOption.

        Logs and suppresses network errors so the
        caller can proceed without questions.
        """
        client = self._make_kobo_client(user)
        if client is None:
            return
        try:
            content = client.get_asset_detail(
                form.asset_uid
            )
            sync_form_questions(form, content)
        except (
            RequestException,
            KoboUnauthorizedError,
        ):
            logger.warning(
                "Sync questions failed for %s",
                form.asset_uid,
                exc_info=True,
            )

    def perform_create(self, serializer):
        instance = serializer.save()
        self._try_sync_questions(
            instance, self.request.user
        )

    def perform_update(self, serializer):
        form = self.get_object()
        old = {f: getattr(form, f) for f in MAPPING_FIELDS}
        instance = serializer.save()
        changed = any(getattr(instance, f) != old[f] for f in MAPPING_FIELDS)
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

        If no questions exist yet, attempts a
        one-time fetch from KoboToolbox.
        """
        form = self.get_object()

        if not FormQuestion.objects.filter(
            form=form
        ).exists():
            self._try_sync_questions(
                form, request.user
            )

        qs = FormQuestion.objects.filter(form=form).order_by("pk")

        if request.query_params.get("is_filter") == "true":
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
                qs = qs.exclude(name__in=excluded)

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
    def form_questions(self, request, asset_uid=None):
        """Return FormQuestion records stored in DB
        for a given form, including their IDs."""
        form = self.get_object()
        qs = (
            FormQuestion.objects.filter(form=form)
            .prefetch_related("options")
            .order_by("pk")
        )
        data = []
        for q in qs:
            item = {
                "id": q.pk,
                "name": q.name,
                "label": q.label,
                "type": q.type,
            }
            if q.type.startswith("select_"):
                item["options"] = [
                    {
                        "name": o.name,
                        "label": o.label,
                    }
                    for o in q.options.all()
                ]
            data.append(item)
        return Response(data)

    @extend_schema(
        tags=["Forms"],
        summary=("Get or update farmer field mapping"),
    )
    @action(
        detail=True,
        methods=["get", "put"],
        url_path="farmer-field-mapping",
    )
    def farmer_field_mapping(self, request, asset_uid=None):
        """GET: return current mapping.
        PUT: create or update mapping."""
        form = self.get_object()
        if request.method == "GET":
            mapping = (
                FarmerFieldMapping.objects
                .filter(form=form)
                .first()
            )
            if not mapping:
                return Response(
                    {
                        "unique_fields": [],
                        "values_fields": [],
                        "uid_start": 1,
                    }
                )
            return Response(
                self._serialize_farmer_mapping(
                    mapping
                )
            )

        # PUT
        raw_unique = request.data.get(
            "unique_fields", []
        )
        raw_values = request.data.get(
            "values_fields", []
        )

        for name, val in [
            ("unique_fields", raw_unique),
            ("values_fields", raw_values),
        ]:
            if not isinstance(val, list):
                return Response(
                    {
                        "detail": (
                            f"{name} must be a list"
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

        # Validate uid_start (optional)
        raw_uid_start = request.data.get(
            "uid_start", None
        )
        uid_start = 1
        if raw_uid_start is not None:
            try:
                uid_start = int(raw_uid_start)
                if uid_start < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return Response(
                    {
                        "detail": (
                            "uid_start must be a "
                            "positive integer"
                        )
                    },
                    status=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                )

        mapping, _ = (
            FarmerFieldMapping.objects
            .update_or_create(
                form=form,
                defaults={
                    "unique_fields": unique_str,
                    "values_fields": (
                        values_str or unique_str
                    ),
                    "uid_start": uid_start,
                },
            )
        )
        return Response(
            self._serialize_farmer_mapping(
                mapping
            )
        )

    @staticmethod
    def _serialize_farmer_mapping(mapping):
        """Serialize a FarmerFieldMapping to dict."""
        return {
            "unique_fields": parse_field_spec(
                mapping.unique_fields
            ),
            "values_fields": parse_field_spec(
                mapping.values_fields
            ),
            "uid_start": mapping.uid_start,
        }

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
            questions_synced = sync_form_questions(form, content)
        except KoboUnauthorizedError:
            return Response(
                {
                    "message": (
                        "KoboToolbox credentials are "
                        "invalid or expired. Please "
                        "log in again."
                    ),
                    "error_type": "kobo_unauthorized",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"message": (f"Error syncing form " f"questions: {str(e)}")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        since_iso = None
        if form.last_sync_timestamp > 0:
            since_iso = datetime.fromtimestamp(
                form.last_sync_timestamp / 1000,
                tz=tz.utc,
            ).strftime("%Y-%m-%dT%H:%M:%S")

        try:
            results = client.fetch_all_submissions(form.asset_uid, since_iso)
        except KoboUnauthorizedError:
            return Response(
                {
                    "message": (
                        "KoboToolbox credentials are "
                        "invalid or expired. Please "
                        "log in again."
                    ),
                    "error_type": "kobo_unauthorized",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        counts = {
            "created": 0,
            "plots_created": 0,
            "plots_updated": 0,
            "plots_flagged": 0,
        }

        for item in results:
            sub, is_new = self._upsert_submission(
                form, item
            )
            if is_new:
                counts["created"] += 1
            self._upsert_plot(
                form, sub, item, counts
            )
            self._queue_attachment_download(
                request.user, item, sub
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
                counts["plots_flagged"] += 1

        # Sync farmer records asynchronously
        async_task(
            "api.v1.v1_odk.utils.farmer_sync"
            ".sync_farmers_for_form",
            form,
        )

        return Response(
            {
                "synced": len(results),
                "questions_synced": (
                    questions_synced
                ),
                **counts,
            }
        )

    def _upsert_submission(self, form, item):
        """Upsert a single Kobo submission."""
        sub_time_str = item.get(
            "_submission_time", ""
        )
        sub_time_ms = int(
            datetime.fromisoformat(
                sub_time_str
            ).timestamp()
            * 1000
        )
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
        return Submission.objects.update_or_create(
            form=form,
            kobo_id=str(item["_id"]),
            defaults={
                "uuid": item["_uuid"],
                "submission_time": sub_time_ms,
                "submitted_by": item.get(
                    "_submitted_by"
                ),
                "instance_name": item.get(
                    "meta/instanceName"
                ),
                "approval_status": approval,
                "raw_data": item,
                "system_data": {
                    "_geolocation": item.get(
                        "_geolocation"
                    ),
                    "_tags": item.get(
                        "_tags", []
                    ),
                },
            },
        )

    def _upsert_plot(self, form, sub, item, counts):
        """Create/update plot from submission data
        with geometry validation and overlap check."""
        plot_data = extract_plot_data(item, form)
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
            "plot_name": plot_data["plot_name"],
            "polygon_source_field": plot_data[
                "polygon_source_field"
            ],
            "polygon_wkt": plot_data[
                "polygon_wkt"
            ],
            "min_lat": plot_data["min_lat"],
            "max_lat": plot_data["max_lat"],
            "min_lon": plot_data["min_lon"],
            "max_lon": plot_data["max_lon"],
            "region": plot_data["region"],
            "sub_region": plot_data["sub_region"],
            "area_ha": area,
            "created_at": int(
                time.time() * 1000
            ),
        }
        if all_flags:
            defaults["flagged_for_review"] = True
            defaults["flagged_reason"] = all_flags
        elif plot_data["flagged_for_review"]:
            defaults["flagged_for_review"] = True
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
            counts["plots_created"] += 1
        else:
            counts["plots_updated"] += 1

        if plot_data["polygon_wkt"]:
            check_and_flag_overlaps(plot)
        if plot.flagged_for_review:
            counts["plots_flagged"] += 1

    def _queue_attachment_download(
        self, user, item, sub
    ):
        """Queue async download of image
        attachments from Kobo."""
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
                user.kobo_url,
                user.kobo_username,
                user.kobo_password,
                str(sub.uuid),
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

    def _get_form_by_uid(self, asset_uid):
        """Fetch FormMetadata by asset_uid,
        return None if not found."""
        try:
            return FormMetadata.objects.get(
                asset_uid=asset_uid
            )
        except FormMetadata.DoesNotExist:
            return None

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.action == "list":
            asset_uid = (
                self.request.query_params.get(
                    "asset_uid"
                )
            )
            form = (
                self._get_form_by_uid(asset_uid)
                if asset_uid
                else None
            )
            if form:
                om, tm = build_option_lookup(form)
                ctx["option_lookup"] = om
                ctx["type_map"] = tm
                ctx["question_names"] = {
                    q["name"]
                    for q in (
                        self._get_form_questions(
                            form
                        )
                    )
                }
        return ctx

    def _get_form_questions(self, form):
        """Return displayable form questions,
        excluding mapped and system fields."""
        mapped_fields = set()
        for spec in [
            form.region_field,
            form.sub_region_field,
        ]:
            mapped_fields.update(
                parse_field_spec(spec)
            )
        qs = (
            FormQuestion.objects.filter(form=form)
            .exclude(
                Q(
                    type__in=(
                        EXCLUDED_QUESTION_TYPES
                    )
                )
                | Q(name__startswith="validate_")
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
        form = (
            self._get_form_by_uid(asset_uid)
            if asset_uid
            else None
        )
        if form:
            response.data["questions"] = (
                self._get_form_questions(form)
            )
            response.data["sortable_fields"] = (
                form.sortable_fields or []
            )
        else:
            response.data["questions"] = []
            response.data["sortable_fields"] = []
        return response

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related(
            "main_plot_submission__main_plot"
        )
        params = self.request.query_params
        asset_uid = params.get("asset_uid")
        if asset_uid:
            qs = qs.filter(form__asset_uid=asset_uid)
        status_param = params.get("status")
        if status_param is not None:
            if status_param == "pending":
                qs = qs.filter(approval_status__isnull=True)
            elif status_param in STATUS_MAP:
                qs = qs.filter(approval_status=(STATUS_MAP[status_param]))
        region = params.get("region")
        if region:
            qs = qs.filter(plot__region=region)
        sub_region = params.get("sub_region")
        if sub_region:
            qs = qs.filter(plot__sub_region=sub_region)
        search = params.get("search")
        if search:
            stripped = strip_id_prefix(search)
            plot_uid_match = Exists(
                MainPlotSubmission.objects.filter(
                    submission=OuterRef("pk"),
                    main_plot__uid__icontains=(
                        stripped
                    ),
                )
            )
            qs = qs.filter(
                Q(
                    instance_name__icontains=search
                )
                | Q(kobo_id__icontains=stripped)
                | Q(plot_uid_match)
            )
        start_date, end_date = parse_date_range(params)
        if start_date is not None:
            qs = qs.filter(submission_time__gte=start_date)
        if end_date is not None:
            qs = qs.filter(submission_time__lte=end_date)
        # Dynamic raw_data filters
        if asset_uid:
            qs = self._apply_dynamic_filters(qs, params, asset_uid)
        # Sorting
        qs = qs.annotate(
            sort_start=KeyTextTransform("start", "raw_data"),
            sort_end=KeyTextTransform("end", "raw_data"),
        )
        ordering = params.get("ordering")
        if ordering:
            desc = ordering.startswith("-")
            field = ordering.lstrip("-")
            orm_field = ALLOWED_ORDERINGS.get(field)
            if orm_field:
                expr = F(orm_field)
                if desc:
                    expr = expr.desc(nulls_last=True)
                else:
                    expr = expr.asc(nulls_last=True)
                qs = qs.order_by(
                    expr,
                    "-submission_time",
                    "pk",
                )
            elif asset_uid:
                qs = self._apply_dynamic_ordering(qs, asset_uid, field, desc)
        return qs

    def _apply_dynamic_ordering(self, qs, asset_uid, field, desc):
        try:
            form = FormMetadata.objects.get(asset_uid=asset_uid)
        except FormMetadata.DoesNotExist:
            return qs
        allowed = form.sortable_fields or []
        if field not in allowed:
            return qs
        ann_key = f"sort_dyn_{field}"
        qs = qs.annotate(**{ann_key: KeyTextTransform(field, "raw_data")})
        sort_key = ann_key
        # For select_one fields, sort by resolved
        # option label instead of raw option name
        question = FormQuestion.objects.filter(
            form=form,
            name=field,
            type="select_one",
        ).first()
        if question:
            label_key = f"sort_label_{field}"
            qs = qs.annotate(
                **{
                    label_key: Subquery(
                        FormOption.objects.filter(
                            question=question,
                            name=OuterRef(ann_key),
                        ).values("label")[:1]
                    )
                }
            )
            sort_key = label_key
        expr = F(sort_key)
        if desc:
            expr = expr.desc(nulls_last=True)
        else:
            expr = expr.asc(nulls_last=True)
        return qs.order_by(expr, "-submission_time", "pk")

    def _apply_dynamic_filters(self, qs, params, asset_uid):
        filter_keys = [k for k in params if k.startswith("filter__")]
        if not filter_keys:
            return qs
        try:
            form = FormMetadata.objects.get(asset_uid=asset_uid)
        except FormMetadata.DoesNotExist:
            return qs
        allowed = form.filter_fields or []
        for key in filter_keys:
            field_name = \
                key[len("filter__"):]
            if field_name in allowed:
                qs = qs.filter(**{f"raw_data__{field_name}": (params[key])})
        return qs

    def perform_update(self, serializer):
        reason_category = serializer.validated_data.get("reason_category")
        reason_text = serializer.validated_data.get("reason_text", "")
        instance = serializer.save(
            updated_by=self.request.user,
            updated_at=timezone.now(),
        )
        approval = instance.approval_status

        # Generate Plot ID on approval
        if approval == ApprovalStatusTypes.APPROVED:
            create_main_plot_for_submission(instance)

        # Unlink Plot ID on revert or rejection
        if approval is None or (
            approval == ApprovalStatusTypes.REJECTED
        ):
            unlink_main_plot_submission(instance)

        # Re-check polygon & overlaps on revert
        if approval is None:
            plot = getattr(instance, "plot", None)
            if plot:
                validate_and_check_plot(plot)

        # Create RejectionAudit for rejections
        audit = None
        if approval == ApprovalStatusTypes.REJECTED and reason_category:
            plot = getattr(instance, "plot", None)
            if plot:
                audit = RejectionAudit.objects.create(
                    plot=plot,
                    submission=instance,
                    validator=(self.request.user),
                    reason_category=(reason_category),
                    reason_text=reason_text,
                )

        kobo_key = approval \
            if approval is not None else ApprovalStatusTypes.PENDING
        kobo_uid = ApprovalStatusTypes.KoboStatusMap.get(kobo_key)
        if not kobo_uid:
            return
        user = self.request.user
        if not _has_kobo_credentials(user):
            return

        task_kwargs = {}
        if audit:
            task_kwargs["hook"] = "api.v1.v1_odk.tasks"\
                ".on_kobo_sync_complete"
            task_kwargs["audit_id"] = audit.pk

        async_task(
            "api.v1.v1_odk.tasks" ".sync_kobo_validation_status",
            user.kobo_url,
            user.kobo_username,
            user.kobo_password,
            instance.form.asset_uid,
            [instance.kobo_id],
            kobo_key,
            **task_kwargs,
        )

    @extend_schema(
        tags=["Submissions"],
        summary="Edit submission field data",
        request=SubmissionEditDataSerializer,
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path="edit_data",
    )
    def edit_data(self, request, uuid=None):
        """Edit submission raw_data fields and
        sync changes to KoboToolbox."""
        submission = self.get_object()
        serializer = SubmissionEditDataSerializer(
            data=request.data,
            context={
                "submission": submission,
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)
        fields = (
            serializer.validated_data["fields"]
        )

        raw = submission.raw_data or {}
        raw.update(fields)
        submission.raw_data = raw
        submission.updated_by = request.user
        submission.updated_at = timezone.now()
        submission.save(
            update_fields=[
                "raw_data",
                "updated_by",
                "updated_at",
            ]
        )

        plot = getattr(submission, "plot", None)
        if plot:
            self._update_plot_from_edit(
                plot, submission, fields
            )

        self._resync_farmers_if_needed(
            submission, fields
        )

        self._sync_edit_to_kobo(
            request.user, submission, fields
        )

        detail_serializer = (
            SubmissionDetailSerializer(submission)
        )
        return Response(detail_serializer.data)

    def _update_plot_from_edit(
        self, plot, submission, fields
    ):
        """Update Plot.region/sub_region/plot_name
        if corresponding raw_data fields changed."""
        form = submission.form
        raw = submission.raw_data or {}

        # (plot_attr, form_spec, joiner, empty)
        field_map = [
            (
                "region",
                form.region_field,
                " - ",
                "",
            ),
            (
                "sub_region",
                form.sub_region_field,
                " - ",
                "",
            ),
            (
                "plot_name",
                form.plot_name_field,
                " ",
                None,
            ),
        ]

        update_fields = []
        for attr, spec, sep, empty in field_map:
            names = parse_field_spec(spec)
            if not any(f in fields for f in names):
                continue
            vals = [
                str(raw.get(f, ""))
                for f in names
                if raw.get(f)
            ]
            setattr(
                plot,
                attr,
                sep.join(vals) if vals else empty,
            )
            update_fields.append(attr)

        if update_fields:
            plot.save(
                update_fields=update_fields
            )

    def _resync_farmers_if_needed(
        self, submission, fields
    ):
        """Update farmer record if any
        farmer-related fields were edited.

        Uses targeted update_farmer_for_submission
        instead of full sync_farmers_for_form to
        preserve the existing Plot.farmer
        relationship and avoid generating new
        farmer UIDs on name changes."""
        form = submission.form
        farmer_mapping = (
            form.farmer_field_mapping.first()
        )
        if not farmer_mapping:
            return
        all_farmer_q_names = set(
            parse_field_spec(
                farmer_mapping.unique_fields
            )
            + parse_field_spec(
                farmer_mapping.values_fields
            )
        )
        if all_farmer_q_names & set(fields.keys()):
            update_farmer_for_submission(
                form, submission
            )

    def _sync_edit_to_kobo(
        self, user, submission, fields
    ):
        """Queue async task to push field edits
        to KoboToolbox."""
        if not _has_kobo_credentials(user):
            return
        async_task(
            "api.v1.v1_odk.tasks"
            ".sync_kobo_submission_data",
            user.kobo_url,
            user.kobo_username,
            user.kobo_password,
            submission.form.asset_uid,
            submission.kobo_id,
            fields,
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


@extend_schema(tags=["Field Settings"])
class FieldSettingsViewSet(
    ListModelMixin,
    GenericViewSet,
):
    """Read-only list of standardized fields."""

    queryset = FieldSettings.objects.all().order_by("pk")
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
        form_id = self.request.query_params.get("form_id")
        if form_id:
            qs = qs.filter(form__asset_uid=form_id)
        return qs.select_related("field", "form_question")

    @extend_schema(
        summary="Bulk upsert field mappings",
    )
    @action(
        detail=False,
        methods=["put"],
        url_path=r"(?P<asset_uid>[^/.]+)",
    )
    def bulk_upsert(self, request, asset_uid=None):
        """Bulk upsert mappings for a form.

        Body: { "field_name": question_id, ... }
        Set question_id to null to delete.
        """
        try:
            form = FormMetadata.objects.get(asset_uid=asset_uid)
        except FormMetadata.DoesNotExist:
            return Response(
                {"detail": "Form not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"detail": ("Expected a JSON object")},
                status=(status.HTTP_400_BAD_REQUEST),
            )

        errors = {}
        for field_name, q_id in data.items():
            try:
                field_setting = FieldSettings.objects.get(name=field_name)
            except FieldSettings.DoesNotExist:
                errors[field_name] = "Unknown field setting"
                continue

            if q_id is None:
                FieldMapping.objects.filter(
                    field=field_setting,
                    form=form,
                ).delete()
                continue

            try:
                question = FormQuestion.objects.get(pk=q_id, form=form)
            except FormQuestion.DoesNotExist:
                errors[field_name] = f"Question {q_id} not found"
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
                status=(status.HTTP_400_BAD_REQUEST),
            )

        mappings = FieldMapping.objects.filter(form=form).select_related(
            "field", "form_question"
        )
        return Response(FieldMappingSerializer(mappings, many=True).data)
