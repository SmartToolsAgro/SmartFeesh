"""Reusable read queries of suppliers (and of customers, from Phase 2)."""

from typing import Literal

from django.db.models import Prefetch, Q, QuerySet

from apps.core.models import Organization

from .models import Supplier, SupplierContact

type SupplierStatus = Literal["active", "archived", "all"]


def suppliers_of(
    organization: Organization, *, search: str = "", status: SupplierStatus = "active"
) -> QuerySet[Supplier]:
    """Suppliers of one organization sorted by name, each with its contacts."""
    suppliers = (
        Supplier.objects.for_organization(organization)
        .prefetch_related(Prefetch("contacts", queryset=SupplierContact.objects.order_by("id")))
        .order_by("name", "id")
    )
    if status == "active":
        suppliers = suppliers.filter(is_active=True)
    elif status == "archived":
        suppliers = suppliers.filter(is_active=False)
    if search := search.strip():
        matching = Supplier.objects.filter(
            Q(name__icontains=search)
            | Q(reference__icontains=search)
            | Q(city__icontains=search)
            | Q(phone__icontains=search)
            | Q(tax_id__icontains=search)
            | Q(contacts__name__icontains=search)
        )
        # A subquery rather than a join: a supplier with two matching contacts is still listed once.
        suppliers = suppliers.filter(pk__in=matching.values("pk"))
    return suppliers


def supplier_of(organization: Organization, supplier_id: int) -> Supplier:
    """One supplier with its contacts. Raises Supplier.DoesNotExist outside the organization."""
    return suppliers_of(organization, status="all").get(pk=supplier_id)
