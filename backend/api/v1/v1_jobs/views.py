import os

from django.http import FileResponse
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
from utils import storage


@extend_schema(
    description="Get the status/result of a job",
    tags=["Jobs"],
    responses=JobSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def view_job(request, job_id):
    job = get_object_or_404(
        Jobs, pk=job_id, created_by=request.user
    )
    serializer = JobSerializer(instance=job)
    return Response(
        data=serializer.data,
        status=status.HTTP_200_OK,
    )


CONTENT_TYPES = {
    ".zip": "application/zip",
    ".geojson": "application/geo+json",
    ".xlsx": (
        "application/vnd.openxmlformats-"
        "officedocument.spreadsheetml.sheet"
    ),
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
    job = get_object_or_404(
        Jobs, pk=job_id, created_by=request.user
    )
    if job.status != JobStatus.done:
        return Response(
            {"message": "Job is not completed yet"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    info = job.info or {}
    rel_path = info.get("file_path")
    if not rel_path or not storage.check(rel_path):
        return Response(
            {"message": "File not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Path-traversal protection
    full_path = storage.get_path(rel_path)
    real_path = os.path.realpath(full_path)
    storage_root = os.path.realpath(
        storage.get_path("")
    )
    if not real_path.startswith(
        storage_root + os.sep
    ):
        return Response(
            {"message": "File not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    ext = os.path.splitext(real_path)[1]
    content_type = CONTENT_TYPES.get(
        ext, "application/octet-stream"
    )
    filename = os.path.basename(real_path)

    response = FileResponse(
        open(real_path, "rb"),
        content_type=content_type,
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )
    return response
