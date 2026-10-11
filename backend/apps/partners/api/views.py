from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Membership, Organization
from apps.core.permissions import ReadOfficeWriteOwnerOrManager, membership_of
from apps.partners import selectors, services
from apps.partners.models import Customer, Supplier

from .serializers import (
    CustomerFilterSerializer,
    CustomerSerializer,
    CustomerWriteSerializer,
    SupplierFilterSerializer,
    SupplierSerializer,
    SupplierWriteSerializer,
)


# Base of the supplier views: every row is read inside the user's organization (D-022). Drivers get 403.
# A comment, not a docstring: a docstring would become the description of every endpoint in the schema.
class SupplierView(APIView):
    permission_classes = (ReadOfficeWriteOwnerOrManager,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization

    def supplier(self, supplier_id: int) -> Supplier:
        try:
            return selectors.supplier_of(self.organization, supplier_id)
        except Supplier.DoesNotExist:
            raise Http404 from None

    def supplier_answer(self, supplier_id: int, status_code: int = status.HTTP_200_OK) -> Response:
        # Read again so the answer carries the contacts as saved.
        return Response(SupplierSerializer(self.supplier(supplier_id)).data, status=status_code)


class SupplierListView(SupplierView):
    @extend_schema(
        operation_id="listSuppliers", parameters=[SupplierFilterSerializer], responses=SupplierSerializer(many=True)
    )
    def get(self, request: Request) -> Response:
        """Suppliers sorted by name, with their contacts. Archived ones only when asked (`status`). Not
        paginated: the company works with a handful of suppliers (D-032)."""
        filters = SupplierFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        suppliers = selectors.suppliers_of(
            self.organization, search=filters.validated_data["search"], status=filters.validated_data["status"]
        )
        return Response(SupplierSerializer(suppliers, many=True).data)

    @extend_schema(operation_id="createSupplier", request=SupplierWriteSerializer, responses={201: SupplierSerializer})
    def post(self, request: Request) -> Response:
        """A new supplier. Without a reference it gets the next free `F-NNN`."""
        serializer = SupplierWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supplier = services.create_supplier(
            organization=self.organization, actor=self.membership.user, **serializer.validated_data
        )
        return self.supplier_answer(supplier.pk, status.HTTP_201_CREATED)


class SupplierDetailView(SupplierView):
    @extend_schema(operation_id="getSupplier", responses=SupplierSerializer)
    def get(self, request: Request, supplier_id: int) -> Response:
        return self.supplier_answer(supplier_id)

    @extend_schema(operation_id="updateSupplier", request=SupplierWriteSerializer, responses=SupplierSerializer)
    def patch(self, request: Request, supplier_id: int) -> Response:
        """Change a supplier. `contacts`, when sent, replaces the whole list."""
        supplier = self.supplier(supplier_id)
        serializer = SupplierWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_supplier(supplier=supplier, actor=self.membership.user, **serializer.validated_data)
        return self.supplier_answer(supplier_id)


class SupplierArchiveView(SupplierView):
    @extend_schema(operation_id="archiveSupplier", request=None, responses=SupplierSerializer)
    def post(self, request: Request, supplier_id: int) -> Response:
        """Archived suppliers keep their history but can no longer be bought from."""
        services.set_supplier_active(supplier=self.supplier(supplier_id), actor=self.membership.user, is_active=False)
        return self.supplier_answer(supplier_id)


class SupplierRestoreView(SupplierView):
    @extend_schema(operation_id="restoreSupplier", request=None, responses=SupplierSerializer)
    def post(self, request: Request, supplier_id: int) -> Response:
        services.set_supplier_active(supplier=self.supplier(supplier_id), actor=self.membership.user, is_active=True)
        return self.supplier_answer(supplier_id)


# Base of the customer views: office data like suppliers (D-032, D-047); drivers get 403.
class CustomerView(APIView):
    permission_classes = (ReadOfficeWriteOwnerOrManager,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization

    def customer(self, customer_id: int) -> Customer:
        try:
            return selectors.customer_of(self.organization, customer_id)
        except Customer.DoesNotExist:
            raise Http404 from None

    def customer_answer(self, customer_id: int, status_code: int = status.HTTP_200_OK) -> Response:
        return Response(CustomerSerializer(self.customer(customer_id)).data, status=status_code)


class CustomerListView(CustomerView):
    @extend_schema(
        operation_id="listCustomers", parameters=[CustomerFilterSerializer], responses=CustomerSerializer(many=True)
    )
    def get(self, request: Request) -> Response:
        """Customers sorted by name, with their contacts. Archived ones only when asked (`status`); `kind`
        keeps one type. Not paginated (D-047)."""
        filters = CustomerFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        customers = selectors.customers_of(
            self.organization,
            search=filters.validated_data["search"],
            status=filters.validated_data["status"],
            kind=filters.validated_data.get("kind", ""),
        )
        return Response(CustomerSerializer(customers, many=True).data)

    @extend_schema(operation_id="createCustomer", request=CustomerWriteSerializer, responses={201: CustomerSerializer})
    def post(self, request: Request) -> Response:
        """A new customer. Without a reference it gets the next free `C-NNN`."""
        serializer = CustomerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = services.create_customer(
            organization=self.organization, actor=self.membership.user, **serializer.validated_data
        )
        return self.customer_answer(customer.pk, status.HTTP_201_CREATED)


class CustomerDetailView(CustomerView):
    @extend_schema(operation_id="getCustomer", responses=CustomerSerializer)
    def get(self, request: Request, customer_id: int) -> Response:
        return self.customer_answer(customer_id)

    @extend_schema(operation_id="updateCustomer", request=CustomerWriteSerializer, responses=CustomerSerializer)
    def patch(self, request: Request, customer_id: int) -> Response:
        """Change a customer. `contacts`, when sent, replaces the whole list."""
        customer = self.customer(customer_id)
        serializer = CustomerWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_customer(customer=customer, actor=self.membership.user, **serializer.validated_data)
        return self.customer_answer(customer_id)


class CustomerArchiveView(CustomerView):
    @extend_schema(operation_id="archiveCustomer", request=None, responses=CustomerSerializer)
    def post(self, request: Request, customer_id: int) -> Response:
        """Archived customers keep their history but can no longer be sold to. The walk-in one cannot be archived."""
        services.set_customer_active(customer=self.customer(customer_id), actor=self.membership.user, is_active=False)
        return self.customer_answer(customer_id)


class CustomerRestoreView(CustomerView):
    @extend_schema(operation_id="restoreCustomer", request=None, responses=CustomerSerializer)
    def post(self, request: Request, customer_id: int) -> Response:
        services.set_customer_active(customer=self.customer(customer_id), actor=self.membership.user, is_active=True)
        return self.customer_answer(customer_id)
