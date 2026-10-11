from django.apps import AppConfig


class SalesConfig(AppConfig):
    name = "apps.sales"
    label = "sales"
    verbose_name = "Ventes"

    def ready(self) -> None:
        # A new organization gets its first finance settings version (D-056).
        from . import signals  # noqa: F401
