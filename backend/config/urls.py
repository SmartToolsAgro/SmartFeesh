from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

api_v1 = [
    path("", include("apps.core.api.urls")),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]
