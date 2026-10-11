from django.urls import path

from . import views

urlpatterns = [
    path("locations", views.LocationListView.as_view(), name="location-list"),
    path("locations/<int:location_id>", views.LocationDetailView.as_view(), name="location-detail"),
    path("locations/<int:location_id>/archive", views.LocationArchiveView.as_view(), name="location-archive"),
    path("locations/<int:location_id>/restore", views.LocationRestoreView.as_view(), name="location-restore"),
    path("batches", views.BatchListView.as_view(), name="batch-list"),
    path("batches/<int:batch_id>", views.BatchDetailView.as_view(), name="batch-detail"),
    # P1-T09 · transfers
    path("locations/<int:location_id>/stock", views.LocationStockView.as_view(), name="location-stock"),
    path("transfers", views.TransferListView.as_view(), name="transfer-list"),
    path("transfers/truck-day", views.TruckDayView.as_view(), name="transfer-truck-day"),
    path("transfers/<int:transfer_id>", views.TransferDetailView.as_view(), name="transfer-detail"),
    path("transfers/<int:transfer_id>/validate", views.TransferValidateView.as_view(), name="transfer-validate"),
    path("transfers/<int:transfer_id>/cancel", views.TransferCancelView.as_view(), name="transfer-cancel"),
]
