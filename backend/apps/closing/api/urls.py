from django.urls import path

from . import views

urlpatterns = [
    path("lots/<int:batch_id>/result", views.LotResultView.as_view(), name="lot-result"),
    path("lots/<int:batch_id>/close", views.CloseLotView.as_view(), name="lot-close"),
    path("lots/<int:batch_id>/reopen", views.ReopenLotView.as_view(), name="lot-reopen"),
]
