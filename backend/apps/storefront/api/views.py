from typing import Any

from django.db.models import QuerySet
from django.http import FileResponse, Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.core.api.pagination import PagedList
from apps.core.models import Membership, Organization
from apps.core.permissions import ReadOfficeWriteOwnerOrManager, membership_of

from .. import selectors, services
from ..models import SiteProduct, WebRequest
from .serializers import (
    OfficeSiteProductSerializer,
    SiteCatalogSerializer,
    SiteProductCreateSerializer,
    SiteProductUpdateSerializer,
    SiteRequestReceivedSerializer,
    SiteRequestSerializer,
    WebRequestFilterSerializer,
    WebRequestSerializer,
    WebRequestStatusSerializer,
)


class SiteCatalogThrottle(AnonRateThrottle):
    scope = "site_catalog"


class SiteRequestThrottle(AnonRateThrottle):
    """A visitor sends a few requests an hour at most; more is a robot filling the office's list."""

    scope = "site_request"


# The public site (D-184): nobody is logged in, so no session and no CSRF; a few calls per address only.
# A comment, not a docstring: a docstring would describe every endpoint in the schema.
class SiteView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def site_organization(self) -> Organization:
        organization = selectors.site_organization()
        if organization is None:
            raise Http404
        return organization


class SiteCatalogView(SiteView):
    throttle_classes = (SiteCatalogThrottle,)

    @extend_schema(operation_id="getSiteCatalog", responses=SiteCatalogSerializer)
    def get(self, request: Request) -> Response:
        """What the public site offers: the company's name, its categories and the products the office put on the
        site, with their web price (or none: "prix sur demande")."""
        organization = self.site_organization()
        answer = {
            "company": organization.name,
            "categories": selectors.site_categories(organization),
            "products": selectors.site_products(organization),
        }
        return Response(SiteCatalogSerializer(answer).data)


class SiteProductPhotoView(SiteView):
    throttle_classes = (SiteCatalogThrottle,)

    # Read by an <img> tag, not by the generated client: kept out of the API contract.
    @extend_schema(exclude=True)
    def get(self, request: Request, product_id: int) -> FileResponse:
        shown = selectors.site_products(self.site_organization()).filter(product_id=product_id).first()
        if shown is None or not shown.product.photo:
            raise Http404
        response = FileResponse(shown.product.photo.open("rb"), content_type="image/webp")
        # The address changes with every new photo (see SiteProductSerializer.photo_url).
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


class SiteRequestView(SiteView):
    throttle_classes = (SiteRequestThrottle,)

    @extend_schema(
        operation_id="sendSiteRequest",
        request=SiteRequestSerializer,
        responses={
            201: SiteRequestReceivedSerializer,
            400: OpenApiResponse(description="A field is missing or wrong, e.g. the phone number"),
            429: OpenApiResponse(description="Too many requests from this address"),
        },
    )
    def post(self, request: Request) -> Response:
        """A visitor asks for a quote or orders products. The phone number is required: the office calls back
        to confirm prices and delivery."""
        serializer = SiteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("website")
        lines = [
            services.RequestedLine(product_id=line["product"], quantity=line["quantity"], note=line["note"])
            for line in data.pop("lines")
        ]
        web_request = services.submit_web_request(organization=self.site_organization(), lines=lines, **data)
        return Response(SiteRequestReceivedSerializer(web_request).data, status=status.HTTP_201_CREATED)


# ---- The office (owners and managers handle them; the accountant reads) ----


class OfficeView(APIView):
    permission_classes = (ReadOfficeWriteOwnerOrManager,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization

    def web_request(self, request_id: int) -> WebRequest:
        try:
            return selectors.web_request_of(self.organization, request_id)
        except WebRequest.DoesNotExist:
            raise Http404 from None


class WebRequestListView(OfficeView, ListAPIView[WebRequest]):
    serializer_class = WebRequestSerializer
    pagination_class = PagedList

    def get_queryset(self) -> QuerySet[WebRequest]:
        filters = WebRequestFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.web_requests_of(
            self.organization,
            status=filters.validated_data.get("status"),
            kind=filters.validated_data.get("kind"),
            search=filters.validated_data["search"],
        )

    @extend_schema(operation_id="listWebRequests", parameters=[WebRequestFilterSerializer])
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Quote requests and orders sent from the public site, newest first, paginated (`limit`, `offset`).
        Filter by status, kind or `search` (name, phone, company, number)."""
        return super().get(request, *args, **kwargs)


class WebRequestDetailView(OfficeView):
    @extend_schema(operation_id="getWebRequest", responses=WebRequestSerializer)
    def get(self, request: Request, request_id: int) -> Response:
        return Response(WebRequestSerializer(self.web_request(request_id)).data)


class WebRequestStatusView(OfficeView):
    @extend_schema(
        operation_id="setWebRequestStatus", request=WebRequestStatusSerializer, responses=WebRequestSerializer
    )
    def post(self, request: Request, request_id: int) -> Response:
        """The office called the visitor back: mark the request handled or cancelled with a note, or new again."""
        serializer = WebRequestStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_web_request_status(
            request=self.web_request(request_id),
            actor=self.membership.user,
            status=serializer.validated_data["status"],
            note=serializer.validated_data["office_note"],
        )
        return Response(WebRequestSerializer(self.web_request(request_id)).data)


# ---- The office: what the site shows (D-184) ----


class SiteProductListView(OfficeView):
    @extend_schema(operation_id="listSiteProducts", responses=OfficeSiteProductSerializer(many=True))
    def get(self, request: Request) -> Response:
        """Every product put on the public site, shown or hidden, in the site's order."""
        rows = selectors.site_products_of(self.organization)
        return Response(OfficeSiteProductSerializer(rows, many=True).data)

    @extend_schema(
        operation_id="addSiteProduct",
        request=SiteProductCreateSerializer,
        responses={201: OfficeSiteProductSerializer},
    )
    def post(self, request: Request) -> Response:
        """Put an active product on the site, with its own web price. The day's price and price lists do not
        change."""
        serializer = SiteProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        site_product = services.add_site_product(
            organization=self.organization,
            actor=self.membership.user,
            product_id=data["product"],
            web_price=data["web_price"],
            description=data["description"],
            is_published=data["is_published"],
            position=data["position"],
        )
        answer = selectors.site_product_of(self.organization, site_product.pk)
        return Response(OfficeSiteProductSerializer(answer).data, status=status.HTTP_201_CREATED)


class SiteProductDetailView(OfficeView):
    def site_product(self, site_product_id: int) -> SiteProduct:
        try:
            return selectors.site_product_of(self.organization, site_product_id)
        except SiteProduct.DoesNotExist:
            raise Http404 from None

    @extend_schema(
        operation_id="updateSiteProduct", request=SiteProductUpdateSerializer, responses=OfficeSiteProductSerializer
    )
    def patch(self, request: Request, site_product_id: int) -> Response:
        """Change the web price (null: "prix sur demande"), the text, the order, or hide the product."""
        serializer = SiteProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_site_product(
            site_product=self.site_product(site_product_id),
            actor=self.membership.user,
            changes=serializer.validated_data,
        )
        return Response(OfficeSiteProductSerializer(self.site_product(site_product_id)).data)

    @extend_schema(operation_id="removeSiteProduct", responses={204: None})
    def delete(self, request: Request, site_product_id: int) -> Response:
        """Take the product off the site. The product, its prices and the requests already received stay."""
        services.remove_site_product(site_product=self.site_product(site_product_id), actor=self.membership.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
