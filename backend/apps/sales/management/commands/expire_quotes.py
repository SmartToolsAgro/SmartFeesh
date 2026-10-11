from typing import Any

from django.core.management.base import BaseCommand

from apps.core.models import Organization
from apps.sales import services


class Command(BaseCommand):
    help = (
        "Mark as expired the sent quotes whose validity date has passed without an answer (D-050). "
        "Run every night; the screens already show them expired before it runs."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        total = 0
        for organization in Organization.objects.order_by("id"):
            total += services.expire_quotes(organization=organization)
        self.stdout.write(self.style.SUCCESS(f"{total} quote(s) expired."))
