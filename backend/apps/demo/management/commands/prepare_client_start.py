"""Empty one organization's business data before the client starts, keeping the real master data (D-146).

Kept: the organization, its settings, the logins (their passwords are replaced), the cold rooms and trucks, the
expense categories, the products whose code starts with ART (their prices and minimum stock are cleared), and the
employees named with --keep-employee (their payroll is emptied with the rest).

Emptied: every other record of the organization: stock, purchases, sales, invoices, customers, suppliers, costs,
payroll, closings, box movements, documents, prices, counters and the audit log. Boxes and stock start at zero.

The ledgers are append-only in the ORM on purpose, so this command deletes with SQL, inside one transaction. Django
creates its foreign keys as deferred, and `SET CONSTRAINTS ALL IMMEDIATE` checks them before the end: a dangling
reference rolls the whole reset back. Without --apply the same steps run and are rolled back, so the counts are real.
"""

import secrets
from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError, QuerySet
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.core.models import Organization, OrganizationScopedModel, User
from apps.expenses.models import ExpenseCategory
from apps.fleet.models import Truck
from apps.hr.models import Employee
from apps.inventory.models import StockLocation, StockSettings
from apps.sales.models import FinanceSettings

# The owner's article codes start with this prefix (docs/spec: the list of 2026-10-13, D-126).
CLIENT_PRODUCT_PREFIX = "ART"
# Organization-scoped models kept as they are. Products, categories and employees are filtered, not kept whole.
KEPT_MODELS = (StockLocation, Truck, StockSettings, FinanceSettings, ExpenseCategory, Product, Category, Employee)


class Command(BaseCommand):
    help = (
        "Empty the business data of one organization before the client starts (D-146). Keeps the company settings, "
        "the logins, the cold rooms and trucks, the ART products and the employees named with --keep-employee. "
        "Without --apply it only reports what would go, and rolls back."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--organization", type=int, help="Organization id (needed when there are several).")
        parser.add_argument(
            "--keep-employee",
            action="append",
            default=[],
            metavar="NAME",
            help="Part of the name of an employee to keep. It must match exactly one employee. Repeat for each.",
        )
        parser.add_argument(
            "--apply", action="store_true", help="Delete for real and replace the logins' passwords (default: dry run)."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        organization = self._organization(options["organization"])
        keep_ids = self._employee_ids(organization, options["keep_employee"])
        apply = options["apply"]

        passwords: list[tuple[str, str]] = []
        try:
            with transaction.atomic():
                report = _empty(organization, keep_ids)
                kept = _kept_counts(organization, keep_ids)
                if apply:
                    passwords = _replace_passwords(organization)
                    Organization.objects.filter(pk=organization.pk).update(real_data_since=timezone.now())
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                if not apply:
                    transaction.set_rollback(True)
        except (IntegrityError, ProtectedError) as error:
            raise CommandError(
                f"Nothing was changed: a record would be left pointing at a deleted one ({error})."
            ) from error

        self._write_report(organization, report, kept, apply)
        for username, password in passwords:
            self.stdout.write(self.style.WARNING(f"New password for {username}: {password}"))

    def _organization(self, pk: int | None) -> Organization:
        organizations = Organization.objects.order_by("id")
        if pk is not None:
            organizations = organizations.filter(pk=pk)
        if organizations.count() != 1:
            raise CommandError("Name the organization with --organization <id>.")
        return organizations.get()

    def _employee_ids(self, organization: Organization, names: list[str]) -> list[int]:
        ids: list[int] = []
        for name in names:
            matches = list(
                Employee.objects.filter(organization=organization, name__icontains=name).values_list("id", "name")
            )
            if len(matches) != 1:
                found = ", ".join(employee_name for _pk, employee_name in matches) or "none"
                raise CommandError(
                    f"--keep-employee {name!r} matches {len(matches)} employee(s) ({found}). "
                    "Give a part of the name that matches exactly one."
                )
            ids.append(matches[0][0])
        return ids

    def _write_report(
        self, organization: Organization, report: list[tuple[str, int]], kept: dict[str, int], apply: bool
    ) -> None:
        self.stdout.write(f"{organization}: {'deleted' if apply else 'would delete'}")
        for label, count in report:
            self.stdout.write(f"  {label:<40} {count}")
        self.stdout.write("Kept:")
        for label, count in kept.items():
            self.stdout.write(f"  {label:<40} {count}")
        if apply:
            self.stdout.write(self.style.SUCCESS("Done. Run `rebuild_on_hand --check` to confirm the stock is empty."))
        else:
            self.stdout.write(self.style.WARNING("Dry run: nothing was changed. Run again with --apply."))


def _kept_counts(organization: Organization, keep_employee_ids: list[int]) -> dict[str, int]:
    """What stays, counted after the deletes, so the report shows the rows that are left."""
    return {
        "Cold rooms and trucks (locations)": StockLocation.objects.filter(organization=organization).count(),
        "Trucks": Truck.objects.filter(organization=organization).count(),
        f"Products with code {CLIENT_PRODUCT_PREFIX}*": Product.objects.filter(
            organization=organization, reference__startswith=CLIENT_PRODUCT_PREFIX
        ).count(),
        "Employees": len(keep_employee_ids),
        "Expense categories": ExpenseCategory.objects.filter(organization=organization).count(),
    }


def _empty(organization: Organization, keep_employee_ids: list[int]) -> list[tuple[str, int]]:
    """Delete everything of the organization that is not kept. Returns the rows deleted per model."""
    report: list[tuple[str, int]] = []
    with connection.cursor() as cursor:
        for model in apps.get_models():
            if not issubclass(model, OrganizationScopedModel) or model in KEPT_MODELS:
                continue
            table = connection.ops.quote_name(model._meta.db_table)
            cursor.execute(f"DELETE FROM {table} WHERE organization_id = %s", [organization.pk])
            if cursor.rowcount:
                report.append((model._meta.label, cursor.rowcount))

    # Products first: a category is only kept while a kept product uses it.
    deleted_products = Product.objects.filter(organization=organization).exclude(
        reference__startswith=CLIENT_PRODUCT_PREFIX
    )
    report += _report_orm_delete(deleted_products)
    report += _report_orm_delete(Category.objects.filter(organization=organization, products=None))
    report += _report_orm_delete(Employee.objects.filter(organization=organization).exclude(pk__in=keep_employee_ids))

    # Kept products start with no price and no minimum, as the 36 products of the owner's list do.
    Product.objects.filter(organization=organization, reference__startswith=CLIENT_PRODUCT_PREFIX).update(
        min_price=None, min_stock=0
    )
    # Trucks keep their place; the driver is chosen again on the day (D-042).
    Truck.objects.filter(organization=organization).update(driver=None)
    return report


def _report_orm_delete(queryset: QuerySet[Any]) -> list[tuple[str, int]]:
    _total, per_model = queryset.delete()
    return [(label, count) for label, count in per_model.items() if count]


def _replace_passwords(organization: Organization) -> list[tuple[str, str]]:
    """New random passwords for the logins of the organization, so the demo password stops working."""
    passwords: list[tuple[str, str]] = []
    for user in User.objects.filter(memberships__organization=organization).distinct().order_by("username"):
        password = secrets.token_urlsafe(12)
        user.set_password(password)
        user.save(update_fields=["password"])
        passwords.append((user.username, password))
    return passwords
