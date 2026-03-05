from django.urls import re_path

from . import views

urlpatterns = [
    re_path(
        r"^(?P<version>(v1))/health/check",
        views.health_check,
        name="health_check",
    ),
    re_path(
        r"^(?P<version>(v1))/settings/telegram/$",
        views.telegram_settings,
        name="telegram_settings",
    ),
    re_path(
        r"^(?P<version>(v1))/settings/telegram/groups/$",
        views.telegram_groups,
        name="telegram_groups",
    ),
]
