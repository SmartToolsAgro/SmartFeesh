from django.apps import AppConfig


class ClosingConfig(AppConfig):
    name = "apps.closing"
    label = "closing"
    verbose_name = "Résultats des lots"

    def ready(self) -> None:
        from . import printing

        # The partner statement PDF (P6-T04).
        printing.register_printables()
