from django.urls import path

from .views import DocumentListView

urlpatterns = [
    path("document-index", DocumentListView.as_view(), name="document-index"),
]
