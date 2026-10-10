from django.apps import AppConfig


class FleetConfig(AppConfig):
    name = "apps.fleet"
    label = "fleet"
    verbose_name = "Flotte"

    def ready(self) -> None:
        from apps.core import session

        from . import selectors

        session.register_truck_lookup(selectors.truck_ref_of_driver)
