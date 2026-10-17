"""Every write on returnable boxes goes through these functions, inside `transaction.atomic` (ARCHITECTURE §3)."""

import datetime as dt
import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Organization, User

from . import selectors
from .models import BoxHolder, BoxMovement, BoxPickup
from .models import BoxMovementKind as BoxMovementKind  # re-exported for apps that post box movements
from .models import BoxType as BoxType

if TYPE_CHECKING:
    from apps.inventory.models import StockLocation
    from apps.partners.models import Customer, Supplier

# Which holder kind each movement kind takes on each side. None means the side is empty.
_HOLDER_KINDS: dict[str, tuple[str | None, str | None]] = {
    BoxMovementKind.OPENING: (None, "location"),
    BoxMovementKind.RECEIVE: ("supplier", "location"),
    BoxMovementKind.LOAD: ("location", "location"),
    BoxMovementKind.LEAVE: ("location", "customer"),
    BoxMovementKind.COLLECT: ("customer", "location"),
    BoxMovementKind.RETURN: ("location", "supplier"),
    BoxMovementKind.TRUCK_RETURN: ("location", "location"),
    BoxMovementKind.WRITE_OFF: ("location", None),
    BoxMovementKind.PURCHASE: (None, "location"),
}


def _check_count(count: object) -> int:
    # Whole units only: a bool or a float is refused, never rounded.
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValidationError(_("Le nombre de caisses doit être un entier positif."))
    return count


def _signed_change(holder: BoxHolder, *, leaving: bool, count: int) -> int:
    """How one movement changes a holder's balance. Suppliers' balance is what we owe them, so it is inverted."""
    arriving_sign = -1 if holder.target_kind == "supplier" else 1
    return -count * arriving_sign if leaving else count * arriving_sign


@transaction.atomic
def holder_for(
    *,
    organization: Organization,
    location: "StockLocation | None" = None,
    customer: "Customer | None" = None,
    supplier: "Supplier | None" = None,
) -> BoxHolder:
    """The box holder of one location, client or supplier; created the first time it is needed."""
    targets = {"location": location, "customer": customer, "supplier": supplier}
    given = {name: obj for name, obj in targets.items() if obj is not None}
    if len(given) != 1:
        raise ValidationError(_("Une caisse se rattache à un seul emplacement, client ou fournisseur."))
    ((_name, target),) = given.items()
    if target.organization_id != organization.pk:
        raise ValidationError(_("Cet élément n'appartient pas à cette organisation."))
    # Every target is passed (None for the other two) so the lookup matches exactly one holder row.
    holder, _created = BoxHolder.objects.get_or_create(
        organization=organization, location=location, customer=customer, supplier=supplier
    )
    return holder


@transaction.atomic
def post_box_movement(
    *,
    organization: Organization,
    actor: User | None,
    kind: str,
    box_type: str,
    count: int,
    from_holder: BoxHolder | None = None,
    to_holder: BoxHolder | None = None,
    reason: str = "",
    source: models.Model | None = None,
    made_at: dt.datetime | None = None,
) -> BoxMovement:
    """Post one box movement. Refuses an unknown kind or box type, holders that do not fit the kind,
    holders of another organization, and any movement that would make a holder's balance negative."""
    if kind not in BoxMovementKind.values:
        raise ValidationError(_("Type de mouvement de caisses inconnu."))
    if box_type not in BoxType.values:
        raise ValidationError(_("Type de caisse inconnu."))
    count = _check_count(count)

    expected_from, expected_to = _HOLDER_KINDS[kind]
    _check_side(organization, from_holder, expected_from, side="départ")
    _check_side(organization, to_holder, expected_to, side="arrivée")
    if kind == BoxMovementKind.LOAD and from_holder is not None and from_holder.pk == to_holder.pk:  # type: ignore[union-attr]
        raise ValidationError(_("Un chargement va d'un emplacement vers un autre."))
    if kind == BoxMovementKind.LOAD and to_holder is not None and to_holder.location.kind != "truck":  # type: ignore[union-attr]
        raise ValidationError(_("Les caisses se chargent dans un camion."))
    # Only a truck gives its boxes back, and only to a cold room (P1-T14e, D-124).
    if (
        kind == BoxMovementKind.TRUCK_RETURN
        and from_holder is not None
        and to_holder is not None
        and (from_holder.location.kind != "truck" or to_holder.location.kind != "cold_room")  # type: ignore[union-attr]
    ):
        raise ValidationError(_("Les caisses reviennent d'un camion vers une chambre froide."))

    reason = reason.strip()
    if kind == BoxMovementKind.WRITE_OFF and not reason:
        raise ValidationError(_("Une casse ou une perte doit indiquer sa raison."))

    if source is not None and getattr(source, "organization_id", None) != organization.pk:
        raise ValidationError(_("Ce document n'appartient pas à cette organisation."))

    # Lock the holders in one order so two movements on the same holder run one after the other.
    holder_ids = sorted({h.pk for h in (from_holder, to_holder) if h is not None})
    locked = {h.pk: h for h in BoxHolder.objects.select_for_update().filter(pk__in=holder_ids).order_by("pk")}

    if from_holder is not None:
        _check_enough(locked[from_holder.pk], box_type, count, leaving=True)
    if to_holder is not None:
        _check_enough(locked[to_holder.pk], box_type, count, leaving=False)

    movement = BoxMovement.objects.create(
        organization=organization,
        box_type=box_type,
        kind=kind,
        count=count,
        from_holder=from_holder,
        to_holder=to_holder,
        reason=reason,
        source_type=ContentType.objects.get_for_model(source) if source is not None else None,
        source_id=source.pk if source is not None else None,
        created_by=actor,
        made_at=made_at,
    )
    audit.record(
        organization=organization,
        actor=actor,
        action="box.moved",
        target=movement,
        after={"kind": kind, "box_type": box_type, "count": count},
    )
    return movement


def _check_side(organization: Organization, holder: BoxHolder | None, expected: str | None, *, side: str) -> None:
    if expected is None:
        if holder is not None:
            raise ValidationError(_("Ce mouvement n'a pas de destinataire sur ce côté."))
        return
    if holder is None:
        raise ValidationError(_("Il manque le détenteur de caisses au %s.") % side)
    if holder.organization_id != organization.pk:
        raise ValidationError(_("Ce détenteur n'appartient pas à cette organisation."))
    if holder.target_kind != expected:
        raise ValidationError(_("Le détenteur au %(side)s doit être un %(kind)s.") % {"side": side, "kind": expected})


def _check_enough(holder: BoxHolder, box_type: str, count: int, *, leaving: bool) -> None:
    """Refuse a movement that would leave the holder below zero (same rule as kilos, D-006)."""
    after = selectors.signed_balance(holder, box_type) + _signed_change(holder, leaving=leaving, count=count)
    if after < 0:
        label = str(BoxType(box_type).label).lower()
        raise ValidationError(_("Pas assez de %(box)s chez ce détenteur.") % {"box": label})


def checked_box_counts(counts: Mapping[str, object] | None, errors: dict[str, str], *, prefix: str) -> dict[str, int]:
    """The non-zero counts of a document (receipt, transfer), or each problem on `<prefix>.<box type>`.

    Zero means no boxes of that type: it is dropped, so a document with no boxes posts nothing.
    """
    checked: dict[str, int] = {}
    for box_type, value in (counts or {}).items():
        key = f"{prefix}.{box_type}"
        if box_type not in BoxType.values:
            errors[key] = _("Type de caisse inconnu.")
        elif value is None:
            continue
        elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors[key] = _("Indiquez un nombre entier de caisses, zéro ou plus.")
        elif value > 0:
            checked[box_type] = value
    return checked


@transaction.atomic
def post_pickup(
    *,
    organization: Organization,
    actor: User | None,
    customer: "Customer",
    location: "StockLocation",
    counts: Mapping[str, int],
    client_uuid: uuid.UUID | None = None,
    made_at: dt.datetime | None = None,
) -> list[BoxMovement]:
    """Boxes a driver collects back from a client into the truck (`collect`, D-122). All or nothing: refused
    when the client holds fewer boxes of one type than asked (the ledger refuses a negative balance).
    A `client_uuid` already used returns the movements of that pickup instead (the driver app retries)."""
    if client_uuid is not None:
        existing = BoxPickup.objects.for_organization(organization).filter(client_uuid=client_uuid).first()
        if existing is not None:
            return list(
                BoxMovement.objects.for_organization(organization).filter(
                    source_type=ContentType.objects.get_for_model(BoxPickup), source_id=existing.pk
                )
            )
    pickup = BoxPickup.objects.create(
        organization=organization,
        customer=customer,
        location=location,
        client_uuid=client_uuid,
        created_by=actor,
    )
    return post_box_counts(
        organization=organization,
        actor=actor,
        kind=BoxMovementKind.COLLECT,
        counts=counts,
        from_holder=holder_for(organization=organization, customer=customer),
        to_holder=holder_for(organization=organization, location=location),
        source=pickup,
        made_at=made_at,
    )


@transaction.atomic
def post_box_counts(
    *,
    organization: Organization,
    actor: User | None,
    kind: str,
    counts: Mapping[str, int],
    from_holder: BoxHolder | None = None,
    to_holder: BoxHolder | None = None,
    source: models.Model | None = None,
    made_at: dt.datetime | None = None,
) -> list[BoxMovement]:
    """One movement per box type with a non-zero count, all or nothing (the caller's transaction)."""
    return [
        post_box_movement(
            organization=organization,
            actor=actor,
            kind=kind,
            box_type=box_type,
            count=count,
            from_holder=from_holder,
            to_holder=to_holder,
            source=source,
            made_at=made_at,
        )
        for box_type, count in counts.items()
        if count
    ]


@transaction.atomic
def adjust_boxes(
    *,
    organization: Organization,
    actor: User | None,
    location: "StockLocation",
    kind: str,
    box_type: str,
    count: int,
    reason: str = "",
) -> BoxMovement:
    """The office changes the boxes a cold room or a truck holds: boxes bought (they come in) or boxes lost or
    broken (they go out, with the reason). The cost of bought boxes is an expense entered on its own."""
    if kind not in (BoxMovementKind.PURCHASE, BoxMovementKind.WRITE_OFF):
        raise ValidationError({"kind": _("Indiquez un achat ou une casse ou perte.")})
    if location.organization_id != organization.pk or location.kind not in ("cold_room", "truck"):
        raise ValidationError({"location": _("Choisissez une chambre froide ou un camion.")})
    holder = holder_for(organization=organization, location=location)
    try:
        return post_box_movement(
            organization=organization,
            actor=actor,
            kind=kind,
            box_type=box_type,
            count=count,
            from_holder=holder if kind == BoxMovementKind.WRITE_OFF else None,
            to_holder=holder if kind == BoxMovementKind.PURCHASE else None,
            reason=reason,
        )
    except ValidationError as failure:
        field = "reason" if kind == BoxMovementKind.WRITE_OFF and not reason.strip() else "count"
        raise ValidationError({field: failure.messages}) from None
