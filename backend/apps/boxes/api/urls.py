from django.urls import path

from . import views

urlpatterns = [
    # P1-T14 · returnable boxes (D-122)
    path("boxes/balances", views.BoxBalanceListView.as_view(), name="box-balances"),
    path("boxes/movements", views.BoxMovementListView.as_view(), name="box-movements"),
]
