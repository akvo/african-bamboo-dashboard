import os

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.generics import (
    get_object_or_404,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from api.v1.v1_jobs.constants import JobStatus
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_jobs.serializers import (
    JobSerializer,
)


@extend_schema(
    description="Get the status/result of a job",
    tags=["Jobs"],
    responses=JobSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def view_job(request, job_id):
    job = get_object_or_404(Jobs, pk=job_id)
    serializer = JobSerializer(instance=job)
    return Response(
        data=serializer.data,
        status=status.HTTP_200_OK,
    )


CONTENT_TYPES = {
    ".zip": "application/zip",
    ".geojson": "application/geo+json",
}


@extend_schema(
    description=(
        "Download the result file of a "
        "completed job"
    ),
    tags=["Jobs"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_job_result(request, job_id):
    job = get_object_or_404(Jobs, pk=job_id)
    if job.status != JobStatus.done:
        return Response(
            {"message": "Job is not completed yet"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    info = job.info or {}
    file_path = info.get("file_path")
    if not file_path or not os.path.exists(
        file_path
    ):
        return Response(
            {"message": "File not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    ext = os.path.splitext(file_path)[1]
    content_type = CONTENT_TYPES.get(
        ext, "application/octet-stream"
    )
    filename = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        response = HttpResponse(
            f.read(), content_type=content_type
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename}"'
        )
        return response
