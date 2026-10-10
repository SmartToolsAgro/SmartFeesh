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


def test_outside_development_the_known_password_is_refused(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError):
        call_command("seed_dev")
    with pytest.raises(CommandError):
        call_command("seed_dev", password="short")
    assert not User.objects.exists()


def test_staging_demo_accounts_get_the_password_given(settings):
    settings.DEBUG = False

    call_command("seed_dev", password="a-long-demo-password")

    driver = User.objects.get(username="driver")
    assert driver.check_password("a-long-demo-password")
    assert not driver.check_password("frutti-dev")
