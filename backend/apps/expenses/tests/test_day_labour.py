from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Role
from apps.expenses import selectors, services
from apps.expenses.models import DayLabourEntry, Expense, ExpenseStatus, WorkType

from .conftest import client_for, days_ago, member, receive

pytestmark = pytest.mark.django_db


@pytest.fixture
def ali(organization, actor):
    return services.create_labourer(
        organization=organization, actor=actor, name=" Ali  Ben Salah ", phone="98 123 456", usual_daily_pay="40"
    )


def work(organization, actor, labourer, **fields):
    fields.setdefault("worked_on", timezone.localdate())
    return services.create_day_labour(organization=organization, actor=actor, labourer=labourer, **fields)


# ---- labourers ----


def test_a_labourer_has_a_name_a_phone_and_a_usual_daily_pay(organization, actor, ali):
    assert (ali.name, ali.phone, ali.usual_daily_pay) == ("Ali Ben Salah", "98 123 456", Decimal("40.000"))
    with pytest.raises(ValidationError) as error:
        services.create_labourer(organization=organization, actor=actor, name="ali ben salah", usual_daily_pay="0")
    assert set(error.value.message_dict) == {"name", "usual_daily_pay"}
    archived = services.update_labourer(labourer=ali, actor=actor, name=ali.name, is_active=False)
    assert archived not in selectors.labourers_of(organization)
    assert archived.usual_daily_pay is None


# ---- days worked ----


def test_a_day_is_one_record_with_its_day_labour_expense(organization, actor, ali, cold_room):
    lot = receive(organization, "Dorade", "100", cold_room)

    entry = work(organization, actor, ali, batch=lot, work_type=WorkType.LOADING, notes="Déchargement du camion")

    expense = entry.expense
    assert (expense.category.code, expense.amount, expense.batch, expense.status) == (
        "day_labour",
        Decimal("40.000"),
        lot,
        ExpenseStatus.DRAFT,
    )
    assert (expense.description, expense.payee, expense.notes) == (
        "Ali Ben Salah",
        "Ali Ben Salah",
        "Déchargement du camion",
    )
    # The same record seen from the calendar and from the lot: never twice.
    assert list(selectors.day_labour_of(organization, date_from=timezone.localdate())) == [entry]
    assert list(selectors.day_labour_of(organization, batch_id=lot.pk)) == [entry]
    assert selectors.expenses_of(organization).count() == 1
    services.approve_expense(expense=expense, actor=actor)
    lines = selectors.lot_cost_lines(organization, batch_id=lot.pk)
    assert [(line.kind, line.category_code, line.amount, line.description) for line in lines] == [
        ("lot", "day_labour", Decimal("40.000"), "Ali Ben Salah")
    ]


def test_a_day_without_lot_is_a_general_cost(organization, actor, ali):
    entry = work(organization, actor, ali, amount="35.500", work_type=WorkType.CLEANING, approve=True)

    assert (entry.expense.batch, entry.expense.amount, entry.expense.status) == (
        None,
        Decimal("35.500"),
        ExpenseStatus.APPROVED,
    )


def test_without_amount_or_usual_pay_the_amount_is_asked(organization, actor):
    moncef = services.create_labourer(organization=organization, actor=actor, name="Moncef")
    with pytest.raises(ValidationError) as error:
        work(organization, actor, moncef)
    assert "amount" in error.value.message_dict


def test_an_archived_labourer_gets_no_new_day(organization, actor, ali):
    ali = services.update_labourer(labourer=ali, actor=actor, name=ali.name, usual_daily_pay="40", is_active=False)
    with pytest.raises(ValidationError) as error:
        work(organization, actor, ali)
    assert "labourer" in error.value.message_dict


def test_a_day_is_corrected_until_approved_and_deleted_while_a_draft(organization, actor, ali, cold_room):
    lot = receive(organization, "Dorade", "100", cold_room, received_on=days_ago(3))
    entry = work(organization, actor, ali)

    corrected = services.update_day_labour(
        entry=entry, actor=actor, labourer=ali, worked_on=days_ago(1), amount="45", batch=lot, work_type="stock"
    )
    assert (corrected.expense.spent_on, corrected.expense.amount, corrected.expense.batch, corrected.work_type) == (
        days_ago(1),
        Decimal("45.000"),
        lot,
        "stock",
    )
    services.delete_day_labour(entry=corrected, actor=actor)
    assert not DayLabourEntry.objects.exists()
    assert not Expense.objects.filter(pk=entry.expense_id).exists()
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"day_labour.created", "day_labour.updated", "day_labour.deleted", "expense.deleted"} <= actions


def test_an_approved_day_never_changes(organization, actor, ali):
    entry = work(organization, actor, ali, approve=True)

    with pytest.raises(ValidationError):
        services.update_day_labour(entry=entry, actor=actor, labourer=ali, worked_on=timezone.localdate(), amount="1")
    with pytest.raises(ValidationError):
        services.delete_day_labour(entry=entry, actor=actor)


def test_a_day_labour_expense_is_changed_only_through_the_calendar(organization, actor, ali):
    expense = work(organization, actor, ali).expense

    with pytest.raises(ValidationError):
        services.update_expense(
            expense=expense, actor=actor, spent_on=expense.spent_on, category=expense.category, amount="1"
        )
    with pytest.raises(ValidationError):
        services.delete_expense(expense=expense, actor=actor)


# ---- API ----


def test_the_calendar_reads_a_month_and_adds_days(api, organization, actor, ali, cold_room):
    lot = receive(organization, "Dorade", "100", cold_room, number="L-0042")
    old = work(organization, actor, ali, worked_on=days_ago(40))

    created = api.post(
        reverse("day-labour-list"),
        {"labourer": ali.pk, "worked_on": timezone.localdate().isoformat(), "batch": lot.pk, "work_type": "loading"},
        format="json",
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["amount"], body["status"], body["labourer"]["name"]) == ("40.000", "draft", "Ali Ben Salah")
    assert body["batch"] == {"id": lot.pk, "number": "L-0042", "product_name": "Dorade"}
    month = api.get(
        reverse("day-labour-list"), {"date_from": days_ago(10).isoformat(), "date_to": timezone.localdate().isoformat()}
    ).json()
    assert [row["id"] for row in month] == [body["id"]]
    assert old.pk not in [row["id"] for row in month]
    # The same record in the expenses list, marked as a day labourer's day.
    expense = api.get(reverse("expense-detail", args=[body["expense_id"]])).json()
    assert (expense["labourer_name"], expense["day_labour_id"]) == ("Ali Ben Salah", body["id"])
    edited = api.put(
        reverse("day-labour-detail", args=[body["id"]]),
        {"labourer": ali.pk, "worked_on": timezone.localdate().isoformat(), "amount": "50", "approve_now": True},
        format="json",
    )
    assert (edited.json()["amount"], edited.json()["status"], edited.json()["batch"]) == ("50.000", "approved", None)
    assert api.delete(reverse("day-labour-detail", args=[body["id"]])).status_code == 400


def test_labourers_api_and_roles(api, organization):
    created = api.post(reverse("day-labourer-list"), {"name": "Moncef", "usual_daily_pay": "35"}, format="json")
    assert (created.status_code, created.json()["usual_daily_pay"]) == (201, "35.000")
    updated = api.put(
        reverse("day-labourer-detail", args=[created.json()["id"]]),
        {"name": "Moncef Trabelsi", "phone": "22 000 111", "usual_daily_pay": "", "is_active": True},
        format="json",
    )
    assert (updated.json()["name"], updated.json()["usual_daily_pay"]) == ("Moncef Trabelsi", None)
    accountant = client_for(member(organization, Role.ACCOUNTANT))
    assert accountant.get(reverse("day-labourer-list")).status_code == 200
    assert accountant.post(reverse("day-labourer-list"), {"name": "X"}, format="json").status_code == 403
    driver = client_for(member(organization, Role.DRIVER))
    assert driver.get(reverse("day-labour-list")).status_code == 403
