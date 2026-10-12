from django.urls import path

from . import views

urlpatterns = [
    path("my-day-summary", views.MyDaySummaryView.as_view(), name="my-day-summary"),
    path("my-day-closing", views.MyDayClosingView.as_view(), name="my-day-closing"),
    path("day-closings", views.DayClosingListView.as_view(), name="day-closing-list"),
    path("day-closings/<int:closing_id>", views.DayClosingDetailView.as_view(), name="day-closing-detail"),
    path("day-closings/<int:closing_id>/approve", views.DayClosingApproveView.as_view(), name="day-closing-approve"),
    path(
        "day-closings/<int:closing_id>/request-justification",
        views.DayClosingJustificationView.as_view(),
        name="day-closing-justification",
    ),
]
