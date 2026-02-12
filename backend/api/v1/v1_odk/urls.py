from rest_framework.routers import DefaultRouter

from api.v1.v1_odk import views

router = DefaultRouter()
router.register(r"forms", views.FormMetadataViewSet)
router.register(r"submissions", views.SubmissionViewSet)
router.register(r"plots", views.PlotViewSet)

urlpatterns = router.urls
