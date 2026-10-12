from django.urls import path

from . import views

urlpatterns = [
    path("imports/<str:kind>/template", views.ImportTemplateView.as_view(), name="import-template"),
    path("imports/<str:kind>", views.ImportRunView.as_view(), name="import-run"),
]
