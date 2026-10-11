from django.apps import AppConfig


class ExpensesConfig(AppConfig):
    name = "apps.expenses"
    label = "expenses"
    verbose_name = "Dépenses"

    def ready(self) -> None:
        # A new organization gets the default expense categories (D-053).
        from . import signals  # noqa: F401
