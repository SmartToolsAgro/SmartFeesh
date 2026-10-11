from django.urls import path

from . import views

urlpatterns = [
    path("truck-assignments", views.TruckAssignmentListView.as_view(), name="truck-assignment-list"),
    path(
        "truck-assignments/<int:assignment_id>",
        views.TruckAssignmentDetailView.as_view(),
        name="truck-assignment-detail",
    ),
    path("trucks", views.TruckListView.as_view(), name="truck-list"),
    path("trucks/<int:truck_id>", views.TruckDetailView.as_view(), name="truck-detail"),
    path("trucks/<int:truck_id>/archive", views.TruckArchiveView.as_view(), name="truck-archive"),
    path("trucks/<int:truck_id>/restore", views.TruckRestoreView.as_view(), name="truck-restore"),
]
