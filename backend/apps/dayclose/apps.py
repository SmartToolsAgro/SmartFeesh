from django.apps import AppConfig


class DaycloseConfig(AppConfig):
    name = "apps.dayclose"
    label = "dayclose"
    verbose_name = "Clôtures de journée"

    def ready(self) -> None:
        # A load validated into a truck opens its driver's sent day again (D-134).
        from . import signals  # noqa: F401
