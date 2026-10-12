from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import SpectacularAPIView

api_v1: list[URLPattern | URLResolver] = [
    path("", include("apps.core.api.urls")),
    path("", include("apps.catalog.api.urls")),
    path("", include("apps.partners.api.urls")),
    path("", include("apps.inventory.api.urls")),
    path("", include("apps.fleet.api.urls")),
    path("", include("apps.purchasing.api.urls")),
    path("", include("apps.sales.api.urls")),
    path("", include("apps.hr.api.urls")),
    path("", include("apps.expenses.api.urls")),
    path("", include("apps.partnerships.api.urls")),
    path("", include("apps.closing.api.urls")),
    path("", include("apps.reports.api.urls")),
    path("", include("apps.dayclose.api.urls")),
    path("", include("apps.documents.api.urls")),
    path("", include("apps.dataimport.api.urls")),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]
