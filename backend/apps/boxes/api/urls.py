from django.urls import path

from . import driver_views, views

urlpatterns = [
    # P1-T14 · returnable boxes (D-122)
    path("boxes/balances", views.BoxBalanceListView.as_view(), name="box-balances"),
    path("boxes/movements", views.BoxMovementListView.as_view(), name="box-movements"),
    path("boxes/adjustments", views.BoxAdjustmentView.as_view(), name="box-adjustments"),
    # P1-T14d · the driver's truck of the day and the boxes a client hands back
    path("my-boxes", driver_views.MyBoxDayView.as_view(), name="my-boxes"),
    path("my-box-pickups", driver_views.MyBoxPickupView.as_view(), name="my-box-pickups"),
]
