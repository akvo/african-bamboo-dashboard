from django.urls import re_path

from api.v1.v1_users.views import ProfileView, login

urlpatterns = [
    re_path(r"^(?P<version>(v1))/auth/login", login),
    re_path(r"^(?P<version>(v1))/users/me", ProfileView.as_view()),
]
