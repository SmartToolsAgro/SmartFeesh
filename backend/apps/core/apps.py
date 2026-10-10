from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    verbose_name = "Core"

    def ready(self) -> None:
        # Registers the OpenAPI description of our session authentication.
        from .api import schema  # noqa: F401
