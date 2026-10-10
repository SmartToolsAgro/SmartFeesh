from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import SpectacularAPIView

api_v1: list[URLPattern | URLResolver] = [
    path("", include("apps.core.api.urls")),
    path("", include("apps.catalog.api.urls")),
    path("", include("apps.partners.api.urls")),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]
