from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import AuditLog
from apps.core.tests.factories import OrganizationFactory
from apps.expenses import selectors, services
from apps.expenses.models import Expense, ExpenseCategory, ExpenseStatus

from .conftest import category, days_ago, load, receive

pytestmark = pytest.mark.django_db

YEAR = timezone.localdate().year


def spend(organization, actor, cat, amount, **fields):
    fields.setdefault("spent_on", timezone.localdate())
    return services.create_expense(organization=organization, actor=actor, category=cat, amount=amount, **fields)


# ---- categories ----


def test_every_organization_starts_with_the_default_categories_in_the_brief_order(organization):
    codes = list(selectors.categories_of(organization).values_list("code", flat=True))

    assert codes == [code for code, _name in services.DEFAULT_CATEGORIES]
    assert selectors.category_by_code(organization, "day_labour").name == "Main-d'œuvre journalière"
    services.ensure_default_categories(organization=organization)
    assert ExpenseCategory.objects.for_organization(organization).count() == len(services.DEFAULT_CATEGORIES)


def test_the_owner_adds_renames_and_archives_his_own_categories(organization, actor):
    glace = services.create_category(organization=organization, actor=actor, name="  Glace   paillette ")

    assert (glace.name, glace.code) == ("Glace paillette", "")
    assert list(selectors.categories_of(organization))[-1] == glace
    with pytest.raises(ValidationError) as error:
        services.create_category(organization=organization, actor=actor, name="carburant")
    assert "name" in error.value.message_dict
    services.update_category(category=glace, actor=actor, name="Glace", is_active=False)
    assert glace not in selectors.categories_of(organization)
    assert glace in selectors.categories_of(organization, status="archived")


def test_a_default_category_is_renamed_but_never_archived(organization, actor, fuel):
    services.update_category(category=fuel, actor=actor, name="Gasoil")
    assert selectors.category_by_code(organization, "fuel").name == "Gasoil"

    with pytest.raises(ValidationError) as error:
        services.update_category(category=fuel, actor=actor, is_active=False)
    assert "is_active" in error.value.message_dict


# ---- expenses ----


def test_an_expense_is_a_draft_with_a_number_until_approved(organization, actor, fuel):
    expense = spend(organization, actor, fuel, "45.500", description=" Gasoil ", payee="Station Agil")

    assert (expense.number, expense.status, expense.amount) == (
        f"DP-{YEAR}-0001",
        ExpenseStatus.DRAFT,
        Decimal("45.500"),
    )
    assert (expense.description, expense.entered_by) == ("Gasoil", actor)
    approved = services.approve_expense(expense=expense, actor=actor)
    assert (approved.status, approved.decided_by) == (ExpenseStatus.APPROVED, actor)
    assert spend(organization, actor, fuel, "1").number == f"DP-{YEAR}-0002"
    assert list(AuditLog.objects.filter(target_id=str(expense.pk)).values_list("action", flat=True).order_by("id")) == [
        "expense.created",
        "expense.approved",
    ]


def test_an_approved_or_refused_expense_never_changes(organization, actor, fuel):
    approved = spend(organization, actor, fuel, "10", approve=True)
    refused = services.reject_expense(expense=spend(organization, actor, fuel, "20"), actor=actor, reason="Doublon")

    assert refused.rejection_reason == "Doublon"
    for expense in (approved, refused):
        with pytest.raises(ValidationError):
            services.update_expense(expense=expense, actor=actor, spent_on=expense.spent_on, category=fuel, amount="5")
        with pytest.raises(ValidationError):
            services.approve_expense(expense=expense, actor=actor)
        with pytest.raises(ValidationError):
            services.delete_expense(expense=expense, actor=actor)


def test_a_refusal_needs_a_reason(organization, actor, fuel):
    with pytest.raises(ValidationError) as error:
        services.reject_expense(expense=spend(organization, actor, fuel, "20"), actor=actor, reason="  ")
    assert "reason" in error.value.message_dict


def test_a_submitted_expense_waits_for_approval_and_can_be_corrected_but_not_deleted(organization, actor, fuel):
    # How a driver's expense arrives from the phone (P3-T04).
    waiting = spend(organization, actor, fuel, "30", submit=True)
    assert waiting.status == ExpenseStatus.PENDING

    corrected = services.update_expense(
        expense=waiting, actor=actor, spent_on=waiting.spent_on, category=fuel, amount="35.250"
    )
    assert (corrected.status, corrected.amount) == (ExpenseStatus.PENDING, Decimal("35.250"))
    with pytest.raises(ValidationError):
        services.delete_expense(expense=waiting, actor=actor)
    draft = spend(organization, actor, fuel, "1")
    services.delete_expense(expense=draft, actor=actor)
    assert not Expense.objects.filter(pk=draft.pk).exists()


def test_amounts_dates_and_targets_are_checked(organization, actor, fuel, cold_room, truck):
    lot = receive(organization, "Dorade", "10", cold_room, received_on=days_ago(2))
    with pytest.raises(ValidationError) as error:
        spend(organization, actor, fuel, "12.3456", spent_on=days_ago(-1), batch=lot, truck=truck)
    assert set(error.value.message_dict) == {"amount", "spent_on", "truck"}
    with pytest.raises(ValidationError) as error:
        spend(organization, actor, fuel, "0", payment_method="crypto")
    assert set(error.value.message_dict) == {"amount", "payment_method"}
    with pytest.raises(ValidationError) as error:
        spend(organization, actor, fuel, "5", batch=lot, spent_on=days_ago(3))
    assert "batch" in error.value.message_dict


def test_a_day_labourers_day_is_not_typed_as_a_plain_expense(organization, actor):
    with pytest.raises(ValidationError) as error:
        spend(organization, actor, category(organization, "day_labour"), "40")
    assert "category" in error.value.message_dict


def test_another_organizations_category_lot_or_truck_is_refused(organization, actor, fuel):
    other = OrganizationFactory.create()
    with pytest.raises(ValidationError) as error:
        spend(organization, actor, category(other, "fuel"), "5")
    assert "category" in error.value.message_dict


def test_an_archived_category_is_no_longer_offered(organization, actor):
    glace = services.create_category(organization=organization, actor=actor, name="Glace")
    draft = spend(organization, actor, glace, "5")
    glace = services.update_category(category=glace, actor=actor, is_active=False)

    with pytest.raises(ValidationError):
        spend(organization, actor, glace, "5")
    with pytest.raises(ValidationError):
        services.approve_expense(expense=draft, actor=actor)


def test_a_client_uuid_already_used_returns_the_same_expense(organization, actor, fuel):
    import uuid

    key = uuid.uuid4()
    first = spend(organization, actor, fuel, "5", client_uuid=key)
    assert spend(organization, actor, fuel, "6", client_uuid=key) == first


def test_totals_count_approved_and_waiting_expenses_but_not_refused_ones(organization, actor, fuel):
    spend(organization, actor, fuel, "10.500", approve=True)
    spend(organization, actor, fuel, "4.250")
    spend(organization, actor, fuel, "3", submit=True)
    services.reject_expense(expense=spend(organization, actor, fuel, "99"), actor=actor, reason="Erreur")

    totals = selectors.expense_totals(selectors.expenses_of(organization))
    assert (totals.count, totals.approved, totals.waiting) == (4, Decimal("10.500"), Decimal("7.250"))


# ---- costs of a lot ----


def test_a_lot_carries_the_expenses_typed_on_it_once_approved(organization, actor, fuel, cold_room):
    lot = receive(organization, "Dorade", "10", cold_room)
    transport = category(organization, "transport")
    approved = spend(organization, actor, transport, "25", batch=lot, description="Port → dépôt", approve=True)
    spend(organization, actor, fuel, "7", batch=lot)

    lines = selectors.lot_cost_lines(organization, batch_id=lot.pk)
    assert [(line.kind, line.expense_id, line.amount, line.description) for line in lines] == [
        ("lot", approved.pk, Decimal("25.000"), "Port → dépôt")
    ]
    preview = selectors.lot_cost_lines(organization, batch_id=lot.pk, approved_only=False)
    assert len(preview) == 2
    assert selectors.lot_cost_total(preview) == Decimal("25.000")


def test_truck_costs_of_the_day_are_split_over_the_lots_loaded_by_kg(organization, actor, cold_room, truck):
    dorade = receive(organization, "Dorade", "100", cold_room, number="L-0001")
    crevette = receive(organization, "Crevette", "100", cold_room, number="L-0002")
    loup = receive(organization, "Loup", "100", cold_room, number="L-0003")
    load(organization, actor, cold_room, truck, [(dorade, "10"), (crevette, "20")])
    # A second load the same day; the loup goes on another day.
    load(organization, actor, cold_room, truck, [(dorade, "5")])
    load(organization, actor, cold_room, truck, [(loup, "50")], day=days_ago(1))
    transport = category(organization, "transport")
    day_cost = spend(organization, actor, transport, "100.000", truck=truck, approve=True)

    shares = selectors.truck_day_shares(organization, expenses=[day_cost])[day_cost.pk]
    assert [(share.batch_number, share.quantity, share.day_quantity, share.amount) for share in shares] == [
        ("L-0001", Decimal("15.000"), Decimal("35.000"), Decimal("42.857")),
        ("L-0002", Decimal("20.000"), Decimal("35.000"), Decimal("57.143")),
    ]
    assert sum(share.amount for share in shares) == day_cost.amount
    dorade_lines = selectors.lot_cost_lines(organization, batch_id=dorade.pk)
    assert [(line.kind, line.amount, line.truck_name, line.quantity) for line in dorade_lines] == [
        ("truck_day", Decimal("42.857"), "Camion 2", Decimal("15.000"))
    ]
    assert selectors.lot_cost_lines(organization, batch_id=loup.pk) == []


def test_a_rounding_split_still_adds_up_to_the_expense(organization, actor, cold_room, truck):
    lots = [receive(organization, f"Produit {index}", "50", cold_room) for index in range(3)]
    load(organization, actor, cold_room, truck, [(lot, "7.333") for lot in lots])
    spend(organization, actor, category(organization, "handling"), "10.000", truck=truck, approve=True)

    total = sum(sum(line.amount for line in selectors.lot_cost_lines(organization, batch_id=lot.pk)) for lot in lots)
    assert total == Decimal("10.000")


def test_a_truck_day_without_load_and_unapproved_costs_charge_no_lot(organization, actor, cold_room, truck):
    lot = receive(organization, "Dorade", "100", cold_room)
    load(organization, actor, cold_room, truck, [(lot, "10")], day=days_ago(1))
    fuel = category(organization, "fuel")
    empty_day = spend(organization, actor, fuel, "50", truck=truck, approve=True)
    draft = spend(organization, actor, fuel, "20", truck=truck, spent_on=days_ago(1))

    assert selectors.truck_day_shares(organization, expenses=[empty_day]) == {}
    assert selectors.lot_cost_lines(organization, batch_id=lot.pk) == []
    preview = selectors.lot_cost_lines(organization, batch_id=lot.pk, approved_only=False)
    assert [(line.expense_id, line.status, line.amount) for line in preview] == [
        (draft.pk, ExpenseStatus.DRAFT, Decimal("20.000"))
    ]
