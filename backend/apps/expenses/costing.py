"""Cold-room cost per day and general costs per day, to the millime (D-041, D-058, D-059).

Pure functions: no database. Every split goes through `allocation.split_by_weight`, so the shares of an
amount always add up to it exactly.
"""

import calendar
import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from apps.core.money import money

from .allocation import split_by_weight

ZERO = Decimal("0.000")
# The client's rule (2026-10-11): a day is a 26th of the monthly amount, for salaries and general costs.
WORKING_DAYS_PER_MONTH = 26


def first_of_month(day: dt.date) -> dt.date:
    return day.replace(day=1)


def next_month(month: dt.date) -> dt.date:
    return (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def add_months(month: dt.date, count: int) -> dt.date:
    """The first day of the month `count` months after (or before, if negative) `month`."""
    index = month.year * 12 + (month.month - 1) + count
    return dt.date(index // 12, index % 12 + 1, 1)


def days_in_month(month: dt.date) -> int:
    return calendar.monthrange(month.year, month.month)[1]


def last_of_month(month: dt.date) -> dt.date:
    return month.replace(day=days_in_month(month))


def month_days(month: dt.date) -> list[dt.date]:
    return [month + dt.timedelta(days=offset) for offset in range(days_in_month(month))]


def split_evenly(amount: Decimal, parts: int) -> list[Decimal]:
    """`amount` in `parts` equal parts to the millime: they add up to `amount` exactly (the first parts
    take the extra millimes)."""
    shares = split_by_weight(amount, {index: Decimal(1) for index in range(parts)})
    return [shares[index] for index in range(parts)]


def room_month_amounts(bill: Decimal, weights: Mapping[int, Decimal]) -> dict[int, Decimal]:
    """The electricity bill shared between the cold rooms by weight: each room's part of the month, adding
    up to the bill exactly. Rooms are the keys of `weights`."""
    return split_by_weight(bill, weights)


def room_day_amounts(room_month_amount: Decimal, month: dt.date) -> dict[dt.date, Decimal]:
    """A room's part of the month spread over the days of the month (to the millime, adding up exactly)."""
    days = month_days(month)
    return dict(zip(days, split_evenly(room_month_amount, len(days)), strict=True))


def estimate_day_amount(room_month_amount: Decimal, month: dt.date) -> Decimal:
    """The daily rate of a billed month, used as the estimate for a month not billed yet: the room's
    part of that month divided by its days, rounded once to the millime."""
    return money(room_month_amount / days_in_month(month))


@dataclass(frozen=True)
class RoomCharge:
    """What one lot carries for one cold room over some days."""

    amount: Decimal
    # Kg held, summed over the days charged ("kg-days").
    kg_days: Decimal


def allocate_room_days(
    day_amounts: Mapping[dt.date, Decimal], kg_by_day: Mapping[dt.date, Mapping[int, Decimal]]
) -> dict[int, RoomCharge]:
    """Each day's cost of a cold room shared over the lots in it that day by kg held, then added up per
    lot. On a day the room is empty nobody pays (the day stays unallocated). Every day's shares add up to
    that day's amount exactly."""
    totals: dict[int, Decimal] = {}
    kg_days: dict[int, Decimal] = {}
    for day, amount in day_amounts.items():
        held = kg_by_day.get(day, {})
        for batch_id, share in split_by_weight(amount, held).items():
            totals[batch_id] = totals.get(batch_id, ZERO) + share
            kg_days[batch_id] = kg_days.get(batch_id, ZERO) + held[batch_id]
    return {batch_id: RoomCharge(amount=totals[batch_id], kg_days=kg_days[batch_id]) for batch_id in sorted(totals)}


def general_day_amount(monthly_amount: Decimal) -> Decimal:
    """A general cost "like a salary" (client, D-041): the monthly amount / 26, rounded once."""
    return money(monthly_amount / WORKING_DAYS_PER_MONTH)


def spread_over_months(amount: Decimal, months: int) -> list[Decimal]:
    """A bill covering several months, spread equally over them (adding up to the bill exactly)."""
    return split_evenly(amount, months)


def allocate_general_days(
    monthly_amount: Decimal, days: list[dt.date], kg_by_day: Mapping[dt.date, Mapping[int, Decimal]]
) -> dict[int, RoomCharge]:
    """A month's general cost: each of `days` costs monthly / 26, shared over the lots in stock that day by
    kg held (provisional, Q21). Days with nothing in stock are not charged to anyone."""
    return allocate_room_days({day: general_day_amount(monthly_amount) for day in days}, kg_by_day)
