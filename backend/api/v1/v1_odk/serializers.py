from rest_framework import serializers

from api.v1.v1_odk.models import FormMetadata, Plot, Submission
from utils.custom_serializer_fields import CustomCharField, CustomFloatField


class FormMetadataSerializer(serializers.ModelSerializer):
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = FormMetadata
        fields = [
            "asset_uid",
            "name",
            "last_sync_timestamp",
            "submission_count",
        ]

    def get_submission_count(self, obj):
        return obj.submissions.count()


class SubmissionListSerializer(serializers.ModelSerializer):
    """Lightweight list — excludes raw_data."""
    region = serializers.CharField(source="raw_data.region", read_only=True)
    woreda = serializers.CharField(source="raw_data.woreda", read_only=True)

    class Meta:
        model = Submission
        fields = [
            "uuid",
            "form",
            "kobo_id",
            "submission_time",
            "submitted_by",
            "instance_name",
            "region",
            "woreda",
        ]


class SubmissionDetailSerializer(serializers.ModelSerializer):
    """Full serializer with raw_data."""

    class Meta:
        model = Submission
        fields = "__all__"


class PlotSerializer(serializers.ModelSerializer):
    submission_uuid = serializers.CharField(
        source="submission.uuid",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Plot
        fields = [
            "uuid",
            "plot_name",
            "instance_name",
            "polygon_wkt",
            "min_lat",
            "max_lat",
            "min_lon",
            "max_lon",
            "is_draft",
            "form_id",
            "region",
            "sub_region",
            "created_at",
            "submission_uuid",
        ]


class PlotOverlapQuerySerializer(serializers.Serializer):
    """Input for bounding-box overlap queries."""

    min_lat = CustomFloatField()
    max_lat = CustomFloatField()
    min_lon = CustomFloatField()
    max_lon = CustomFloatField()
    exclude_uuid = CustomCharField(required=False, default="")


class SyncTriggerSerializer(serializers.Serializer):
    """Input for triggering a form sync."""

    asset_uid = CustomCharField()
