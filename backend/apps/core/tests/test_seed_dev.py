import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.models import Membership, Organization, Role, User
from apps.core.selectors import active_membership

pytestmark = pytest.mark.django_db


def test_seed_creates_one_organization_one_owner_and_one_driver(settings):
    settings.DEBUG = True

    call_command("seed_dev")
    call_command("seed_dev")  # running it again changes nothing

    organization = Organization.objects.get()
    assert organization.name == "Frutti Del Mare"
    assert set(Membership.objects.values_list("user__username", "role")) == {
        ("owner", Role.OWNER),
        ("driver", Role.DRIVER),
    }
    owner = User.objects.get(username="owner")
    assert owner.check_password("frutti-dev")
    membership = active_membership(owner)
    assert membership is not None
    assert membership.organization == organization


def test_seed_refuses_to_run_outside_development(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError):
        call_command("seed_dev")
    assert not User.objects.exists()
