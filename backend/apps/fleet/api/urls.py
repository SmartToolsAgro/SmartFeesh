from django.urls import path

from . import views

urlpatterns = [
    path("trucks", views.TruckListView.as_view(), name="truck-list"),
    path("trucks/<int:truck_id>", views.TruckDetailView.as_view(), name="truck-detail"),
    path("trucks/<int:truck_id>/archive", views.TruckArchiveView.as_view(), name="truck-archive"),
    path("trucks/<int:truck_id>/restore", views.TruckRestoreView.as_view(), name="truck-restore"),
]
