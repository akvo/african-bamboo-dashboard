from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from api.v1.v1_jobs.constants import (
    JobStatus,
    JobTypes,
)
from api.v1.v1_jobs.models import Jobs


class JobSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_type(self, instance):
        return JobTypes.FieldStr.get(
            instance.type
        )

    @extend_schema_field(serializers.CharField())
    def get_status(self, instance):
        return JobStatus.FieldStr.get(
            instance.status
        )

    class Meta:
        model = Jobs
        fields = [
            "id",
            "type",
            "status",
            "created",
            "available",
        ]
