from django.urls import re_path
from rest_framework.routers import DefaultRouter

from api.v1.v1_odk import plot_views, views

router = DefaultRouter()
router.register(r"forms", views.FormMetadataViewSet)
router.register(
    r"submissions", views.SubmissionViewSet
)
router.register(r"plots", plot_views.PlotViewSet)
router.register(
    r"field-settings",
    views.FieldSettingsViewSet,
)
router.register(
    r"field-mappings",
    views.FieldMappingViewSet,
)
router.register(
    r"farmers",
    plot_views.FarmerViewSet,
)
router.register(
    r"enumerators",
    plot_views.EnumeratorViewSet,
    basename="enumerator",
)

urlpatterns = router.urls + [
    re_path(
        r"^rejection-audits/(?P<pk>[0-9]+)"
        r"/resend_notification/$",
        views.resend_rejection_notification,
        name="resend_rejection_notification",
    ),
]
