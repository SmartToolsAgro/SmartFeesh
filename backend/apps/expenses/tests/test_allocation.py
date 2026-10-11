from decimal import Decimal

import pytest

from apps.expenses.allocation import (
    LoadedLot,
    TruckCostShare,
    TruckDayExpense,
    allocate_truck_day_costs,
    split_by_weight,
)


def D(value: str) -> Decimal:
    return Decimal(value)


def test_an_amount_is_split_in_proportion_to_the_kg():
    assert split_by_weight(D("90.000"), {1: D("30.000"), 2: D("60.000")}) == {1: D("30.000"), 2: D("60.000")}


def test_the_millimes_left_over_go_to_the_largest_remainders_and_the_total_is_exact():
    # 100 DT over three equal lots: 33.333 each and one millime left, given to the first by id.
    parts = split_by_weight(D("100.000"), {7: D("10.000"), 3: D("10.000"), 5: D("10.000")})

    assert parts == {3: D("33.334"), 5: D("33.333"), 7: D("33.333")}
    assert sum(parts.values()) == D("100.000")


def test_a_tie_on_the_remainder_goes_to_the_heavier_lot():
    # 0.005 DT over 2 kg and 3 kg: exact 0.002 and 0.003 → no tie; 0.001 over 1 kg and 1 kg → tie by id.
    assert split_by_weight(D("0.001"), {2: D("1.000"), 1: D("1.000")}) == {1: D("0.001"), 2: D("0.000")}
    # 0.010 over 1.5 kg and 3.5 kg: 0.003 and 0.007 exactly.
    assert split_by_weight(D("0.010"), {1: D("1.500"), 2: D("3.500")}) == {1: D("0.003"), 2: D("0.007")}


@pytest.mark.parametrize(
    ("amount", "weights"),
    [
        ("45.500", ["12.345", "7.001", "0.333"]),
        ("0.001", ["1.000", "2.000", "3.000"]),
        ("1000.000", ["0.001", "999.999"]),
        ("17.017", ["3.333", "3.333", "3.334", "10.000", "0.500"]),
        ("99999999.999", ["1.234", "5.678", "9.101"]),
    ],
)
def test_the_parts_always_add_up_to_the_amount_to_the_millime(amount, weights):
    parts = split_by_weight(D(amount), {index: D(weight) for index, weight in enumerate(weights)})

    assert sum(parts.values()) == D(amount)
    assert all(part == part.quantize(D("0.001")) and part >= 0 for part in parts.values())


def test_nothing_to_split_over_gives_no_part():
    assert split_by_weight(D("50.000"), {}) == {}
    assert split_by_weight(D("50.000"), {1: D("0.000")}) == {}
    assert split_by_weight(D("50.000"), {1: D("0.000"), 2: D("4.000")}) == {2: D("50.000")}


def test_each_truck_cost_of_the_day_is_split_on_its_own_over_the_lots_loaded():
    shares = allocate_truck_day_costs(
        [TruckDayExpense(expense_id=10, amount=D("60.000")), TruckDayExpense(expense_id=11, amount=D("10.000"))],
        # One lot loaded twice that day (two loads): its kg add up.
        [
            LoadedLot(batch_id=1, quantity=D("20.000")),
            LoadedLot(batch_id=2, quantity=D("30.000")),
            LoadedLot(batch_id=1, quantity=D("10.000")),
        ],
    )

    assert shares == [
        TruckCostShare(expense_id=10, batch_id=1, quantity=D("30.000"), amount=D("30.000")),
        TruckCostShare(expense_id=10, batch_id=2, quantity=D("30.000"), amount=D("30.000")),
        TruckCostShare(expense_id=11, batch_id=1, quantity=D("30.000"), amount=D("5.000")),
        TruckCostShare(expense_id=11, batch_id=2, quantity=D("30.000"), amount=D("5.000")),
    ]


def test_a_truck_day_without_load_charges_no_lot():
    assert allocate_truck_day_costs([TruckDayExpense(expense_id=1, amount=D("30.000"))], []) == []
