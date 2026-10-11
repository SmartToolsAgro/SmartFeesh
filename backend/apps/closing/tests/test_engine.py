"""The lot result engine, worked out by hand to the millime (P6-T02, D-061). No database.

The reference lot: 100 kg of dorade bought at 20.000 DT/kg (2 000.000 DT), sold in three pieces at three
prices, 5 kg spoiled, four kinds of costs. Every figure below was computed by hand, not by the code.
"""

import datetime as dt
import random
from decimal import Decimal

import pytest

from apps.closing import engine
from apps.closing.engine import CostRow, LotSnapshot, PartnershipTerms, SaleRow, StockRow

D = Decimal
DAY = dt.date(2026, 10, 1)


def sale(number: int, kg: str, price: str, revenue: str, cost: str, due: str = "0.000") -> SaleRow:
    return SaleRow(
        sale_id=number,
        sale_number=f"VE-{number:04d}",
        sold_on=DAY,
        customer=f"Client {number}",
        quantity=D(kg),
        unit_price=D(price),
        revenue=D(revenue),
        cost=D(cost),
        amount_due=D(due),
    )


# 40 kg × 32.500 = 1 300.000 (cost 40 × 20 = 800); 35 kg × 30.000 = 1 050.000 (700); 20 kg × 28.750 = 575.000
# (400). Revenue 2 925.000, purchase cost of the kg sold 1 900.000.
PIECES = (
    sale(1, "40.000", "32.500", "1300.000", "800.000"),
    sale(2, "35.000", "30.000", "1050.000", "700.000"),
    sale(3, "20.000", "28.750", "575.000", "400.000"),
)
# 5 kg spoiled at 20.000: 100.000.
SPOILED = (StockRow(movement_id=9, kind="loss", occurred_on=DAY, quantity=D("5.000"), unit_cost=D("20.000")),)
# Transport 120.000 and a day labourer 40.000 typed on the lot, 28.333 of a truck day, half a day of an
# employee paid 2 600.000 a month: 0.5 × 2 600 / 26 = 50.000. Costs 238.333.
COSTS = (
    CostRow(kind="lot", on=DAY, title="Transport", amount=D("120.000"), source_type="expense", source_id=1),
    CostRow(
        kind="lot", on=DAY, title="Main-d'œuvre journalière", amount=D("40.000"), source_type="expense", source_id=2
    ),
    CostRow(kind="truck_day", on=DAY, title="Carburant", amount=D("28.333"), source_type="expense", source_id=3),
    CostRow(kind="employee", on=DAY, title="Karim", amount=D("50.000"), source_type="employee", source_id=1),
)


def terms(capital: str = "1000.000", profit: str = "40.00", loss: str = "25.00", owner: str = "1000.000"):
    return PartnershipTerms(
        partnership_id=1,
        partner_id=4,
        partner_name="Pêcherie Kerkennah",
        owner_capital=D(owner),
        partner_capital=D(capital),
        profit_rate=D(profit),
        loss_rate=D(loss),
    )


def snapshot(sales=PIECES, stock_rows=SPOILED, costs=COSTS, partnership=None, on_hand="0.000") -> LotSnapshot:
    return LotSnapshot(
        batch_id=1,
        batch_number="L-0001",
        product_name="Dorade",
        supplier_name="Pêcherie Kerkennah",
        received_on=DAY,
        unit_cost=D("20.000"),
        received_quantity=D("100.000"),
        returned_quantity=D("0.000"),
        on_hand_quantity=D(on_hand),
        sales=sales,
        stock_rows=stock_rows,
        costs=costs,
        partnership=partnership,
    )


def steps(result: engine.ComputedResult) -> list[tuple[str, str, str]]:
    return [(step.code, step.kind, str(step.amount)) for step in result.steps]


def test_a_profit_lot_sold_in_pieces_shares_the_profit_at_the_profit_rate():
    result = engine.lot_result(snapshot(partnership=terms()))

    assert result.revenue == D("2925.000")
    assert result.cogs == D("1900.000")
    assert result.spoilage == D("100.000")
    assert [(group.kind, group.total) for group in result.cost_groups] == [
        ("lot", D("160.000")),
        ("truck_day", D("28.333")),
        ("employee", D("50.000")),
    ]
    assert result.costs_total == D("238.333")
    # 2 925.000 − 1 900.000 − 100.000 − 238.333
    assert result.net_result == D("686.667")
    assert result.outcome == "profit"
    partner = result.partner
    assert partner is not None
    # 686.667 × 40 % = 274.6668 → 274.667; the owner keeps 412.000.
    assert partner.rate == D("40.00")
    assert partner.share == D("274.667")
    assert result.owner_share == D("412.000")
    assert partner.capital_deducted == D("0.000")
    assert partner.uncovered_loss == D("0.000")
    assert partner.capital_to_return == D("1000.000")
    assert partner.payable_to_partner == D("1274.667")
    assert result.quantity_sold == D("95.000")
    assert result.quantity_written_off == D("5.000")
    assert result.purchase_cost == D("2000.000")
    assert result.stock_value == D("0.000")
    assert steps(result) == [
        ("revenue", "", "2925.000"),
        ("cogs", "", "1900.000"),
        ("spoilage", "", "100.000"),
        ("cost", "lot", "160.000"),
        ("cost", "truck_day", "28.333"),
        ("cost", "employee", "50.000"),
        ("net_result", "", "686.667"),
        ("partner_share", "", "274.667"),
        ("owner_share", "", "412.000"),
        ("partner_capital", "", "1000.000"),
        ("capital_to_return", "", "1000.000"),
        ("profit_share", "", "274.667"),
        ("payable_to_partner", "", "1274.667"),
    ]


# The same lot sold badly: 75 kg at its cost (20.000) and the last 20 kg given away. Revenue 1 500.000 for
# the same 95 kg (purchase cost 1 900.000).
LOSS_SALES = (
    sale(1, "40.000", "20.000", "800.000", "800.000"),
    sale(2, "35.000", "20.000", "700.000", "700.000"),
    sale(3, "20.000", "0.000", "0.000", "400.000"),
)


def test_a_loss_is_carried_at_the_loss_rate_and_taken_from_the_capital():
    result = engine.lot_result(snapshot(sales=LOSS_SALES, partnership=terms()))

    # 1 500.000 − 1 900.000 − 100.000 − 238.333
    assert result.revenue == D("1500.000")
    assert result.net_result == D("-738.333")
    assert result.outcome == "loss"
    partner = result.partner
    assert partner is not None
    # 738.333 × 25 % = 184.58325 → 184.583, taken from 1 000.000 of capital.
    assert partner.rate == D("25.00")
    assert partner.share == D("-184.583")
    assert partner.capital_deducted == D("184.583")
    assert partner.uncovered_loss == D("0.000")
    assert partner.capital_to_return == D("815.417")
    assert partner.payable_to_partner == D("815.417")
    # The owner carries the rest of the loss: −738.333 + 184.583.
    assert result.owner_share == D("-553.750")
    assert ("capital_deducted", "", "184.583") in steps(result)
    assert "profit_share" not in [code for code, _kind, _amount in steps(result)]


def test_a_loss_share_beyond_the_capital_is_carried_as_owed_by_the_partner():
    result = engine.lot_result(snapshot(sales=LOSS_SALES, partnership=terms(capital="100.000")))

    partner = result.partner
    assert partner is not None
    # Loss share 184.583: the 100.000 of capital goes to zero, 84.583 is owed (D-031, provisional).
    assert partner.capital_deducted == D("100.000")
    assert partner.uncovered_loss == D("84.583")
    assert partner.capital_to_return == D("0.000")
    assert partner.payable_to_partner == D("0.000")
    assert result.owner_share == D("-553.750")
    assert steps(result)[-1] == ("uncovered_loss", "", "84.583")


def test_a_partner_without_capital_owes_their_whole_loss_share():
    result = engine.lot_result(snapshot(sales=LOSS_SALES, partnership=terms(capital="0.000")))

    assert result.partner is not None
    assert result.partner.capital_deducted == D("0.000")
    assert result.partner.uncovered_loss == D("184.583")


def test_the_two_rates_differ_and_each_applies_to_its_own_case():
    profit = engine.lot_result(snapshot(partnership=terms(profit="30.00", loss="20.00")))
    loss = engine.lot_result(snapshot(sales=LOSS_SALES, partnership=terms(profit="30.00", loss="20.00")))

    assert profit.partner is not None
    assert loss.partner is not None
    # 686.667 × 30 % = 206.0001 → 206.000
    assert (profit.partner.rate, profit.partner.share, profit.owner_share) == (
        D("30.00"),
        D("206.000"),
        D("480.667"),
    )
    # 738.333 × 20 % = 147.6666 → 147.667
    assert (loss.partner.rate, loss.partner.share, loss.owner_share) == (D("20.00"), D("-147.667"), D("-590.666"))
    assert loss.partner.capital_to_return == D("852.333")


def test_a_zero_result_shares_nothing():
    # 2 000.000 sold for 1 900.000 of goods and 100.000 of transport.
    result = engine.lot_result(
        snapshot(
            sales=(sale(1, "95.000", "21.053", "2000.000", "1900.000"),),
            stock_rows=(),
            costs=(CostRow(kind="lot", on=DAY, title="Transport", amount=D("100.000")),),
            partnership=terms(),
        )
    )

    assert result.net_result == D("0.000")
    assert result.outcome == "zero"
    assert result.partner is not None
    assert result.partner.rate is None
    assert result.partner.share == D("0.000")
    assert result.owner_share == D("0.000")
    assert result.partner.capital_to_return == D("1000.000")


def test_a_share_is_rounded_half_up_once_and_the_owner_takes_the_rest():
    # Net 10.005 at 50 %: 5.0025 → 5.003 for the partner, 5.002 for the owner.
    result = engine.lot_result(
        snapshot(
            sales=(sale(1, "1.000", "30.005", "30.005", "20.000"),),
            stock_rows=(),
            costs=(),
            partnership=terms(profit="50.00"),
        )
    )

    assert result.net_result == D("10.005")
    assert result.partner is not None
    assert result.partner.share == D("5.003")
    assert result.owner_share == D("5.002")


def test_an_open_lot_shows_its_result_so_far_and_the_stock_still_held_at_cost():
    # Only the first piece sold, 60 kg still in the cold room, no cost yet.
    result = engine.lot_result(snapshot(sales=PIECES[:1], stock_rows=(), costs=(), on_hand="60.000"))

    assert result.net_result == D("500.000")
    assert result.owner_share == D("500.000")
    assert result.partner is None
    # 60 kg × 20.000: still an asset, not a cost.
    assert result.stock_value == D("1200.000")


def test_kilos_found_at_a_count_reduce_the_written_off_value():
    rows = (
        StockRow(movement_id=1, kind="loss", occurred_on=DAY, quantity=D("5.000"), unit_cost=D("20.000")),
        StockRow(movement_id=2, kind="count_correction", occurred_on=DAY, quantity=D("-1.250"), unit_cost=D("20.000")),
    )
    result = engine.lot_result(snapshot(stock_rows=rows))

    assert result.spoilage == D("75.000")
    assert result.quantity_written_off == D("3.750")


def test_a_cost_kind_the_engine_does_not_know_yet_is_listed_after_the_known_ones():
    costs = (
        CostRow(kind="rent_share", on=DAY, title="Loyer", amount=D("12.500")),
        CostRow(kind="cold_room", on=DAY, title="Chambre froide 1", amount=D("31.250")),
        *COSTS,
    )
    result = engine.lot_result(snapshot(costs=costs))

    assert [group.kind for group in result.cost_groups] == ["lot", "truck_day", "employee", "cold_room", "rent_share"]
    assert result.costs_total == D("282.083")
    assert result.net_result == D("642.917")


def test_the_json_copy_keeps_every_amount_as_a_string():
    data = engine.to_json(engine.lot_result(snapshot(partnership=terms())))

    assert data["net_result"] == "686.667"
    assert data["partner"]["share"] == "274.667"
    assert data["sales"][0]["sold_on"] == "2026-10-01"
    assert data["cost_groups"][0]["lines"][0]["title"] == "Transport"
    assert data["stock_rows"][0]["value"] == "100.000"
    assert data["steps"][0] == {"code": "revenue", "sign": "+", "amount": "2925.000", "kind": "", "rate": None}


@pytest.mark.parametrize("seed", range(5))
def test_shares_always_add_up_to_the_net_result(seed):
    """Property: for any net result, rates and capital, partner share + owner share = net result to the
    millime, the capital never goes below zero, and deducted + owed = the loss share."""
    draw = random.Random(seed)
    for _ in range(400):
        net = D(draw.randint(-5_000_000, 5_000_000)) / 1000
        partnership = terms(
            capital=str(D(draw.randint(0, 3_000_000)) / 1000),
            profit=str(D(draw.randint(0, 10_000)) / 100),
            loss=str(D(draw.randint(0, 10_000)) / 100),
        )
        share = engine.partner_share(partnership, net)
        owner = net - share.share
        assert share.share + owner == net
        assert share.share == share.share.quantize(D("0.001"))
        assert share.capital_to_return >= 0
        assert share.capital_deducted + share.capital_to_return == partnership.partner_capital
        if net < 0:
            assert share.capital_deducted + share.uncovered_loss == -share.share
            assert share.share <= 0
        else:
            assert share.uncovered_loss == 0
            assert share.share >= 0
