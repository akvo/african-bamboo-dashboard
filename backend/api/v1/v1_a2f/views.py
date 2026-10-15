from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.v1_a2f.metrics import (
    FILTER_PARAMS,
    compute_metrics,
    filter_options,
)
from api.v1.v1_a2f.models import A2FSnapshot


@extend_schema(
    description=(
        "Access to finance metrics from the latest imported "
        "snapshot. 404 while the feature is disabled or before "
        "the first import."
    ),
    tags=["Access to finance"],
    parameters=[
        OpenApiParameter(name, OpenApiTypes.STR, required=False)
        for name in FILTER_PARAMS
    ],
    responses={200: OpenApiTypes.OBJECT},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def a2f_metrics(request):
    snapshot = A2FSnapshot.objects.first()
    if not settings.A2F_ENABLED or snapshot is None:
        return Response(
            {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
        )
    filters = {
        name: value
        for name in FILTER_PARAMS
        if (value := request.query_params.get(name, "").strip())
    }
    data = compute_metrics(snapshot, filters)
    data["filter_options"] = filter_options(snapshot)
    return Response(data)
