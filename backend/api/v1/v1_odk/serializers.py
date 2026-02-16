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
            "polygon_field",
            "region_field",
            "sub_region_field",
            "plot_name_field",
        ]

    def get_submission_count(self, obj):
        return obj.submissions.count()


class SubmissionListSerializer(serializers.ModelSerializer):
    """Lightweight list — excludes raw_data."""

    form = serializers.CharField(source="form.asset_uid", read_only=True)
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
            "approval_status",
        ]


class SubmissionDetailSerializer(serializers.ModelSerializer):
    """Full serializer with raw_data."""

    form = serializers.CharField(source="form.asset_uid", read_only=True)

    class Meta:
        model = Submission
        fields = "__all__"


class SubmissionUpdateSerializer(serializers.ModelSerializer):
    """Restrict writable fields for approval."""

    class Meta:
        model = Submission
        fields = [
            "approval_status",
            "reviewer_notes",
        ]


class PlotSerializer(serializers.ModelSerializer):
    submission_uuid = serializers.CharField(
        source="submission.uuid",
        read_only=True,
        allow_null=True,
    )
    form_id = serializers.SlugRelatedField(
        slug_field="asset_uid",
        queryset=FormMetadata.objects.all(),
        source="form",
    )
    approval_status = serializers.IntegerField(
        source="submission.approval_status",
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
            "form_id",
            "region",
            "sub_region",
            "created_at",
            "submission_uuid",
            "approval_status",
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
