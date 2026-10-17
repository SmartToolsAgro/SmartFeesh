from django.urls import path

from . import views

urlpatterns = [
    path("me/notifications", views.MyNotificationsView.as_view(), name="my-notifications"),
    path("me/notifications/read", views.MyNotificationsReadView.as_view(), name="my-notifications-read"),
]
