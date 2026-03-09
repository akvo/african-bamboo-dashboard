from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

urlpatterns = [
    re_path(
        r"^storage/(?P<path>.*)$",
        serve,
        {"document_root": settings.STORAGE_PATH},
    ),
    path(
        "api/",
        include("api.v1.v1_init.urls"),
        name="v1_init",
    ),
    path(
        "api/",
        include("api.v1.v1_users.urls"),
        name="v1_users",
    ),
    path(
        "api/v1/odk/",
        include("api.v1.v1_odk.urls"),
        name="v1_odk",
    ),
    path(
        "api/v1/jobs/",
        include("api.v1.v1_jobs.urls"),
        name="v1_jobs",
    ),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema"
        ),
        name="swagger-ui",
    ),
]
