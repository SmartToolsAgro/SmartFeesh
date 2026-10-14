"""The trace the nightly stock check leaves and the public status the uptime workflow reads (P4-T04, D-140)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core import selectors, services
from apps.core.models import Job, JobRun
from apps.core.tests.factories import OrganizationFactory, UserFactory
from apps.inventory import services as inventory_services
from apps.inventory.models import MovementKind, StockOnHand
from apps.inventory.tests.factories import BatchFactory, StockLocationFactory

pytestmark = pytest.mark.django_db

URL = reverse("health-stock-check")


def status_of(client: APIClient) -> tuple[int, dict[str, object]]:
    answer = client.get(URL)
    return answer.status_code, answer.json()


def age_run(hours: float) -> None:
    JobRun.objects.filter(job=Job.STOCK_CHECK).update(ran_at=timezone.now() - timedelta(hours=hours))


@pytest.fixture
def stocked_batch():
    organization = OrganizationFactory.create()
    cold_room = StockLocationFactory.create(organization=organization)
    batch = BatchFactory.create(organization=organization)
    inventory_services.post_movement(
        organization=organization,
        actor=UserFactory.create(),
        kind=MovementKind.RECEIPT,
        batch=batch,
        quantity="40",
        to_location=cold_room,
    )
    return cold_room, batch


def test_the_last_run_is_kept_once_per_job():
    services.record_job_run(job=Job.STOCK_CHECK, ok=False, problems=3)
    run = services.record_job_run(job=Job.STOCK_CHECK, ok=True)

    assert JobRun.objects.count() == 1
    assert (run.ok, run.problems) == (True, 0)


def test_the_nightly_check_records_a_pass_then_a_failure_with_the_count(stocked_batch):
    cold_room, batch = stocked_batch
    call_command("rebuild_on_hand", "--check")
    run = JobRun.objects.get(job=Job.STOCK_CHECK)
    assert (run.ok, run.problems) == (True, 0)

    StockOnHand.objects.filter(location=cold_room, batch=batch).update(quantity=Decimal("1.000"))
    with pytest.raises(CommandError, match="1 difference"):
        call_command("rebuild_on_hand", "--check")
    run.refresh_from_db()
    assert (run.ok, run.problems) == (False, 1)

    # The repair alone does not clear the alert: the next check does (runbook, "Monitoring").
    call_command("rebuild_on_hand")
    run.refresh_from_db()
    assert run.ok is False
    call_command("rebuild_on_hand", "--check")
    run.refresh_from_db()
    assert (run.ok, run.problems) == (True, 0)


def test_a_check_that_crashes_is_recorded_as_failed(monkeypatch):
    def boom(organization):
        raise RuntimeError("database gone")

    OrganizationFactory.create()
    monkeypatch.setattr("apps.inventory.selectors.on_hand_differences", boom)
    with pytest.raises(RuntimeError):
        call_command("rebuild_on_hand", "--check")
    assert JobRun.objects.get(job=Job.STOCK_CHECK).ok is False


def test_status_is_ok_after_a_recent_pass():
    services.record_job_run(job=Job.STOCK_CHECK, ok=True)

    code, body = status_of(APIClient())

    assert code == 200
    assert body["status"] == "ok"
    assert body["checked_at"] is not None


def test_status_fails_when_the_last_check_failed():
    services.record_job_run(job=Job.STOCK_CHECK, ok=False, problems=4)

    code, body = status_of(APIClient())

    assert (code, body["status"]) == (503, "failed")
    assert body["checked_at"] is not None


def test_status_fails_when_the_last_pass_is_too_old():
    services.record_job_run(job=Job.STOCK_CHECK, ok=True)
    age_run(25)
    assert status_of(APIClient())[0] == 200

    age_run(27)
    code, body = status_of(APIClient())
    assert (code, body["status"]) == (503, "late")


def test_status_fails_when_the_check_never_ran():
    assert status_of(APIClient()) == (503, {"status": "never", "checked_at": None})


def test_selector_reads_the_states():
    assert selectors.job_health(Job.STOCK_CHECK, max_age=timedelta(hours=1)).state is selectors.JobState.NEVER
    services.record_job_run(job=Job.STOCK_CHECK, ok=True)
    later = timezone.now() + timedelta(hours=2)
    assert selectors.job_health(Job.STOCK_CHECK, max_age=timedelta(hours=1), now=later).state is selectors.JobState.LATE
    assert selectors.job_health(Job.STOCK_CHECK, max_age=timedelta(hours=3), now=later).ok


def test_status_reveals_only_a_time_and_a_state():
    """Public, without a login: no count of differences, nothing of a company, even with a session cookie."""
    services.record_job_run(job=Job.STOCK_CHECK, ok=False, problems=12)
    logged_in = APIClient()
    logged_in.force_authenticate(UserFactory.create())

    for client in (APIClient(), logged_in):
        answer = client.get(URL)
        assert set(answer.json()) == {"status", "checked_at"}
        assert "12" not in answer.content.decode().replace(answer.json()["checked_at"], "")
