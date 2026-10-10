from django.urls import path

from . import views

urlpatterns = [
    path("locations", views.LocationListView.as_view(), name="location-list"),
    path("locations/<int:location_id>", views.LocationDetailView.as_view(), name="location-detail"),
    path("locations/<int:location_id>/archive", views.LocationArchiveView.as_view(), name="location-archive"),
    path("locations/<int:location_id>/restore", views.LocationRestoreView.as_view(), name="location-restore"),
]
