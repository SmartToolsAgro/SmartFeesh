from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("auth/csrf", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path("me", views.MeView.as_view(), name="me"),
    path("members", views.MemberListView.as_view(), name="member-list"),
]
