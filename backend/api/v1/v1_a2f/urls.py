from django.urls import path

from api.v1.v1_a2f.views import a2f_metrics

urlpatterns = [
    path("metrics/", a2f_metrics, name="a2f_metrics"),
]
