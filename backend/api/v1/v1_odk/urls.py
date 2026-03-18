from rest_framework.routers import DefaultRouter

from api.v1.v1_odk import views

router = DefaultRouter()
router.register(r"forms", views.FormMetadataViewSet)
router.register(r"submissions", views.SubmissionViewSet)
router.register(r"plots", views.PlotViewSet)
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
    views.FarmerViewSet,
)
router.register(
    r"enumerators",
    views.EnumeratorViewSet,
    basename="enumerator",
)

urlpatterns = router.urls
