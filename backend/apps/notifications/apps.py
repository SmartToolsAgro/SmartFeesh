from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notifications"

    def ready(self) -> None:
        # What the drivers do is told to the office, and what the office does to a driver is told to them (D-175).
        from . import signals  # noqa: F401
