"""Demo cold-room cost and general costs (P5-T02, P5-T05): the -20 degree room weighs twice the fresh one,
last month's electricity bill is typed and approved (so this month shows an estimate), a monthly rent,
accountant and insurance generated and approved for this month, and a year of insurance spread over 12
months.

Running it again creates nothing. Dates are relative to the day of the seed.
"""

import datetime as dt

from django.utils import timezone

from apps.core.models import Organization, User
from apps.expenses import selectors, services


def first_of_month(day: dt.date) -> dt.date:
    return day.replace(day=1)


def add_months(month: dt.date, count: int) -> dt.date:
    index = month.year * 12 + (month.month - 1) + count
    return dt.date(index // 12, index % 12 + 1, 1)


FROZEN_ROOM = "Chambre froide 2 (congelé)"
# name, category code, monthly amount, payee, payment method
MONTHLY = [
    ("Loyer du dépôt", "rent", "1200.000", "Société Immobilière Sfax", "transfer"),
    ("Honoraires comptables", "accountant", "300.000", "Cabinet Trabelsi", "cheque"),
]
YEAR_INSURANCE = "Assurance annuelle du dépôt"
LAST_BILL = "684.250"


def seed_costing(*, organization: Organization, actor: User | None) -> int:
    """Create the demo cold-room weights, electricity bill, monthly costs and spread bill that do not exist
    yet. Returns how many records were made."""
    created = 0
    this_month = first_of_month(timezone.localdate())
    last_month = add_months(this_month, -1)

    rooms = {room.name: room for room in selectors.cold_rooms(organization)}
    frozen = rooms.get(FROZEN_ROOM)
    if frozen is not None and selectors.room_weights(organization)[frozen.pk] != 2:
        services.set_cold_room_weight(organization=organization, actor=actor, location=frozen, weight="2")
        created += 1
    if rooms and not selectors.electricity_bills_of(organization).filter(month=last_month).exists():
        services.create_electricity_bill(
            organization=organization,
            actor=actor,
            month=last_month,
            amount=LAST_BILL,
            payee="STEG",
            payment_method="transfer",
            approve=True,
        )
        created += 1

    known = {cost.name for cost in selectors.recurring_costs_of(organization)}
    for name, code, amount, payee, method in MONTHLY:
        if name not in known:
            services.create_recurring_cost(
                organization=organization,
                actor=actor,
                name=name,
                category=selectors.category_by_code(organization, code),
                monthly_amount=amount,
                payee=payee,
                payment_method=method,
                start_month=add_months(this_month, -6),
            )
            created += 1
    created += len(
        services.generate_recurring_costs(organization=organization, actor=actor, month=this_month, approve=True)
    )

    if not any(period.expense.description == YEAR_INSURANCE for period in selectors.general_periods_of(organization)):
        services.create_general_cost(
            organization=organization,
            actor=actor,
            spent_on=this_month,
            category=selectors.category_by_code(organization, "administration"),
            amount="1560.000",
            first_month=this_month,
            months=12,
            description=YEAR_INSURANCE,
            payee="Assurances Star",
            approve=True,
        )
        created += 1
    return created
