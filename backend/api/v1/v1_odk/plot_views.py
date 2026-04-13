import logging
import re

from django.conf import settings as django_settings
from django.db.models import (
    Count,
    Exists,
    OuterRef,
    Q,
    Sum,
)
from django.http import HttpResponse
from django_q.tasks import async_task
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
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

from api.v1.v1_jobs.constants import (
    JobStatus,
    JobTypes,
)
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_jobs.serializers import JobSerializer
from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.export import _wkt_to_kml
from api.v1.v1_odk.funcs import (
    check_and_flag_overlaps,
    dispatch_kobo_geometry_sync,
    parse_date_range,
    strip_id_prefix,
    validate_and_check_plot,
)
from api.v1.v1_odk.models import (
    Farmer,
    FarmerFieldMapping,
    FormMetadata,
    FormQuestion,
    MainPlotSubmission,
    Plot,
    Submission,
)
from api.v1.v1_odk.serializers import (
    PlotOverlapQuerySerializer,
    PlotSerializer,
    StatsSerializer,
    build_option_lookup,
    resolve_value,
)
from api.v1.v1_odk.utils.area_calc import (
    calculate_area_ha,
)
from utils.polygon import (
    extract_plot_data,
    wkt_to_odk_geoshape,
)

logger = logging.getLogger(__name__)


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
            .prefetch_related(
                "submission__"
                "main_plot_submission__"
                "main_plot"
            )
        )
        params = self.request.query_params
        form_id = params.get("form_id")
        status_param = params.get("status")
        if form_id:
            qs = qs.filter(form__asset_uid=form_id)
        if status_param is not None:
            if status_param == "flagged":
                qs = qs.filter(
                    flagged_for_review=True
                )
            elif status_param == "pending":
                qs = qs.filter(
                    Q(
                        submission__approval_status__isnull=True  # noqa: E501
                    )
                    | Q(
                        submission__approval_status=(  # noqa: E501
                            ApprovalStatusTypes.PENDING
                        )
                    )
                )
            elif status_param in self.STATUS_MAP:
                qs = qs.filter(
                    submission__approval_status=(
                        self.STATUS_MAP[status_param]
                    )
                )
        search = params.get("search")
        if search:
            stripped = strip_id_prefix(search)
            plot_uid_match = Exists(
                MainPlotSubmission.objects.filter(
                    submission=OuterRef(
                        "submission_id"
                    ),
                    main_plot__uid__icontains=(
                        stripped
                    ),
                )
            )
            qs = qs.filter(
                Q(
                    submission__instance_name__icontains=search  # noqa: E501
                )
                | Q(
                    submission__kobo_id__icontains=stripped  # noqa: E501
                )
                | Q(plot_uid_match)
            )
        region = params.get("region")
        if region:
            qs = qs.filter(region=region)
        sub_region = params.get("sub_region")
        if sub_region:
            qs = qs.filter(sub_region=sub_region)
        start_date, end_date = parse_date_range(
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
            qs = qs.order_by(
                "-submission__submission_time"
            )
        else:
            qs = qs.order_by(
                "-submission__submission_time"
            )
        # Dynamic raw_data filters
        if form_id:
            filter_keys = [
                k
                for k in params
                if k.startswith("filter__")
            ]
            if filter_keys:
                try:
                    form = FormMetadata.objects.get(
                        asset_uid=form_id
                    )
                    allowed = (
                        form.filter_fields or []
                    )
                    for key in filter_keys:
                        field = key[len("filter__"):]
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
        if "polygon_wkt" in serializer.validated_data:
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
        name = plot.plot_name or str(plot.uuid)
        kml_content = _wkt_to_kml(
            plot.polygon_wkt, name=name
        )
        if not kml_content:
            return Response(
                {"detail": "Invalid geometry"},
                status=(
                    status
                    .HTTP_422_UNPROCESSABLE_ENTITY
                ),
            )
        # Sanitize filename for header safety
        safe_name = (
            re.sub(r"[^\w\s\-.]", "", name)[
                :100
            ].strip()
            or "plot"
        )
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
            labels using option lookups.

            When positional lookup fails (the
            stored value has fewer parts than
            fields because empty fields were
            skipped), try all fields' options
            as fallback.
            """
            if not raw_val:
                return raw_val
            fields = [
                f.strip()
                for f in (
                    field_spec or ""
                ).split(",")
                if f.strip()
            ]
            parts = raw_val.split(" - ")
            resolved = []
            for i, part in enumerate(parts):
                label = part
                if i < len(fields):
                    opts = option_map.get(
                        fields[i], {}
                    )
                    label = opts.get(part, part)
                # Fallback: if positional lookup
                # returned the raw code, search
                # all fields in the spec.
                if label == part:
                    for f in fields:
                        opts = option_map.get(
                            f, {}
                        )
                        if part in opts:
                            label = opts[part]
                            break
                resolved.append(label)
            return " - ".join(resolved)

        raw_regions = list(
            qs.exclude(region="")
            .values_list("region", flat=True)
            .distinct()
            .order_by("region")
        )
        regions = sorted(
            [
                {
                    "value": r,
                    "label": _resolve_label(
                        r, form.region_field
                    ),
                }
                for r in raw_regions
            ],
            key=lambda x: x["label"],
        )

        sub_region_qs = qs.exclude(sub_region="")
        region = request.query_params.get("region")
        if region:
            sub_region_qs = (
                sub_region_qs.filter(region=region)
            )
        raw_sub_regions = list(
            sub_region_qs.values_list(
                "sub_region", flat=True
            )
            .distinct()
            .order_by("sub_region")
        )
        sub_regions = sorted(
            [
                {
                    "value": w,
                    "label": _resolve_label(
                        w, form.sub_region_field
                    ),
                }
                for w in raw_sub_regions
            ],
            key=lambda x: x["label"],
        )

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
                        "options": sorted(
                            [
                                {
                                    "name": o.name,
                                    "label": (
                                        o.label
                                    ),
                                }
                                for o in (
                                    q.options.all()
                                )
                            ],
                            key=lambda x: (
                                x["label"]
                            ),
                        ),
                    }
                )

        response_data = {
            "regions": regions,
            "sub_regions": sub_regions,
            "dynamic_filters": dynamic_filters,
        }

        all_eligible = (
            request.query_params.get(
                "all_eligible"
            )
            == "true"
        )
        if all_eligible:
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
            eligible_qs = (
                FormQuestion.objects.filter(
                    form=form,
                    type__startswith="select_",
                )
                .exclude(name__in=excluded)
                .prefetch_related("options")
                .order_by("label")
            )
            available = []
            for q in eligible_qs:
                available.append(
                    {
                        "name": q.name,
                        "label": q.label,
                        "type": q.type,
                        "options": sorted(
                            [
                                {
                                    "name": o.name,
                                    "label": (
                                        o.label
                                    ),
                                }
                                for o in (
                                    q.options
                                    .all()
                                )
                            ],
                            key=lambda x: (
                                x["label"]
                            ),
                        ),
                    }
                )
            response_data[
                "available_filters"
            ] = available

        return Response(response_data)

    @extend_schema(
        tags=["Plots"],
        summary="Dashboard statistics",
        responses=StatsSerializer,
    )
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Aggregate stats for dashboard cards.

        Reuses get_queryset() so all filters
        (form_id, region, sub_region, date range,
        dynamic filters) are applied."""
        qs = self.get_queryset().order_by()

        pending_q = Q(
            submission__approval_status__isnull=True  # noqa: E501
        ) | Q(
            submission__approval_status=(
                ApprovalStatusTypes.PENDING
            )
        )

        approved_q = Q(
            submission__approval_status=(
                ApprovalStatusTypes.APPROVED
            )
        )

        result = qs.aggregate(
            total_plots=Count("id", distinct=True),
            total_area_ha=Sum("area_ha"),
            approved_count=Count(
                "id",
                filter=approved_q,
                distinct=True,
            ),
            pending_count=Count(
                "id",
                filter=pending_q,
                distinct=True,
            ),
            pending_area_ha=Sum(
                "area_ha",
                filter=pending_q,
            ),
        )

        approved_area_ha = (
            qs.filter(approved_q).aggregate(
                total=Sum("area_ha")
            )["total"]
            or 0
        )

        total = result["total_plots"] or 0
        approved = result["approved_count"] or 0
        approval_pct = (
            round(approved / total * 100, 1)
            if total > 0
            else 0
        )

        serializer = StatsSerializer(
            data={
                "total_plots": total,
                "total_area_ha": round(
                    result["total_area_ha"] or 0,
                    2,
                ),
                "approval_percentage": approval_pct,
                "approved_area_ha": round(
                    approved_area_ha, 2
                ),
                "pending_count": (
                    result["pending_count"] or 0
                ),
                "pending_area_ha": round(
                    result["pending_area_ha"] or 0,
                    2,
                ),
            }
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)

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
        status_param = request.data.get("status")
        if (
            status_param
            and status_param != "all"
        ):
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
            stripped = strip_id_prefix(search)
            qs = qs.filter(
                Q(
                    lookup_key__icontains=search
                )
                | Q(uid__icontains=stripped)
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
                    ).values_list("name", "label")
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
        ).exclude(raw_data__enumerator_id="")

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
                om, tm = build_option_lookup(form)
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
