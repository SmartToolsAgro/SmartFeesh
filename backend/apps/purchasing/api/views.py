from typing import Any

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import QuerySet
from django.http import Http404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog import selectors as catalog
from apps.core.api.pagination import PagedList
from apps.core.models import Membership, Organization
from apps.core.permissions import ReadOfficeWriteOwnerOrManager, membership_of
from apps.inventory import selectors as inventory
from apps.partners import selectors as partners
from apps.purchasing import selectors, services
from apps.purchasing.models import GoodsReceipt, GoodsReceiptLine, SupplierInvoice, SupplierPayment

from .serializers import (
    DifferenceFilterSerializer,
    DifferenceLineSerializer,
    LastCostFilterSerializer,
    LastCostSerializer,
    PaymentAllocateSerializer,
    ReceiptFilterSerializer,
    ReceiptSerializer,
    ReceiptWriteSerializer,
    SupplierBalanceSerializer,
    SupplierInvoiceFilterSerializer,
    SupplierInvoiceSerializer,
    SupplierInvoiceUpdateSerializer,
    SupplierInvoiceWriteSerializer,
    SupplierPaymentFilterSerializer,
    SupplierPaymentSerializer,
    SupplierPaymentWriteSerializer,
)


# Purchases are office data (D-032): owner, manager and accountant read; owner and manager record; drivers 403.
# Rows of the user's organization only (D-022). A comment, not a docstring: it would describe every endpoint.
class PurchasingView(APIView):
    permission_classes = (ReadOfficeWriteOwnerOrManager,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization


def _resolved(organization: Organization, data: dict[str, Any]) -> dict[str, Any]:
    """The ids of a receipt replaced by the rows they name in the organization; unknown ids are field errors."""
    errors: dict[str, str] = {}
    supplier = location = None
    try:
        supplier = partners.supplier_of(organization, data["supplier"])
    except ObjectDoesNotExist:
        errors["supplier"] = _("Fournisseur inconnu.")
    try:
        location = inventory.location_of(organization, data["location"])
    except ObjectDoesNotExist:
        errors["location"] = _("Emplacement inconnu.")
    lines = []
    for index, line in enumerate(data["lines"]):
        try:
            product = catalog.product_of(organization, line["product"])
        except ObjectDoesNotExist:
            errors[services.line_error_key(index, "product")] = _("Produit inconnu.")
            continue
        lines.append({**line, "product": product})
    if errors:
        raise ValidationError(errors)
    return {**data, "supplier": supplier, "location": location, "lines": lines}


class ReceiptListView(PurchasingView, ListAPIView[GoodsReceipt]):
    serializer_class = ReceiptSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[GoodsReceipt]:
        filters = ReceiptFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.receipts_of(
            self.organization,
            supplier_id=filters.validated_data.get("supplier"),
            search=filters.validated_data["search"],
            with_differences=filters.validated_data["differences"],
            uninvoiced=filters.validated_data["uninvoiced"],
        )

    @extend_schema(operation_id="listReceipts", parameters=[ReceiptFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Goods receipts, newest first, paginated (`limit`, `offset`), each with its lines and totals.
        Filter by supplier, by `search` (number, supplier's reference, supplier name) or to receipts with
        a weight difference."""
        return super().get(request, *args, **kwargs)

    @extend_schema(operation_id="createReceipt", request=ReceiptWriteSerializer, responses={201: ReceiptSerializer})
    def post(self, request: Request) -> Response:
        """Record goods received from a supplier: one batch per line, its accepted net weight into stock.
        Errors of a line come back on `lines.<index>.<field>`."""
        serializer = ReceiptWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _resolved(self.organization, serializer.validated_data)
        receipt = services.create_receipt(organization=self.organization, actor=self.membership.user, **data)
        return Response(
            ReceiptSerializer(selectors.receipt_of(self.organization, receipt.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class ReceiptDetailView(PurchasingView):
    @extend_schema(operation_id="getReceipt", responses=ReceiptSerializer)
    def get(self, request: Request, receipt_id: int) -> Response:
        try:
            receipt = selectors.receipt_of(self.organization, receipt_id)
        except GoodsReceipt.DoesNotExist:
            raise Http404 from None
        return Response(ReceiptSerializer(receipt).data)


class ReceiptDifferenceListView(PurchasingView, ListAPIView[GoodsReceiptLine]):
    serializer_class = DifferenceLineSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[GoodsReceiptLine]:
        filters = DifferenceFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.difference_lines(
            self.organization,
            supplier_id=filters.validated_data.get("supplier"),
            date_from=filters.validated_data.get("date_from"),
            date_to=filters.validated_data.get("date_to"),
        )

    @extend_schema(operation_id="listReceiptDifferences", parameters=[DifferenceFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Weight differences report: receipt lines whose accepted weight is not the invoiced or ordered
        weight, newest first, paginated. Filter by supplier and by receipt dates (inclusive)."""
        return super().get(request, *args, **kwargs)


class LastCostListView(PurchasingView):
    @extend_schema(
        operation_id="listLastPurchaseCosts",
        parameters=[LastCostFilterSerializer],
        responses=LastCostSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        """What was last paid one supplier for each product (its latest batch). The receipt form suggests
        it and shows the change. The full history per product and supplier is `listBatches`."""
        filters = LastCostFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        batches = inventory.last_batches_from(self.organization, supplier_id=filters.validated_data["supplier"])
        return Response(LastCostSerializer(batches, many=True).data)


# ---- Supplier invoices and payments (P1-T08, D-043) ----


def _supplier(organization: Organization, supplier_id: int) -> Any:
    try:
        return partners.supplier_of(organization, supplier_id)
    except ObjectDoesNotExist:
        raise ValidationError({"supplier": _("Fournisseur inconnu.")}) from None


def _receipts(organization: Organization, receipt_ids: list[int]) -> list[GoodsReceipt]:
    """The receipts named by id in the organization; an unknown one is an error on `receipts`."""
    found = list(selectors.receipts_of(organization).filter(pk__in=receipt_ids))
    if len(found) != len(set(receipt_ids)):
        raise ValidationError({"receipts": _("Réception inconnue.")})
    return found


def _allocations(organization: Organization, lines: list[dict[str, Any]]) -> list[services.AllocationFields]:
    """The invoices named by id in the organization; an unknown one is an error on its own line."""
    errors: dict[str, str] = {}
    resolved: list[services.AllocationFields] = []
    for index, line in enumerate(lines):
        try:
            invoice = selectors.invoices_of(organization).get(pk=line["invoice"])
        except SupplierInvoice.DoesNotExist:
            errors[services.allocation_error_key(index, "invoice")] = _("Facture inconnue.")
            continue
        resolved.append({"invoice": invoice, "amount": line["amount"]})
    if errors:
        raise ValidationError(errors)
    return resolved


class SupplierInvoiceListView(PurchasingView, ListAPIView[SupplierInvoice]):
    serializer_class = SupplierInvoiceSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[SupplierInvoice]:
        filters = SupplierInvoiceFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.invoices_of(
            self.organization,
            supplier_id=filters.validated_data.get("supplier"),
            status=filters.validated_data.get("status"),
            search=filters.validated_data["search"],
            overdue=filters.validated_data["overdue"],
        )

    @extend_schema(operation_id="listSupplierInvoices", parameters=[SupplierInvoiceFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Supplier invoices, newest first, paginated, each with its receipts, payments, paid amount and what
        is still owed. Filter by supplier, status (`open` = posted and not fully paid), overdue, or `search`
        (our number, the supplier's invoice number, the supplier's name)."""
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="createSupplierInvoice",
        request=SupplierInvoiceWriteSerializer,
        responses={201: SupplierInvoiceSerializer},
    )
    def post(self, request: Request) -> Response:
        """Record a supplier invoice for some of their receipts, as a draft, or posted at once with `post`.
        Its amount is the receipts' invoiced amount (invoiced kg × cost); a receipt goes on one invoice only."""
        serializer = SupplierInvoiceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        supplier = _supplier(self.organization, data.pop("supplier"))
        receipts = _receipts(self.organization, data.pop("receipts"))
        invoice = services.create_invoice(
            organization=self.organization, actor=self.membership.user, supplier=supplier, receipts=receipts, **data
        )
        return Response(
            SupplierInvoiceSerializer(selectors.invoice_of(self.organization, invoice.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class InvoiceView(PurchasingView):
    def _invoice(self, invoice_id: int) -> SupplierInvoice:
        try:
            return selectors.invoice_of(self.organization, invoice_id)
        except SupplierInvoice.DoesNotExist:
            raise Http404 from None


class SupplierInvoiceDetailView(InvoiceView):
    @extend_schema(operation_id="getSupplierInvoice", responses=SupplierInvoiceSerializer)
    def get(self, request: Request, invoice_id: int) -> Response:
        return Response(SupplierInvoiceSerializer(self._invoice(invoice_id)).data)

    @extend_schema(
        operation_id="updateSupplierInvoice",
        request=SupplierInvoiceUpdateSerializer,
        responses=SupplierInvoiceSerializer,
    )
    def put(self, request: Request, invoice_id: int) -> Response:
        """Change a draft invoice: receipts, dates, reference, notes; `post` posts it afterwards. A posted
        invoice no longer changes (400). The supplier does not change."""
        invoice = self._invoice(invoice_id)
        serializer = SupplierInvoiceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        receipts = _receipts(self.organization, data.pop("receipts"))
        services.update_invoice(invoice=invoice, actor=self.membership.user, receipts=receipts, **data)
        return Response(SupplierInvoiceSerializer(self._invoice(invoice_id)).data)

    @extend_schema(operation_id="deleteSupplierInvoice", responses={204: None})
    def delete(self, request: Request, invoice_id: int) -> Response:
        """Delete a draft invoice; its receipts can go on another one. A posted invoice is never deleted (400)."""
        services.delete_invoice(invoice=self._invoice(invoice_id), actor=self.membership.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SupplierInvoicePostView(InvoiceView):
    @extend_schema(operation_id="postSupplierInvoice", request=None, responses=SupplierInvoiceSerializer)
    def post(self, request: Request, invoice_id: int) -> Response:
        """Post a draft invoice: it is owed to the supplier, counts in their balance and can be paid. Final."""
        services.post_invoice(invoice=self._invoice(invoice_id), actor=self.membership.user)
        return Response(SupplierInvoiceSerializer(self._invoice(invoice_id)).data)


class SupplierPaymentListView(PurchasingView, ListAPIView[SupplierPayment]):
    serializer_class = SupplierPaymentSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[SupplierPayment]:
        filters = SupplierPaymentFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.payments_of(
            self.organization,
            supplier_id=filters.validated_data.get("supplier"),
            search=filters.validated_data["search"],
            unallocated=filters.validated_data["unallocated"],
        )

    @extend_schema(operation_id="listSupplierPayments", parameters=[SupplierPaymentFilterSerializer])
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Payments to suppliers, newest first, paginated, with the invoices each one settled and the part
        not allocated yet. Filter by supplier, to payments with an unallocated part, or `search` (number,
        cheque or transfer reference, supplier's name)."""
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="recordSupplierPayment",
        request=SupplierPaymentWriteSerializer,
        responses={201: SupplierPaymentSerializer},
    )
    def post(self, request: Request) -> Response:
        """Record money paid to a supplier and the posted invoices it settles. What is not allocated is an
        advance, to allocate later. Errors of an allocation come back on `allocations.<index>.<field>`."""
        serializer = SupplierPaymentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        supplier = _supplier(self.organization, data.pop("supplier"))
        allocations = _allocations(self.organization, data.pop("allocations"))
        payment = services.record_payment(
            organization=self.organization,
            actor=self.membership.user,
            supplier=supplier,
            allocations=allocations,
            **data,
        )
        return Response(
            SupplierPaymentSerializer(selectors.payment_of(self.organization, payment.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentView(PurchasingView):
    def _payment(self, payment_id: int) -> SupplierPayment:
        try:
            return selectors.payment_of(self.organization, payment_id)
        except SupplierPayment.DoesNotExist:
            raise Http404 from None


class SupplierPaymentDetailView(PaymentView):
    @extend_schema(operation_id="getSupplierPayment", responses=SupplierPaymentSerializer)
    def get(self, request: Request, payment_id: int) -> Response:
        return Response(SupplierPaymentSerializer(self._payment(payment_id)).data)


class SupplierPaymentAllocateView(PaymentView):
    @extend_schema(
        operation_id="allocateSupplierPayment", request=PaymentAllocateSerializer, responses=SupplierPaymentSerializer
    )
    def post(self, request: Request, payment_id: int) -> Response:
        """Allocate the part of a payment not allocated yet (an advance) to posted invoices of its supplier."""
        payment = self._payment(payment_id)
        serializer = PaymentAllocateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allocations = _allocations(self.organization, serializer.validated_data["allocations"])
        services.allocate_payment(payment=payment, actor=self.membership.user, allocations=allocations)
        return Response(SupplierPaymentSerializer(self._payment(payment_id)).data)


class SupplierBalanceView(PurchasingView):
    @extend_schema(operation_id="getSupplierBalance", responses=SupplierBalanceSerializer)
    def get(self, request: Request, supplier_id: int) -> Response:
        """The trade balance with one supplier: posted invoices − payments, with what is overdue, advances not
        allocated, drafts and receipts not invoiced yet. A partner's capital and profit share are not in it."""
        try:
            supplier = partners.supplier_of(self.organization, supplier_id)
        except ObjectDoesNotExist:
            raise Http404 from None
        return Response(SupplierBalanceSerializer(selectors.supplier_balance(self.organization, supplier.pk)).data)
