"""The lot result as the API sends it. The same serializers read the live result and the frozen copy:
both are `engine.to_json` dicts (amounts as strings, dates ISO)."""

from typing import Any

from rest_framework import serializers

from apps.closing.models import LotOutcome, LotResultStatus, LotState


def _money(**kwargs: Any) -> serializers.DecimalField:
    return serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3, **kwargs)


def _quantity(**kwargs: Any) -> serializers.DecimalField:
    return serializers.DecimalField(read_only=True, max_digits=12, decimal_places=3, **kwargs)


def _rate(**kwargs: Any) -> serializers.DecimalField:
    return serializers.DecimalField(read_only=True, max_digits=5, decimal_places=2, **kwargs)


class ResultBatchSerializer(serializers.Serializer[Any]):
    batch_id = serializers.IntegerField(read_only=True)
    batch_number = serializers.CharField(read_only=True)
    product_name = serializers.CharField(read_only=True)
    supplier_name = serializers.CharField(read_only=True)
    received_on = serializers.DateField(read_only=True)
    unit_cost = _money()
    received_quantity = _quantity()
    returned_quantity = _quantity()
    on_hand_quantity = _quantity()


class ResultSaleSerializer(serializers.Serializer[Any]):
    sale_id = serializers.IntegerField(read_only=True)
    sale_number = serializers.CharField(read_only=True)
    sold_on = serializers.DateField(read_only=True)
    customer = serializers.CharField(read_only=True)
    quantity = _quantity()
    unit_price = _money()
    revenue = _money()
    cost = _money()
    amount_due = _money()


class ResultStockRowSerializer(serializers.Serializer[Any]):
    movement_id = serializers.IntegerField(read_only=True)
    # The ledger's movement kind: "loss", "count_correction" or "adjustment".
    kind = serializers.CharField(read_only=True)
    occurred_on = serializers.DateField(read_only=True)
    # Signed: + kg written off, − kg found again.
    quantity = _quantity()
    unit_cost = _money()
    reason = serializers.CharField(read_only=True)
    value = _money()


class ResultCostLineSerializer(serializers.Serializer[Any]):
    kind = serializers.CharField(read_only=True)
    on = serializers.DateField(read_only=True)
    title = serializers.CharField(read_only=True)
    amount = _money()
    description = serializers.CharField(read_only=True)
    # What the line links to: "expense" or "employee" (empty: nothing to open).
    source_type = serializers.CharField(read_only=True)
    source_id = serializers.IntegerField(read_only=True, allow_null=True)
    reference = serializers.CharField(read_only=True)
    detail = serializers.CharField(read_only=True)


class ResultCostGroupSerializer(serializers.Serializer[Any]):
    # "lot" (typed on it), "truck_day", "employee", and the kinds later phases add ("cold_room"...).
    kind = serializers.CharField(read_only=True)
    total = _money()
    lines = ResultCostLineSerializer(many=True, read_only=True)


class ResultPartnerSerializer(serializers.Serializer[Any]):
    partnership_id = serializers.IntegerField(read_only=True)
    partner_id = serializers.IntegerField(read_only=True)
    partner_name = serializers.CharField(read_only=True)
    owner_capital = _money()
    partner_capital = _money()
    profit_rate = _rate()
    loss_rate = _rate()
    rate = _rate(allow_null=True)
    # Signed: + their part of a profit, − their part of a loss.
    share = _money()
    capital_deducted = _money()
    uncovered_loss = _money()
    capital_to_return = _money()
    payable_to_partner = _money()


class ResultStepSerializer(serializers.Serializer[Any]):
    code = serializers.CharField(read_only=True)
    sign = serializers.CharField(read_only=True)
    amount = _money()
    kind = serializers.CharField(read_only=True)
    rate = _rate(allow_null=True)


class ComputedResultSerializer(serializers.Serializer[Any]):
    batch = ResultBatchSerializer(read_only=True)
    quantity_sold = _quantity()
    quantity_written_off = _quantity()
    revenue = _money()
    cogs = _money()
    spoilage = _money()
    costs_total = _money()
    net_result = _money()
    outcome = serializers.ChoiceField(choices=LotOutcome.choices, read_only=True)
    owner_share = _money()
    purchase_cost = _money()
    stock_value = _money()
    sales = ResultSaleSerializer(many=True, read_only=True)
    stock_rows = ResultStockRowSerializer(many=True, read_only=True)
    cost_groups = ResultCostGroupSerializer(many=True, read_only=True)
    partner = ResultPartnerSerializer(read_only=True, allow_null=True)
    steps = ResultStepSerializer(many=True, read_only=True)


class ClosingCheckSerializer(serializers.Serializer[Any]):
    # "stock_empty", "costs_approved", "customers_paid".
    code = serializers.CharField(read_only=True)
    ok = serializers.BooleanField(read_only=True)
    blocking = serializers.BooleanField(read_only=True)
    quantity = _quantity(allow_null=True)
    count = serializers.IntegerField(read_only=True, allow_null=True)
    amount = _money(allow_null=True)


class LotClosingSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    status = serializers.ChoiceField(choices=LotResultStatus.choices, read_only=True)
    net_result = _money()
    closed_at = serializers.DateTimeField(read_only=True)
    closed_by_name = serializers.CharField(read_only=True)
    payments_unverified = serializers.BooleanField(read_only=True)
    reopened_at = serializers.DateTimeField(read_only=True, allow_null=True)
    reopened_by_name = serializers.CharField(read_only=True)
    reopen_reason = serializers.CharField(read_only=True)


class LotResultViewSerializer(serializers.Serializer[Any]):
    batch_id = serializers.IntegerField(read_only=True)
    # "open": the result so far, live. "closed": the frozen result of the closing.
    state = serializers.ChoiceField(choices=LotState.choices, read_only=True)
    result = ComputedResultSerializer(read_only=True)
    # Open lot: what a closing needs now. Closed lot: the checks as they were at the closing.
    checks = ClosingCheckSerializer(many=True, read_only=True)
    can_close = serializers.BooleanField(read_only=True)
    closing = LotClosingSerializer(read_only=True, allow_null=True)
    # Closed lot: the net result if it were computed now. A difference comes from a cost or a sale
    # recorded after the closing; it goes to the partner's next settlement (D-041, P6-T03).
    live_net_result = _money(allow_null=True)
    # Earlier closings of this lot that were reopened, newest first.
    history = LotClosingSerializer(many=True, read_only=True)


class CloseLotSerializer(serializers.Serializer[Any]):
    # The person closing confirms every cost of the lot is typed: the system cannot know it.
    costs_confirmed = serializers.BooleanField(required=False, default=False)


class ReopenLotSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(max_length=300, allow_blank=True)
