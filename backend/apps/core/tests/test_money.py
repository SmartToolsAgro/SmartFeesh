from decimal import Decimal

import pytest

from apps.core.money import MoneyField, QuantityField, line_total, money, quantity


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1.0004", "1.000"),
        ("1.0005", "1.001"),  # half goes up, not to the even neighbour
        ("1.0015", "1.002"),
        ("2.0025", "2.003"),
        ("-1.0005", "-1.001"),  # half goes away from zero
        ("0", "0.000"),
        (12, "12.000"),
        (Decimal("99999999999.9994"), "99999999999.999"),
    ],
)
def test_money_rounds_half_up_to_millimes(value, expected):
    result = money(value)

    assert result == Decimal(expected)
    assert result.as_tuple().exponent == -3


def test_quantity_rounds_half_up_to_grams():
    assert quantity("12.3455") == Decimal("12.346")


@pytest.mark.parametrize("value", [1.5, 0.1 + 0.2, True, None])
def test_floats_and_other_types_are_refused(value):
    with pytest.raises(TypeError):
        money(value)


def test_line_total_rounds_once_after_multiplying():
    # 2.345 kg at 42.500 DT = 99.6625, which rounds up to 99.663.
    assert line_total("2.345", "42.500") == Decimal("99.663")
    # The product is rounded, not the inputs: rounding 0.3335 first would give 1.002.
    assert line_total("0.3335", "3") == Decimal("1.001")


def test_fields_default_to_three_decimal_places():
    money_field = MoneyField()
    quantity_field = QuantityField()

    assert (money_field.max_digits, money_field.decimal_places) == (14, 3)
    assert (quantity_field.max_digits, quantity_field.decimal_places) == (12, 3)
