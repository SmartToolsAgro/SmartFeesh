from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.core import services
from apps.core.models import Organization, Role, User
from apps.demo.batches import seed_batches
from apps.demo.catalogue import seed_catalogue
from apps.demo.costing import seed_costing
from apps.demo.customers import seed_customers
from apps.demo.employees import seed_employees
from apps.demo.expenses import seed_expenses
from apps.demo.locations import seed_locations
from apps.demo.losses import seed_losses
from apps.demo.prices import seed_prices
from apps.demo.quotes import seed_quotes
from apps.demo.receipts import seed_receipts
from apps.demo.sale_invoices import seed_invoices
from apps.demo.sales import seed_sales
from apps.demo.stock import seed_stock
from apps.demo.supplier_invoices import seed_supplier_invoices
from apps.demo.suppliers import seed_suppliers
from apps.demo.transfers import seed_transfers

ORGANIZATION_NAME = "Frutti Del Mare"
# Known password for local development only. Anywhere else a password must be given (--password).
DEV_PASSWORD = "frutti-dev"
MIN_PASSWORD_LENGTH = 12
DEV_USERS = [
    ("owner", "Nadia", "K.", Role.OWNER),
    ("driver", "Sami", "B.", Role.DRIVER),
]


class Command(BaseCommand):
    help = (
        "Create one organization, one owner, one driver, a demo catalogue, suppliers, cold rooms, "
        "trucks, batches and their stock: development data, "
        "or demo data on staging with --password. Safe to run twice; an existing account keeps its password."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--password", help=f"Required when DEBUG is off, at least {MIN_PASSWORD_LENGTH} characters."
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        password: str | None = options["password"]
        if password is None:
            if not settings.DEBUG:
                raise CommandError("Outside development, give the demo password with --password.")
            password = DEV_PASSWORD

        organization = Organization.objects.filter(name=ORGANIZATION_NAME).first()
        if organization is None:
            organization = services.create_organization(name=ORGANIZATION_NAME)

        for username, first_name, last_name, role in DEV_USERS:
            user = User.objects.filter(username=username).first()
            if user is None:
                # Checked only for a new account: an existing one keeps its password, whatever is given.
                if password != DEV_PASSWORD and len(password) < MIN_PASSWORD_LENGTH:
                    raise CommandError(f"The password must have at least {MIN_PASSWORD_LENGTH} characters.")
                user = services.create_user(
                    username=username, password=password, first_name=first_name, last_name=last_name
                )
            if not user.memberships.filter(organization=organization, role=role, is_active=True).exists():
                services.add_member(organization=organization, user=user, role=role)

        owner = User.objects.get(username=DEV_USERS[0][0])
        products = seed_catalogue(organization=organization, actor=owner)
        suppliers = seed_suppliers(organization=organization, actor=owner)
        driver = User.objects.get(username=DEV_USERS[1][0])
        locations = seed_locations(organization=organization, actor=owner, driver=driver)
        batches = seed_batches(organization=organization, actor=owner)
        movements = seed_stock(organization=organization, actor=owner)
        receipts = seed_receipts(organization=organization, actor=owner)
        invoices = seed_supplier_invoices(organization=organization, actor=owner)
        customers = seed_customers(organization=organization, actor=owner)
        transfers = seed_transfers(organization=organization, actor=owner)
        losses = seed_losses(organization=organization, actor=owner)
        prices = seed_prices(organization=organization, actor=owner)
        quotes = seed_quotes(organization=organization, actor=owner)
        sales = seed_sales(organization=organization, actor=owner, driver=driver)
        sale_invoices = seed_invoices(organization=organization, actor=owner)
        employees = seed_employees(organization=organization, actor=owner, driver=driver)
        expenses = seed_expenses(organization=organization, actor=owner)
        costing = seed_costing(organization=organization, actor=owner)

        logins = ", ".join(username for username, *_ in DEV_USERS)
        shown = password if password == DEV_PASSWORD else "the one given"
        self.stdout.write(
            self.style.SUCCESS(
                f"{ORGANIZATION_NAME}: logins {logins}, password {shown}, "
                f"{products} new products, {suppliers} new suppliers, {locations} new cold rooms and trucks, "
                f"{batches} new batches, {movements} new stock movements, {receipts} new goods receipts, "
                f"{invoices} new supplier invoices, {customers} new customers"
            )
        )
        self.stdout.write(self.style.SUCCESS(f"{transfers} new transfers"))
        self.stdout.write(self.style.SUCCESS(f"{losses} new losses and stock counts"))
        self.stdout.write(self.style.SUCCESS(f"{prices} new minimum prices and price lists"))
        self.stdout.write(self.style.SUCCESS(f"{quotes} new quotes"))
        self.stdout.write(self.style.SUCCESS(f"{sales} new sales"))
        self.stdout.write(self.style.SUCCESS(f"{sale_invoices} new customer invoices"))
        self.stdout.write(self.style.SUCCESS(f"{employees} new employees"))
        self.stdout.write(self.style.SUCCESS(f"{expenses} new expenses, day labourers and days worked"))
        self.stdout.write(self.style.SUCCESS(f"{costing} new cold-room costs and general costs"))
