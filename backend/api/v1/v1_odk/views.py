from datetime import datetime
from datetime import timezone as tz

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.v1_odk.models import FormMetadata, Plot, Submission
from api.v1.v1_odk.serializers import (FormMetadataSerializer,
                                       PlotOverlapQuerySerializer,
                                       PlotSerializer,
                                       SubmissionDetailSerializer,
                                       SubmissionListSerializer,
                                       SyncTriggerSerializer)
from utils.encryption import decrypt
from utils.kobo_client import KoboClient


class FormMetadataViewSet(viewsets.ModelViewSet):
    queryset = FormMetadata.objects.all()
    serializer_class = FormMetadataSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SyncTriggerSerializer,
        tags=["ODK"],
        summary="Trigger sync from KoboToolbox",
    )
    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """Fetch submissions from KoboToolbox
        and upsert into local DB."""
        form = self.get_object()
        user = request.user

        if not user.kobo_url or not user.kobo_username:
            return Response(
                {"message": ("No Kobo credentials")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = KoboClient(
            user.kobo_url,
            user.kobo_username,
            decrypt(user.kobo_password),
        )

        since_iso = None
        if form.last_sync_timestamp > 0:
            since_iso = datetime.fromtimestamp(
                form.last_sync_timestamp / 1000,
                tz=tz.utc,
            ).strftime("%Y-%m-%dT%H:%M:%S")

        results = client.fetch_all_submissions(form.asset_uid, since_iso)

        created = 0
        for item in results:
            sub_time_str = item.get("_submission_time", "")
            sub_time_ms = int(
                datetime.fromisoformat(sub_time_str).timestamp() * 1000
            )
            _, is_new = Submission.objects.update_or_create(
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
            }
        )


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Submission.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SubmissionDetailSerializer
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
        """Get latest submission_time for a form."""
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


class PlotViewSet(viewsets.ModelViewSet):
    queryset = Plot.objects.all()
    serializer_class = PlotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        form_id = self.request.query_params.get("form_id")
        is_draft = self.request.query_params.get("is_draft")
        if form_id:
            qs = qs.filter(form_id=form_id)
        if is_draft is not None:
            qs = qs.filter(is_draft=(is_draft.lower() == "true"))
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
