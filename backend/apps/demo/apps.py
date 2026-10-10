from django.apps import AppConfig


class DemoConfig(AppConfig):
    """Demo and development data. The only app allowed to call every other app, to fill them."""

    name = "apps.demo"
    label = "demo"
    verbose_name = "Demo data"
