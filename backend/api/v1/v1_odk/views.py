import time
from datetime import datetime
from datetime import timezone as tz

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.mixins import (DestroyModelMixin, ListModelMixin,
                                   RetrieveModelMixin, UpdateModelMixin)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from api.v1.v1_odk.models import FormMetadata, Plot, Submission
from api.v1.v1_odk.serializers import (FormMetadataSerializer,
                                       PlotOverlapQuerySerializer,
                                       PlotSerializer,
                                       SubmissionDetailSerializer,
                                       SubmissionListSerializer,
                                       SubmissionUpdateSerializer,
                                       SyncTriggerSerializer)
from utils.encryption import decrypt
from utils.kobo_client import KoboClient
from utils.polygon import extract_plot_data


@extend_schema(tags=["Forms"])
class FormMetadataViewSet(viewsets.ModelViewSet):
    queryset = FormMetadata.objects.all()
    serializer_class = FormMetadataSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "asset_uid"

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
            if field_type in self.SKIP_FIELD_TYPES:
                continue
            label_list = item.get("label", [])
            label = (
                label_list[0]
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

        for item in results:
            sub_time_str = item.get("_submission_time", "")
            sub_time_ms = int(
                datetime.fromisoformat(
                    sub_time_str
                ).timestamp()
                * 1000
            )
            sub, is_new = Submission.objects.update_or_create(
                uuid=item["_uuid"],
                defaults={
                    "form": form,
                    "kobo_id": str(item["_id"]),
                    "submission_time": (sub_time_ms),
                    "submitted_by": item.get("_submitted_by"),
                    "instance_name": item.get("meta/instanceName"),
                    "raw_data": item,
                    "system_data": {
                        "_geolocation": (item.get("_geolocation")),
                        "_tags": item.get("_tags", []),
                    },
                },
            )
            if is_new:
                created += 1

            # Auto-generate plot
            plot_data = extract_plot_data(item, form)
            now_ms = int(time.time() * 1000)
            _, plot_is_new = Plot.objects.update_or_create(
                submission=sub,
                defaults={
                    "form": form,
                    "plot_name": (plot_data["plot_name"]),
                    "instance_name": (
                        item.get(
                            "meta/instanceName",
                            "",
                        )
                    ),
                    "polygon_wkt": (plot_data["polygon_wkt"]),
                    "min_lat": (plot_data["min_lat"]),
                    "max_lat": (plot_data["max_lat"]),
                    "min_lon": (plot_data["min_lon"]),
                    "max_lon": (plot_data["max_lon"]),
                    "region": (plot_data["region"]),
                    "sub_region": (plot_data["sub_region"]),
                    "created_at": now_ms,
                },
            )
            if plot_is_new:
                plots_created += 1
            else:
                plots_updated += 1

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

    def get_queryset(self):
        qs = super().get_queryset()
        asset_uid = self.request.query_params.get("asset_uid")
        if asset_uid:
            qs = qs.filter(form__asset_uid=asset_uid)
        return qs

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

    def get_queryset(self):
        qs = super().get_queryset()
        form_id = self.request.query_params.get("form_id")
        approval_status = self.request.query_params.get("status")
        if form_id:
            qs = qs.filter(form__asset_uid=form_id)
        if approval_status is not None:
            if approval_status == "pending":
                qs = qs.filter(submission__approval_status__isnull=True)  # noqa: E501
            else:
                qs = qs.filter(
                    submission__approval_status=approval_status  # noqa: E501
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
