import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core.models import Organization
from apps.inventory import selectors, services

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Compare the stock on hand of every location and batch with the sum of its movements and repair it "
        "from the ledger (D-038). With --check, only report: the nightly check, which fails when it finds "
        "a difference."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--check", action="store_true", help="Report the differences without repairing them.")

    def handle(self, *args: Any, **options: Any) -> None:
        check_only: bool = options["check"]
        found = 0
        for organization in Organization.objects.order_by("id"):
            if check_only:
                differences = selectors.on_hand_differences(organization)
            else:
                differences = services.rebuild_on_hand(organization=organization, actor=None)
            for difference in differences:
                found += 1
                message = (
                    f"{organization}: location {difference.location_id}, batch {difference.batch_id}: "
                    f"cache {difference.cached} kg, ledger {difference.ledger} kg"
                )
                # An error in the log reaches Sentry once its DSN is set.
                logger.error("Stock on hand differs from the ledger: %s", message)
                self.stdout.write(message)
        if check_only and found:
            raise CommandError(f"{found} difference(s) between the stock on hand and the ledger.")
        verb = "found" if check_only else "repaired"
        self.stdout.write(
            self.style.SUCCESS(f"Stock on hand checked against the ledger: {found} difference(s) {verb}.")
        )
