import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.boxes import selectors, services
from apps.boxes.models import BoxHolder, BoxMovement, BoxMovementKind, BoxType
from apps.core.models import AuditLog
from apps.core.tests.factories import OrganizationFactory
from apps.inventory.models import LocationKind
from apps.inventory.tests.factories import StockLocationFactory
from apps.partners.tests.factories import CustomerFactory, SupplierFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory.create()


@pytest.fixture
def cold_room(organization):
    return StockLocationFactory.create(organization=organization, kind=LocationKind.COLD_ROOM)


@pytest.fixture
def truck(organization):
    return StockLocationFactory.create(organization=organization, kind=LocationKind.TRUCK)


@pytest.fixture
def client_holder_target(organization):
    return CustomerFactory.create(organization=organization)


@pytest.fixture
def supplier(organization):
    return SupplierFactory.create(organization=organization)


def _holder(organization, **target):
    return services.holder_for(organization=organization, **target)


def _post(organization, **kwargs):
    return services.post_box_movement(organization=organization, actor=None, **kwargs)


def _balance(organization, holder, box_type=BoxType.SMALL):
    return selectors.balance_of(organization, holder, box_type)


def test_receive_from_supplier_raises_the_owed_count_and_the_cold_room(organization, cold_room, supplier):
    cold = _holder(organization, location=cold_room)
    sup = _holder(organization, supplier=supplier)

    _post(
        organization,
        kind=BoxMovementKind.RECEIVE,
        box_type=BoxType.BIG,
        count=10,
        from_holder=sup,
        to_holder=cold,
    )

    assert _balance(organization, cold, BoxType.BIG) == 10
    assert _balance(organization, sup, BoxType.BIG) == 10  # we owe the supplier 10 big boxes


def test_opening_stock_puts_the_company_boxes_in_a_location_and_owes_no_supplier(organization, cold_room):
    cold = _holder(organization, location=cold_room)

    movement = _post(organization, kind=BoxMovementKind.OPENING, box_type=BoxType.SMALL, count=50, to_holder=cold)

    assert movement.from_holder is None
    assert _balance(organization, cold) == 50
    # The boxes are the company's: the cold room is the only holder with a balance, no supplier is owed any.
    assert [(row.holder, row.box_type, row.count) for row in selectors.balances_of(organization)] == [
        (cold, BoxType.SMALL, 50)
    ]


def test_opening_stock_only_enters_a_location_from_outside_the_ledger(organization, cold_room, supplier):
    cold = _holder(organization, location=cold_room)
    sup = _holder(organization, supplier=supplier)
    client = _holder(organization, customer=CustomerFactory.create(organization=organization))

    with pytest.raises(ValidationError):  # it has no sender: boxes from a supplier are a receipt
        _post(
            organization,
            kind=BoxMovementKind.OPENING,
            box_type=BoxType.SMALL,
            count=1,
            from_holder=sup,
            to_holder=cold,
        )
    with pytest.raises(ValidationError):  # boxes already at a client are not an opening stock (D-135)
        _post(organization, kind=BoxMovementKind.OPENING, box_type=BoxType.SMALL, count=1, to_holder=client)
    with pytest.raises(ValidationError):  # nor boxes already owed to a supplier
        _post(organization, kind=BoxMovementKind.OPENING, box_type=BoxType.SMALL, count=1, to_holder=sup)
    with pytest.raises(ValidationError):  # it needs the location that holds them
        _post(organization, kind=BoxMovementKind.OPENING, box_type=BoxType.SMALL, count=1)

    assert BoxMovement.objects.for_organization(organization).count() == 0


def test_load_to_truck_moves_boxes_between_locations(organization, cold_room, truck):
    cold = _holder(organization, location=cold_room)
    tr = _holder(organization, location=truck)
    supplier = SupplierFactory.create(organization=organization)
    _post(
        organization,
        kind=BoxMovementKind.RECEIVE,
        box_type=BoxType.SMALL,
        count=8,
        from_holder=_holder(organization, supplier=supplier),
        to_holder=cold,
    )

    _post(organization, kind=BoxMovementKind.LOAD, box_type=BoxType.SMALL, count=5, from_holder=cold, to_holder=tr)

    assert _balance(organization, cold) == 3
    assert _balance(organization, tr) == 5


def test_leave_at_client_and_collect_back(organization, cold_room, truck, supplier):
    cold = _holder(organization, location=cold_room)
    tr = _holder(organization, location=truck)
    client = _holder(organization, customer=CustomerFactory.create(organization=organization))
    _post(
        organization,
        kind=BoxMovementKind.RECEIVE,
        box_type=BoxType.SMALL,
        count=6,
        from_holder=_holder(organization, supplier=supplier),
        to_holder=cold,
    )
    _post(organization, kind=BoxMovementKind.LOAD, box_type=BoxType.SMALL, count=6, from_holder=cold, to_holder=tr)

    _post(organization, kind=BoxMovementKind.LEAVE, box_type=BoxType.SMALL, count=4, from_holder=tr, to_holder=client)
    assert _balance(organization, client) == 4
    assert _balance(organization, tr) == 2

    _post(organization, kind=BoxMovementKind.COLLECT, box_type=BoxType.SMALL, count=3, from_holder=client, to_holder=tr)
    assert _balance(organization, client) == 1
    assert _balance(organization, tr) == 5


def test_return_to_supplier_lowers_what_we_owe(organization, cold_room, supplier):
    cold = _holder(organization, location=cold_room)
    sup = _holder(organization, supplier=supplier)
    _post(organization, kind=BoxMovementKind.RECEIVE, box_type=BoxType.BIG, count=7, from_holder=sup, to_holder=cold)

    _post(organization, kind=BoxMovementKind.RETURN, box_type=BoxType.BIG, count=5, from_holder=cold, to_holder=sup)

    assert _balance(organization, sup, BoxType.BIG) == 2
    assert _balance(organization, cold, BoxType.BIG) == 2


def test_write_off_needs_a_reason_and_leaves_the_ledger(organization, cold_room, supplier):
    cold = _holder(organization, location=cold_room)
    _post(
        organization,
        kind=BoxMovementKind.RECEIVE,
        box_type=BoxType.SMALL,
        count=4,
        from_holder=_holder(organization, supplier=supplier),
        to_holder=cold,
    )

    with pytest.raises(ValidationError):
        _post(organization, kind=BoxMovementKind.WRITE_OFF, box_type=BoxType.SMALL, count=1, from_holder=cold)
    with pytest.raises(ValidationError):
        _post(
            organization,
            kind=BoxMovementKind.WRITE_OFF,
            box_type=BoxType.SMALL,
            count=1,
            from_holder=cold,
            reason="   ",
        )
    assert _balance(organization, cold) == 4

    movement = _post(
        organization,
        kind=BoxMovementKind.WRITE_OFF,
        box_type=BoxType.SMALL,
        count=1,
        from_holder=cold,
        reason="Cassée au déchargement",
    )

    assert movement.to_holder is None
    assert movement.reason == "Cassée au déchargement"
    assert _balance(organization, cold) == 3


def test_write_off_reason_is_also_enforced_by_the_database(organization, cold_room, supplier):
    cold = _holder(organization, location=cold_room)
    _post(
        organization,
        kind=BoxMovementKind.RECEIVE,
        box_type=BoxType.SMALL,
        count=2,
        from_holder=_holder(organization, supplier=supplier),
        to_holder=cold,
    )
    with pytest.raises(IntegrityError):
        BoxMovement.objects.create(
            organization=organization,
            kind=BoxMovementKind.WRITE_OFF,
            box_type=BoxType.SMALL,
            count=1,
            from_holder=cold,
            reason="",
        )


def test_refuses_a_movement_that_would_make_a_balance_negative(organization, cold_room, truck, supplier):
    cold = _holder(organization, location=cold_room)
    tr = _holder(organization, location=truck)
    client = _holder(organization, customer=CustomerFactory.create(organization=organization))
    _post(
        organization,
        kind=BoxMovementKind.RECEIVE,
        box_type=BoxType.SMALL,
        count=2,
        from_holder=_holder(organization, supplier=supplier),
        to_holder=cold,
    )

    with pytest.raises(ValidationError):
        _post(organization, kind=BoxMovementKind.LOAD, box_type=BoxType.SMALL, count=3, from_holder=cold, to_holder=tr)
    with pytest.raises(ValidationError):
        _post(
            organization, kind=BoxMovementKind.LEAVE, box_type=BoxType.SMALL, count=1, from_holder=tr, to_holder=client
        )
    with pytest.raises(ValidationError):
        _post(
            organization,
            kind=BoxMovementKind.COLLECT,
            box_type=BoxType.SMALL,
            count=1,
            from_holder=client,
            to_holder=cold,
        )

    assert BoxMovement.objects.for_organization(organization).count() == 1
    assert _balance(organization, cold) == 2


def test_refused_return_to_supplier_above_what_we_owe(organization, cold_room, supplier):
    cold = _holder(organization, location=cold_room)
    sup = _holder(organization, supplier=supplier)
    _post(organization, kind=BoxMovementKind.RECEIVE, box_type=BoxType.BIG, count=2, from_holder=sup, to_holder=cold)

    with pytest.raises(ValidationError):
        _post(organization, kind=BoxMovementKind.RETURN, box_type=BoxType.BIG, count=3, from_holder=cold, to_holder=sup)
    assert _balance(organization, sup, BoxType.BIG) == 2


def test_box_types_are_counted_separately(organization, cold_room, supplier):
    cold = _holder(organization, location=cold_room)
    sup = _holder(organization, supplier=supplier)
    _post(organization, kind=BoxMovementKind.RECEIVE, box_type=BoxType.SMALL, count=5, from_holder=sup, to_holder=cold)

    assert _balance(organization, cold, BoxType.SMALL) == 5
    assert _balance(organization, cold, BoxType.BIG) == 0
    with pytest.raises(ValidationError):
        _post(organization, kind=BoxMovementKind.WRITE_OFF, box_type=BoxType.BIG, count=1, from_holder=cold, reason="x")


def test_each_kind_checks_the_holder_kinds(organization, cold_room, truck, supplier):
    cold = _holder(organization, location=cold_room)
    tr = _holder(organization, location=truck)
    sup = _holder(organization, supplier=supplier)

    with pytest.raises(ValidationError):  # a receipt must come from a supplier
        _post(
            organization,
            kind=BoxMovementKind.RECEIVE,
            box_type=BoxType.SMALL,
            count=1,
            from_holder=cold,
            to_holder=cold,
        )
    with pytest.raises(ValidationError):  # a load goes into a truck, not a cold room
        _post(organization, kind=BoxMovementKind.LOAD, box_type=BoxType.SMALL, count=1, from_holder=tr, to_holder=cold)
    with pytest.raises(ValidationError):  # a load cannot stay where it is
        _post(organization, kind=BoxMovementKind.LOAD, box_type=BoxType.SMALL, count=1, from_holder=tr, to_holder=tr)
    with pytest.raises(ValidationError):  # a write-off has no destination
        _post(
            organization,
            kind=BoxMovementKind.WRITE_OFF,
            box_type=BoxType.SMALL,
            count=1,
            from_holder=cold,
            to_holder=sup,
            reason="x",
        )
    with pytest.raises(ValidationError):  # a leave goes to a client
        _post(
            organization, kind=BoxMovementKind.LEAVE, box_type=BoxType.SMALL, count=1, from_holder=cold, to_holder=sup
        )
    with pytest.raises(ValidationError):  # a collect comes from a client
        _post(
            organization,
            kind=BoxMovementKind.COLLECT,
            box_type=BoxType.SMALL,
            count=1,
            from_holder=cold,
            to_holder=cold,
        )
    with pytest.raises(ValidationError):  # missing holder on a side that needs one
        _post(
            organization, kind=BoxMovementKind.LEAVE, box_type=BoxType.SMALL, count=1, from_holder=cold, to_holder=None
        )


def test_unknown_kind_or_box_type_is_refused(organization, cold_room):
    cold = _holder(organization, location=cold_room)
    with pytest.raises(ValidationError):
        _post(organization, kind="teleport", box_type=BoxType.SMALL, count=1, from_holder=cold)
    with pytest.raises(ValidationError):
        _post(organization, kind=BoxMovementKind.WRITE_OFF, box_type="pallet", count=1, from_holder=cold, reason="x")


@pytest.mark.parametrize("count", [0, -1, 1.0, 2.5, True, "3", None])
def test_counts_are_positive_whole_numbers(organization, cold_room, supplier, count):
    cold = _holder(organization, location=cold_room)
    sup = _holder(organization, supplier=supplier)
    with pytest.raises(ValidationError):
        _post(
            organization,
            kind=BoxMovementKind.RECEIVE,
            box_type=BoxType.SMALL,
            count=count,
            from_holder=sup,
            to_holder=cold,
        )
    assert BoxMovement.objects.for_organization(organization).count() == 0


def test_stored_count_is_an_integer(organization, cold_room, supplier):
    cold = _holder(organization, location=cold_room)
    sup = _holder(organization, supplier=supplier)
    movement = _post(
        organization, kind=BoxMovementKind.RECEIVE, box_type=BoxType.SMALL, count=3, from_holder=sup, to_holder=cold
    )
    movement.refresh_from_db()
    assert type(movement.count) is int
    assert selectors.signed_balance(cold, BoxType.SMALL) == 3


def test_holder_from_another_organization_is_refused(organization, cold_room, supplier):
    other = OrganizationFactory.create()
    foreign_cold = StockLocationFactory.create(organization=other, kind=LocationKind.COLD_ROOM)
    foreign_holder = BoxHolder.objects.create(organization=other, location=foreign_cold)
    sup = _holder(organization, supplier=supplier)

    with pytest.raises(ValidationError):
        _post(
            organization,
            kind=BoxMovementKind.RECEIVE,
            box_type=BoxType.SMALL,
            count=1,
            from_holder=sup,
            to_holder=foreign_holder,
        )
    with pytest.raises(ValidationError):
        services.holder_for(organization=organization, location=foreign_cold)


def test_organization_isolation_in_balances_and_history(organization, supplier):
    other = OrganizationFactory.create()
    cold_a = StockLocationFactory.create(organization=organization, kind=LocationKind.COLD_ROOM)
    cold_b = StockLocationFactory.create(organization=other, kind=LocationKind.COLD_ROOM)
    holder_a = _holder(organization, location=cold_a)
    holder_b = _holder(other, location=cold_b)
    sup_b = services.holder_for(organization=other, supplier=SupplierFactory.create(organization=other))
    _post(other, kind=BoxMovementKind.RECEIVE, box_type=BoxType.SMALL, count=9, from_holder=sup_b, to_holder=holder_b)

    assert selectors.balances_of(organization) == []
    assert _balance(organization, holder_a) == 0
    assert list(selectors.movements_of(organization)) == []
    assert _balance(other, holder_b) == 9


def test_exactly_one_target_per_holder(organization, cold_room, supplier):
    with pytest.raises(ValidationError):
        services.holder_for(organization=organization, location=cold_room, supplier=supplier)
    with pytest.raises(ValidationError):
        services.holder_for(organization=organization)
    assert _holder(organization, location=cold_room) == _holder(organization, location=cold_room)


def test_movement_is_audited_and_history_filters_by_holder(organization, cold_room, truck, supplier):
    cold = _holder(organization, location=cold_room)
    tr = _holder(organization, location=truck)
    sup = _holder(organization, supplier=supplier)
    _post(organization, kind=BoxMovementKind.RECEIVE, box_type=BoxType.SMALL, count=4, from_holder=sup, to_holder=cold)
    _post(organization, kind=BoxMovementKind.LOAD, box_type=BoxType.SMALL, count=1, from_holder=cold, to_holder=tr)

    assert AuditLog.objects.for_organization(organization).filter(action="box.moved").count() == 2
    assert [m.kind for m in selectors.movements_of(organization, holder=tr)] == [BoxMovementKind.LOAD]
    assert selectors.movements_of(organization, box_type=BoxType.BIG).count() == 0
    assert selectors.movements_of(organization, box_type=BoxType.SMALL).count() == 2


def test_movements_are_append_only(organization, cold_room, supplier):
    cold = _holder(organization, location=cold_room)
    movement = _post(
        organization,
        kind=BoxMovementKind.RECEIVE,
        box_type=BoxType.SMALL,
        count=1,
        from_holder=_holder(organization, supplier=supplier),
        to_holder=cold,
    )
    movement.count = 5
    with pytest.raises(TypeError):
        movement.save()
    with pytest.raises(TypeError):
        movement.delete()
    with pytest.raises(TypeError):
        BoxMovement.objects.for_organization(organization).update(count=5)
    with pytest.raises(TypeError):
        BoxMovement.objects.for_organization(organization).delete()
