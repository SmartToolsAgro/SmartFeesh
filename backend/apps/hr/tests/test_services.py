import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import AuditLog
from apps.core.tests.factories import MembershipFactory
from apps.hr import selectors, services
from apps.hr.models import SalaryStatus

from .factories import EmployeeFactory

pytestmark = pytest.mark.django_db

THIS_MONTH = timezone.localdate().replace(day=1)


def test_a_day_on_a_lot_costs_days_times_salary_over_26_rounded_once():
    cost = selectors.employee_cost_for_lot_days

    assert cost("1", "1300.000") == Decimal("50.000")
    assert cost("0.5", "1300.000") == Decimal("25.000")
    # 1250 / 26 = 48.0769...: rounded once, half up, at the end.
    assert cost("1", "1250.000") == Decimal("48.077")
    assert cost("0.25", "1250.000") == Decimal("12.019")
    # Three half days are NOT three rounded half days: no intermediate rounding.
    assert cost("0.75", "1000.000") == Decimal("28.846")
    assert cost(Decimal("1.00"), 0) == Decimal("0.000")


def test_the_employer_contribution_is_the_rate_of_the_gross_rounded_once():
    assert services.employer_contribution("1600.000", "17.07") == Decimal("273.120")
    assert services.employer_contribution("1250.000", "17.07") == Decimal("213.375")
    assert services.employer_contribution("1000.001", "17.07") == Decimal("170.700")


def test_creating_an_employee_gives_a_reference_the_default_rate_and_an_audit_entry():
    organization = EmployeeFactory.create(reference="E-001").organization
    employee = services.create_employee(
        organization=organization, actor=None, name=" Hedi Z. ", monthly_salary=Decimal("1100.000")
    )

    assert (employee.reference, employee.name, employee.cnss_rate) == ("E-002", "Hedi Z.", Decimal("17.07"))
    assert AuditLog.objects.filter(action="employee.created", target_id=str(employee.pk)).exists()


def test_a_duplicate_reference_or_a_login_of_another_organization_is_refused():
    first = EmployeeFactory.create()
    other_login = MembershipFactory.create().user

    with pytest.raises(ValidationError) as error:
        services.create_employee(
            organization=first.organization,
            actor=None,
            reference=first.reference.lower(),
            name="X",
            user=other_login,
        )

    assert set(error.value.message_dict) == {"reference", "user"}


def test_one_login_belongs_to_one_employee():
    first = EmployeeFactory.create()
    membership = MembershipFactory.create(organization=first.organization)
    services.update_employee(employee=first, actor=None, user=membership.user)

    with pytest.raises(ValidationError) as error:
        services.create_employee(organization=first.organization, actor=None, name="Y", user=membership.user)

    assert "user" in error.value.message_dict


def test_generating_a_month_makes_drafts_for_active_employees_once():
    organization = EmployeeFactory.create(monthly_salary=Decimal("1600.000")).organization
    EmployeeFactory.create(organization=organization, monthly_salary=Decimal("1250.000"), cnss_rate=Decimal("0"))
    EmployeeFactory.create(organization=organization, is_active=False)
    EmployeeFactory.create(organization=organization, monthly_salary=Decimal("0"))  # the owner, not paid
    EmployeeFactory.create(organization=organization, hire_date=THIS_MONTH + dt.timedelta(days=40))

    created = services.generate_month(organization=organization, actor=None, month=THIS_MONTH + dt.timedelta(days=3))
    again = services.generate_month(organization=organization, actor=None, month=THIS_MONTH)

    assert len(created) == 2
    assert again == []
    first, second = sorted(created, key=lambda record: record.gross, reverse=True)
    assert (first.month, first.status) == (THIS_MONTH, SalaryStatus.DRAFT)
    assert (first.base_salary, first.gross, first.employer_cnss, first.net) == (
        Decimal("1600.000"),
        Decimal("1600.000"),
        Decimal("273.120"),
        Decimal("1600.000"),
    )
    assert second.employer_cnss == Decimal("0.000")


def test_a_future_month_cannot_be_generated():
    organization = EmployeeFactory.create().organization
    future = (THIS_MONTH + dt.timedelta(days=40)).replace(day=1)

    with pytest.raises(ValidationError) as error:
        services.generate_month(organization=organization, actor=None, month=future)

    assert "month" in error.value.message_dict


def draft_record(**fields):
    employee = EmployeeFactory.create(monthly_salary=Decimal("1000.000"))
    services.generate_month(organization=employee.organization, actor=None, month=THIS_MONTH)
    record = selectors.salary_records_of(employee.organization).get()
    if fields:
        record = services.update_salary_record(record=record, actor=None, **fields)
    return record


def test_a_draft_is_recomputed_when_bonus_overtime_and_deductions_change():
    record = draft_record(bonus="100.000", overtime="50.500", deductions="200.000")

    assert record.gross == Decimal("1150.500")
    # 1150.500 x 17.07 % = 196.39035
    assert record.employer_cnss == Decimal("196.390")
    assert record.net == Decimal("950.500")
    assert record.expense_amount == Decimal("1346.890")


def test_deductions_above_the_gross_are_refused():
    record = draft_record()

    with pytest.raises(ValidationError) as error:
        services.update_salary_record(record=record, actor=None, deductions="1000.001")

    assert "deductions" in error.value.message_dict


def test_an_approved_salary_is_immutable_and_corrected_by_an_adjustment():
    record = draft_record(bonus="100.000")
    approved = services.approve_salary_record(record=record, actor=None)

    assert approved.status == SalaryStatus.APPROVED
    assert approved.approved_at is not None
    with pytest.raises(ValidationError):
        services.update_salary_record(record=approved, actor=None, bonus="0.000")
    with pytest.raises(ValidationError):
        services.delete_salary_record(record=approved, actor=None)
    with pytest.raises(ValidationError):
        services.approve_salary_record(record=approved, actor=None)

    services.add_adjustment(record=approved, actor=None, amount="-30.000", reason="Absence non déclarée")
    fresh = selectors.salary_record_of(approved.organization, approved.pk)
    assert fresh.net == Decimal("1100.000")
    assert selectors.due_amount(fresh) == Decimal("1070.000")


def test_an_adjustment_needs_an_approved_salary_a_reason_and_a_sensible_amount():
    record = draft_record()
    with pytest.raises(ValidationError) as error:
        services.add_adjustment(record=record, actor=None, amount="10.000", reason="x")
    assert "status" in error.value.message_dict

    approved = services.approve_salary_record(record=record, actor=None)
    with pytest.raises(ValidationError) as error:
        services.add_adjustment(record=approved, actor=None, amount="0", reason="")
    assert set(error.value.message_dict) == {"amount", "reason"}
    with pytest.raises(ValidationError) as error:
        services.add_adjustment(record=approved, actor=None, amount="-1000.001", reason="trop")
    assert "amount" in error.value.message_dict


def test_a_draft_can_be_deleted_and_regenerated():
    record = draft_record()

    services.delete_salary_record(record=record, actor=None)

    assert not selectors.salary_records_of(record.organization).exists()
    assert len(services.generate_month(organization=record.organization, actor=None, month=THIS_MONTH)) == 1


def test_approving_the_month_approves_every_draft():
    employee = EmployeeFactory.create()
    EmployeeFactory.create(organization=employee.organization)
    services.generate_month(organization=employee.organization, actor=None, month=THIS_MONTH)

    approved = services.approve_month(organization=employee.organization, actor=None, month=THIS_MONTH)

    assert len(approved) == 2
    expense = selectors.monthly_personnel_expense(employee.organization, month=THIS_MONTH)
    assert expense == Decimal("1300.000") * 2 + Decimal("221.910") * 2


def approved(record):
    return services.approve_salary_record(record=record, actor=None)


def test_a_payment_settles_salaries_and_the_unpaid_amount_falls():
    record = approved(draft_record())  # net 1000.000
    organization, employee = record.organization, record.employee

    payment = services.record_payment(
        organization=organization,
        actor=None,
        employee=employee,
        paid_on=timezone.localdate(),
        amount="400.000",
        method="cash",
        allocations=[{"salary_record": record, "amount": "400.000"}],
    )

    assert payment.number == "PS-0001"
    assert selectors.unpaid_by_employee(organization) == {employee.pk: Decimal("600.000")}
    summary = selectors.payroll_summary(organization, month=THIS_MONTH)
    assert (summary.paid, summary.outstanding, summary.unpaid_total, summary.unpaid_records) == (
        Decimal("400.000"),
        Decimal("600.000"),
        Decimal("600.000"),
        1,
    )
    # The rest, with an advance on top: 600 allocated, 50 kept as an advance.
    services.record_payment(
        organization=organization,
        actor=None,
        employee=employee,
        paid_on=timezone.localdate(),
        amount="650.000",
        method="transfer",
        reference="VIR-1",
        allocations=[{"salary_record": record, "amount": "600.000"}],
    )
    assert selectors.unpaid_by_employee(organization) == {}
    last = selectors.payments_of(organization).first()
    assert last is not None
    assert selectors.unallocated_amount(last) == Decimal("50.000")


def test_allocations_are_checked_like_supplier_payments():
    record = approved(draft_record())
    other = approved(_another_draft(record.organization))
    kwargs: dict[str, Any] = {
        "organization": record.organization,
        "actor": None,
        "employee": record.employee,
        "paid_on": timezone.localdate(),
        "method": "cash",
    }

    with pytest.raises(ValidationError) as error:
        services.record_payment(
            **kwargs,
            amount="100.000",
            allocations=[
                {"salary_record": other, "amount": "10.000"},
                {"salary_record": record, "amount": "1000.001"},
            ],
        )
    assert set(error.value.message_dict) == {"allocations.0.salary_record", "allocations.1.amount"}

    with pytest.raises(ValidationError) as error:
        services.record_payment(
            **kwargs, amount="100.000", allocations=[{"salary_record": record, "amount": "150.000"}]
        )
    assert "allocations" in error.value.message_dict

    with pytest.raises(ValidationError) as error:
        services.record_payment(
            **{**kwargs, "paid_on": timezone.localdate() + dt.timedelta(days=1)}, amount="0", allocations=[]
        )
    assert set(error.value.message_dict) == {"paid_on", "amount"}


def _another_draft(organization):
    employee = EmployeeFactory.create(organization=organization)
    services.generate_month(organization=organization, actor=None, month=THIS_MONTH)
    return selectors.salary_records_of(organization, employee_id=employee.pk).get()


def test_a_draft_cannot_be_paid_and_an_advance_is_allocated_later():
    record = draft_record()
    kwargs: dict[str, Any] = {"organization": record.organization, "actor": None, "employee": record.employee}
    today = timezone.localdate()

    with pytest.raises(ValidationError):
        services.record_payment(
            **kwargs,
            paid_on=today,
            amount="10.000",
            method="cash",
            allocations=[{"salary_record": record, "amount": "10.000"}],
        )

    advance = services.record_payment(**kwargs, paid_on=today, amount="300.000", method="cash")
    services.approve_salary_record(record=record, actor=None)
    services.allocate_payment(payment=advance, actor=None, allocations=[{"salary_record": record, "amount": "300.000"}])

    assert selectors.unpaid_by_employee(record.organization) == {record.employee_id: Decimal("700.000")}
    with pytest.raises(ValidationError):  # nothing left to allocate
        services.allocate_payment(
            payment=advance, actor=None, allocations=[{"salary_record": record, "amount": "1.000"}]
        )


def test_days_on_a_lot_keep_their_cost_and_cap_a_day_at_one():
    employee = EmployeeFactory.create(monthly_salary=Decimal("1250.000"))
    today = timezone.localdate()
    kwargs: dict[str, Any] = {
        "organization": employee.organization,
        "actor": None,
        "employee": employee,
        "work_date": today,
    }

    morning = services.add_lot_work_day(**kwargs, days="0.5")
    services.update_employee(employee=employee, actor=None, monthly_salary=Decimal("1500.000"))

    assert (morning.cost, morning.monthly_salary) == (Decimal("24.038"), Decimal("1250.000"))
    afternoon = services.add_lot_work_day(**kwargs, days="0.5", notes="Tri")
    assert afternoon.cost == Decimal("28.846")
    with pytest.raises(ValidationError) as error:
        services.add_lot_work_day(**kwargs, days="0.25")
    assert "days" in error.value.message_dict
    for bad in ("0", "1.5", "0.333", "abc"):
        with pytest.raises(ValidationError):
            services.add_lot_work_day(**{**kwargs, "work_date": today - dt.timedelta(days=1)}, days=bad)

    services.delete_lot_work_day(work_day=morning, actor=None)
    assert selectors.lot_work_days_of(employee.organization).count() == 1
