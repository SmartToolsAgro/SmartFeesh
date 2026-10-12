from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import SpectacularAPIView

from apps.core.permissions import IsOwnerOrManager

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
    path("", include("apps.dayclose.api.urls")),
    path("", include("apps.documents.api.urls")),
    # The API map is for the people who build the apps: not for a driver or the accountant (D-108).
    path("schema", SpectacularAPIView.as_view(permission_classes=[IsOwnerOrManager]), name="schema"),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]
