from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core import services
from apps.core.models import Organization, Role, User

ORGANIZATION_NAME = "Frutti Del Mare"
# Development logins only. The command refuses to run when DEBUG is off.
DEV_PASSWORD = "frutti-dev"
DEV_USERS = [
    ("owner", "Nadia", "K.", Role.OWNER),
    ("driver", "Sami", "B.", Role.DRIVER),
]


class Command(BaseCommand):
    help = "Create one organization, one owner and one driver for local development. Safe to run twice."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError("seed_dev creates accounts with a known password: it only runs with DEBUG on.")

        organization = Organization.objects.filter(name=ORGANIZATION_NAME).first()
        if organization is None:
            organization = services.create_organization(name=ORGANIZATION_NAME)

        for username, first_name, last_name, role in DEV_USERS:
            user = User.objects.filter(username=username).first()
            if user is None:
                user = services.create_user(
                    username=username, password=DEV_PASSWORD, first_name=first_name, last_name=last_name
                )
            if not user.memberships.filter(organization=organization, role=role, is_active=True).exists():
                services.add_member(organization=organization, user=user, role=role)

        logins = ", ".join(username for username, *_ in DEV_USERS)
        self.stdout.write(self.style.SUCCESS(f"{ORGANIZATION_NAME}: logins {logins}, password {DEV_PASSWORD}"))
