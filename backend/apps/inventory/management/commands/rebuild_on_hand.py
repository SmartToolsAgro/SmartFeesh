import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core import services as core_services
from apps.core.models import Job, Organization
from apps.inventory import selectors, services

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Compare the stock on hand of every location and batch with the sum of its movements and repair it "
        "from the ledger (D-038). With --check, only report: the nightly check, which fails when it finds "
        "a difference and records its run for the monitoring (D-140)."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--check", action="store_true", help="Report the differences without repairing them.")

    def handle(self, *args: Any, **options: Any) -> None:
        check_only: bool = options["check"]
        if not check_only:
            self._summary(self._run(check_only=False), "repaired")
            return
        # The check leaves a trace the uptime workflow watches (/api/v1/health/stock-check): passed, failed with
        # the number of differences, or failed because it crashed. A run that never happens reads as late there.
        try:
            found = self._run(check_only=True)
        except Exception:
            core_services.record_job_run(job=Job.STOCK_CHECK, ok=False)
            raise
        core_services.record_job_run(job=Job.STOCK_CHECK, ok=found == 0, problems=found)
        if found:
            raise CommandError(f"{found} difference(s) between the stock on hand and the ledger.")
        self._summary(found, "found")

    def _run(self, *, check_only: bool) -> int:
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
        return found

    def _summary(self, found: int, verb: str) -> None:
        self.stdout.write(
            self.style.SUCCESS(f"Stock on hand checked against the ledger: {found} difference(s) {verb}.")
        )
