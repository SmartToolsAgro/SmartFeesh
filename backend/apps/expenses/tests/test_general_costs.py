import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.core.models import AuditLog
from apps.expenses import cost_selectors, selectors, services
from apps.expenses.costing import (
    add_months,
    allocate_general_days,
    first_of_month,
    general_day_amount,
    month_days,
    spread_over_months,
)
from apps.expenses.models import ExpenseStatus

from .conftest import category
from .test_cold_room_cost import put

pytestmark = pytest.mark.django_db

D = Decimal


def general_lines(organization, batch):
    return [line for line in selectors.lot_cost_lines(organization, batch_id=batch.pk) if line.kind == "general"]


def current_month():
    return first_of_month(timezone.localdate())


def days_so_far():
    return (timezone.localdate() - current_month()).days + 1


# ---- pure functions ----


def test_a_day_is_a_26th_of_the_monthly_amount():
    assert general_day_amount(D("260.000")) == D("10.000")
    assert general_day_amount(D("1500.000")) == D("57.692")


def test_a_bill_over_several_months_is_spread_exactly():
    parts = spread_over_months(D("1000.000"), 12)
    assert sum(parts) == D("1000.000")
    assert sorted(set(parts)) == [D("83.333"), D("83.334")]
    assert spread_over_months(D("90.000"), 1) == [D("90.000")]


def test_each_days_general_cost_is_shared_over_the_lots_in_stock_that_day():
    month = dt.date(2026, 9, 1)
    days = month_days(month)
    kg = {day: {1: D("75.000"), 2: D("25.000")} for day in days[:10]}
    charges = allocate_general_days(D("260.000"), days, kg)
    assert charges[1].amount + charges[2].amount == D("100.000")  # 10 days x 10 DT
    assert charges[1].amount == D("75.000")
    assert charges[2].kg_days == D("250.000")
    assert allocate_general_days(D("260.000"), days, {}) == {}


# ---- templates ----


def test_a_template_generates_the_months_expense_once(organization, actor):
    rent = category(organization, "rent")
    cost = services.create_recurring_cost(
        organization=organization,
        actor=actor,
        name="Loyer",
        category=rent,
        monthly_amount="1300.000",
        start_month=add_months(current_month(), -2),
    )
    created = services.generate_recurring_costs(organization=organization, actor=actor, month=current_month())
    assert len(created) == 1
    expense = created[0].expense
    assert (expense.status, expense.amount, expense.spent_on, expense.description) == (
        ExpenseStatus.DRAFT,
        D("1300.000"),
        current_month(),
        "Loyer",
    )
    assert services.generate_recurring_costs(organization=organization, actor=actor, month=current_month()) == []

    stopped = services.update_recurring_cost(
        cost=cost,
        actor=actor,
        name="Loyer",
        category=rent,
        monthly_amount="1400",
        start_month=cost.start_month,
        is_active=False,
    )
    assert (
        services.generate_recurring_costs(organization=organization, actor=actor, month=add_months(current_month(), -1))
        == []
    )
    assert stopped.monthly_amount == D("1400.000")
    with pytest.raises(ValidationError):
        services.generate_recurring_costs(organization=organization, actor=actor, month=add_months(current_month(), 1))


def recurring(organization, actor, rent, **fields):
    values = {"name": "Loyer", "category": rent, "monthly_amount": "1300.000", "start_month": current_month()}
    return services.create_recurring_cost(organization=organization, actor=actor, **{**values, **fields})


def test_a_template_with_an_archived_category_is_skipped_and_reported_not_a_failure(organization, actor):
    own = services.create_category(organization=organization, actor=actor, name="Gardiennage")
    recurring(organization, actor, own, name="Gardien")
    recurring(organization, actor, category(organization, "rent"))
    services.update_category(category=own, actor=actor, is_active=False)

    created = services.generate_recurring_costs(organization=organization, actor=actor, month=current_month())

    assert [period.expense.description for period in created] == ["Loyer"]
    skipped = AuditLog.objects.get(action="recurring_cost.skipped")
    assert skipped.after is not None
    assert skipped.after["archived_category"] == ["Gardien"]


def test_a_refused_month_of_a_template_is_generated_again(organization, actor):
    recurring(organization, actor, category(organization, "rent"))
    [first] = services.generate_recurring_costs(organization=organization, actor=actor, month=current_month())
    services.reject_expense(expense=first.expense, actor=actor, reason="Erreur de saisie")

    [second] = services.generate_recurring_costs(organization=organization, actor=actor, month=current_month())

    assert second.expense_id != first.expense_id
    assert second.expense.status == ExpenseStatus.DRAFT
    first.expense.refresh_from_db()
    assert first.expense.status == ExpenseStatus.REJECTED  # the refusal stays as a trace
    assert services.generate_recurring_costs(organization=organization, actor=actor, month=current_month()) == []


def test_generating_locks_the_organization_so_two_runs_cannot_both_create_a_month(organization, actor):
    recurring(organization, actor, category(organization, "rent"))

    with CaptureQueriesContext(connection) as queries:
        services.generate_recurring_costs(organization=organization, actor=actor, month=current_month())

    assert any("FOR UPDATE" in query["sql"] and "core_organization" in query["sql"] for query in queries)


def test_a_template_respects_its_first_and_last_month(organization, actor):
    rent = category(organization, "rent")
    services.create_recurring_cost(
        organization=organization,
        actor=actor,
        name="Assurance",
        category=rent,
        monthly_amount="50",
        start_month=add_months(current_month(), -1),
        end_month=add_months(current_month(), -1),
    )
    assert (
        services.generate_recurring_costs(organization=organization, actor=actor, month=add_months(current_month(), -2))
        == []
    )
    assert services.generate_recurring_costs(organization=organization, actor=actor, month=current_month()) == []
    assert (
        len(
            services.generate_recurring_costs(
                organization=organization, actor=actor, month=add_months(current_month(), -1), approve=True
            )
        )
        == 1
    )


def test_template_validation(organization, actor):
    day_labour = category(organization, "day_labour")
    rent = category(organization, "rent")
    with pytest.raises(ValidationError):
        services.create_recurring_cost(
            organization=organization,
            actor=actor,
            name="X",
            category=day_labour,
            monthly_amount="5",
            start_month=current_month(),
        )
    with pytest.raises(ValidationError):
        services.create_recurring_cost(
            organization=organization,
            actor=actor,
            name="X",
            category=rent,
            monthly_amount="0",
            start_month=current_month(),
        )
    with pytest.raises(ValidationError):
        services.create_recurring_cost(
            organization=organization,
            actor=actor,
            name="X",
            category=rent,
            monthly_amount="5",
            start_month=current_month() + dt.timedelta(days=1),
        )


# ---- cost on lots ----


def test_rent_is_a_26th_per_day_split_over_the_lots_in_stock_by_kg(organization, actor, cold_room):
    rent = category(organization, "rent")
    services.create_recurring_cost(
        organization=organization,
        actor=actor,
        name="Loyer",
        category=rent,
        monthly_amount="260.000",
        start_month=current_month(),
    )
    big = put(organization, "Dorade", "300", cold_room, current_month() - dt.timedelta(days=40))
    small = put(organization, "Loup", "100", cold_room, current_month() - dt.timedelta(days=40))

    [period] = services.generate_recurring_costs(organization=organization, actor=actor, month=current_month())
    assert general_lines(organization, big) == []  # a draft counts for nothing
    services.approve_expense(expense=period.expense, actor=actor)

    days = days_so_far()
    [line_big] = general_lines(organization, big)
    [line_small] = general_lines(organization, small)
    assert line_big.amount + line_small.amount == D("10.000") * days
    assert abs(line_big.amount - D("7.500") * days) <= D("0.001") * days
    assert (line_big.month, line_big.expense_number, line_big.category_code) == (
        current_month(),
        period.expense.number,
        "rent",
    )
    assert line_big.quantity == D("300.000") * days
    # It joins the other costs of the lot and its total.
    assert selectors.lot_cost_total(selectors.lot_cost_lines(organization, batch_id=big.pk)) == line_big.amount


def test_days_with_nothing_in_stock_charge_nobody(organization, actor, cold_room):
    rent = category(organization, "rent")
    services.create_recurring_cost(
        organization=organization,
        actor=actor,
        name="Loyer",
        category=rent,
        monthly_amount="260.000",
        start_month=current_month(),
    )
    [period] = services.generate_recurring_costs(
        organization=organization, actor=actor, month=current_month(), approve=True
    )
    assert period.expense.status == ExpenseStatus.APPROVED
    lot = put(organization, "Dorade", "10", cold_room, timezone.localdate())  # arrived today only
    [line] = general_lines(organization, lot)
    assert line.amount == D("10.000")  # one day


def test_a_bill_over_several_months_is_spread_over_them(organization, actor, cold_room):
    insurance = category(organization, "administration")
    start = add_months(current_month(), -1)
    period = services.create_general_cost(
        organization=organization,
        actor=actor,
        spent_on=start,
        category=insurance,
        amount="780.000",
        first_month=start,
        months=3,
        description="Assurance trimestrielle",
        approve=True,
    )
    lot = put(organization, "Dorade", "100", cold_room, start - dt.timedelta(days=5))
    lines = general_lines(organization, lot)
    assert [line.month for line in lines] == [start, current_month()]  # next month has not come yet
    assert lines[0].amount == D("260.000") / 26 * len(month_days(start))  # 10 DT x days
    assert lines[1].amount == D("10.000") * days_so_far()
    assert lines[0].description == "Assurance trimestrielle"
    assert cost_selectors.general_periods_of(organization, month=add_months(start, 2)).count() == 1
    assert cost_selectors.general_periods_of(organization, month=add_months(start, 3)).count() == 0
    assert period.months == 3


def test_a_general_cost_draft_is_deleted_through_its_own_record(organization, actor):
    draft = services.create_general_cost(
        organization=organization,
        actor=actor,
        spent_on=timezone.localdate(),
        category=category(organization, "rent"),
        amount="100",
        first_month=current_month(),
    )
    with pytest.raises(ValidationError):
        services.delete_expense(expense=draft.expense, actor=actor)
    services.delete_general_cost(period=draft, actor=actor)
    assert not cost_selectors.general_periods_of(organization).exists()
    with pytest.raises(ValidationError):
        services.create_general_cost(
            organization=organization,
            actor=actor,
            spent_on=timezone.localdate(),
            category=category(organization, "rent"),
            amount="100",
            first_month=current_month(),
            months=61,
        )


def test_changing_a_template_updates_its_months_not_yet_approved(organization, actor):
    rent = category(organization, "rent")
    cost = recurring(organization, actor, rent)
    last_month = add_months(current_month(), -1)
    services.update_recurring_cost(
        cost=cost, actor=actor, name="Loyer", category=rent, monthly_amount="1300", start_month=last_month
    )
    [approved] = services.generate_recurring_costs(
        organization=organization, actor=actor, month=last_month, approve=True
    )
    [draft] = services.generate_recurring_costs(organization=organization, actor=actor, month=current_month())

    services.update_recurring_cost(
        cost=cost,
        actor=actor,
        name="Loyer dépôt",
        category=rent,
        monthly_amount="1450",
        start_month=last_month,
        payee="M. Ben Ali",
    )

    draft.expense.refresh_from_db()
    approved.expense.refresh_from_db()
    assert (draft.expense.amount, draft.expense.description, draft.expense.payee) == (
        D("1450.000"),
        "Loyer dépôt",
        "M. Ben Ali",
    )
    assert draft.expense.status == ExpenseStatus.DRAFT
    # An approved month never changes: a correction is a new expense.
    assert (approved.expense.amount, approved.expense.description) == (D("1300.000"), "Loyer")
