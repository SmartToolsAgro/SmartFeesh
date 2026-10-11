from django.urls import path

from .views import DocumentPdfView

urlpatterns = [
    path("documents/<str:kind>/<int:object_id>/pdf", DocumentPdfView.as_view(), name="document-pdf"),
]
