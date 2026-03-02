from django.urls import path

from api.v1.v1_jobs.views import (
    download_job_result,
    view_job,
)

urlpatterns = [
    path(
        "<int:job_id>/",
        view_job,
        name="view_job",
    ),
    path(
        "<int:job_id>/download/",
        download_job_result,
        name="download_job_result",
    ),
]
