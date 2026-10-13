from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.catalog import services
from apps.catalog.product_codes import PRODUCT_CODES
from apps.core.models import Organization


class Command(BaseCommand):
    help = (
        "Write the article codes of the owner's product list (ART0002...) into the reference of the products "
        "with the same name (D-126). Only the reference changes. With --create-missing, an article that matches "
        "no product is created with its code and name, in kg, in the category « À classer » and with no price. "
        "Without --apply, only report what would change."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--organization", type=int, help="Organization id (needed when there are several).")
        parser.add_argument("--apply", action="store_true", help="Write the codes (default: report only).")
        parser.add_argument(
            "--create-missing", action="store_true", help="Create the articles of the list that match no product."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        organizations = Organization.objects.order_by("id")
        if options["organization"] is not None:
            organizations = organizations.filter(pk=options["organization"])
        if organizations.count() != 1:
            raise CommandError("Name the organization with --organization <id>.")
        organization = organizations.get()
        outcomes = services.set_product_codes(
            organization=organization,
            actor=None,
            codes=PRODUCT_CODES,
            apply=options["apply"],
            create_missing=options["create_missing"],
        )
        for outcome in outcomes:
            old = f" (was {outcome.old_reference})" if outcome.old_reference else ""
            self.stdout.write(f"{outcome.code}  {outcome.status:<18} {outcome.name}{old}")
        written = sum(outcome.status == "set" for outcome in outcomes)
        created = sum(outcome.status == "new" for outcome in outcomes)
        verb = "written" if options["apply"] else "to write (run again with --apply)"
        self.stdout.write(
            f"{organization}: {written} code(s) {verb}, {len(outcomes) - written - created} left as they are."
        )
        if options["create_missing"]:
            verb = "created" if options["apply"] else "to create (run again with --apply)"
            self.stdout.write(
                f"{organization}: {created} product(s) {verb}, in « {services.UNSORTED_CATEGORY} », with no price."
            )
