from typing import TYPE_CHECKING, Any

from django.urls import reverse
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.money import MAX_AMOUNT, MAX_QUANTITY

from ..models import SiteSettings, WebRequest, WebRequestKind, WebRequestLine, WebRequestStatus
from ..selectors import SiteOffer

if TYPE_CHECKING:
    from apps.catalog.models import Product


# ---- The public site: what a visitor sees and sends (no login) ----


class SiteCategorySerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    name = serializers.CharField()


def _photo_url(product: "Product") -> str | None:
    if not product.photo.name:
        return None
    # The file name changes with every upload, so the address can be cached for good.
    version = product.photo.name.rsplit("/", 1)[-1].split(".", 1)[0]
    return f"{reverse('site-product-photo', args=[product.pk])}?v={version}"


class SiteProductSerializer(serializers.Serializer[Any]):
    """A product as the public site shows it: its web price only, no stock, no cost (D-186)."""

    id = serializers.IntegerField(source="product_id")
    name = serializers.CharField(source="product.name")
    name_ar = serializers.CharField(source="product.name_ar")
    category = serializers.IntegerField(source="product.category_id")
    category_name = serializers.CharField(source="product.category.name")
    unit = serializers.CharField(source="product.base_unit.symbol")
    # DT per kg, an indication confirmed on the phone; null: "prix sur demande".
    web_price = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True)
    description = serializers.CharField()
    # The prototype's drawing kind ("fish", "shrimp"...): the site picks its own picture from it.
    illustration = serializers.CharField(source="product.illustration")
    photo_url = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_photo_url(self, offer: SiteOffer) -> str | None:
        return _photo_url(offer.product)


class SiteContactSerializer(serializers.ModelSerializer[SiteSettings]):
    """How a visitor reaches the company; an empty field is not shown."""

    class Meta:
        model = SiteSettings
        fields = ("phone", "whatsapp", "email", "address", "opening_hours")
        read_only_fields = fields


class SiteCatalogSerializer(serializers.Serializer[Any]):
    company = serializers.CharField()
    # The logo uploaded in the office app's Paramètres (D-125); null when there is none.
    logo_url = serializers.CharField(allow_null=True)
    contact = SiteContactSerializer()
    categories = SiteCategorySerializer(many=True)
    products = SiteProductSerializer(many=True)


class SiteRequestLineSerializer(serializers.Serializer[Any]):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=0, max_value=MAX_QUANTITY)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class SiteRequestSerializer(serializers.Serializer[Any]):
    """A quote request or an order from the site. `phone` is required; `website` must stay empty (a field
    people never see, filled only by robots)."""

    kind = serializers.ChoiceField(choices=WebRequestKind.choices)
    full_name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=30)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    company = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    address = serializers.CharField(max_length=250, required=False, allow_blank=True, default="")
    wanted_on = serializers.DateField(required=False, allow_null=True, default=None)
    message = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    lines = SiteRequestLineSerializer(many=True, required=False, default=list)
    website = serializers.CharField(required=False, allow_blank=True, default="", write_only=True)

    def validate_website(self, value: str) -> str:
        if value:
            raise serializers.ValidationError("Demande refusée.")
        return value


class SiteRequestReceivedSerializer(serializers.Serializer[WebRequest]):
    number = serializers.CharField()
    kind = serializers.ChoiceField(choices=WebRequestKind.choices)


# ---- The office: reading and closing the requests ----


class WebRequestLineSerializer(serializers.ModelSerializer[WebRequestLine]):
    product = serializers.IntegerField(source="product_id")
    product_name = serializers.CharField(source="product.name")
    product_reference = serializers.CharField(source="product.reference")
    unit = serializers.CharField(source="product.base_unit.symbol")

    class Meta:
        model = WebRequestLine
        fields = ("id", "product", "product_name", "product_reference", "unit", "quantity", "web_price", "note")
        read_only_fields = fields


class WebRequestSerializer(serializers.ModelSerializer[WebRequest]):
    number = serializers.CharField()
    handled_by = serializers.SerializerMethodField()
    lines = WebRequestLineSerializer(many=True)

    class Meta:
        model = WebRequest
        fields = (
            "id",
            "number",
            "kind",
            "status",
            "full_name",
            "phone",
            "email",
            "company",
            "city",
            "address",
            "wanted_on",
            "message",
            "lines",
            "handled_by",
            "handled_at",
            "office_note",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_handled_by(self, request: WebRequest) -> str | None:
        user = request.handled_by
        return (user.get_full_name() or user.username) if user else None


class WebRequestFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=WebRequestStatus.choices, required=False)
    kind = serializers.ChoiceField(choices=WebRequestKind.choices, required=False)
    search = serializers.CharField(required=False, allow_blank=True, default="")


class WebRequestStatusSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=WebRequestStatus.choices)
    office_note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


# ---- The office: what the site shows (D-186) ----


class OfficeSiteProductSerializer(serializers.Serializer[Any]):
    """One active product of the application as the office sees it on the site screen: its photo, its day's price
    for comparison, and the site's settings (defaults when the office never changed them)."""

    product = serializers.IntegerField(source="product_id")
    product_name = serializers.CharField(source="product.name")
    product_reference = serializers.CharField(source="product.reference")
    category_name = serializers.CharField(source="product.category.name")
    unit = serializers.CharField(source="product.base_unit.symbol")
    illustration = serializers.CharField(source="product.illustration")
    photo_url = serializers.SerializerMethodField()
    day_price = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True)
    is_published = serializers.BooleanField()
    web_price = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True)
    description = serializers.CharField()
    position = serializers.IntegerField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_photo_url(self, offer: SiteOffer) -> str | None:
        # The office reads the photo through the catalogue (members only), shown on the site or not.
        product = offer.product
        if not product.photo.name:
            return None
        version = product.photo.name.rsplit("/", 1)[-1].split(".", 1)[0]
        return f"{reverse('product-photo', args=[product.pk])}?v={version}"


class SiteProductUpdateSerializer(serializers.Serializer[Any]):
    """Only the fields sent change; `web_price: null` means "prix sur demande"."""

    web_price = serializers.DecimalField(
        max_digits=14, decimal_places=3, required=False, allow_null=True, max_value=MAX_AMOUNT
    )
    description = serializers.CharField(max_length=300, required=False, allow_blank=True)
    is_published = serializers.BooleanField(required=False)
    position = serializers.IntegerField(min_value=0, required=False)


class SiteSettingsSerializer(serializers.ModelSerializer[SiteSettings]):
    """The site's contact details as the office edits them. Every field may be empty: it is then not shown."""

    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    whatsapp = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    address = serializers.CharField(max_length=250, required=False, allow_blank=True, default="")
    opening_hours = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    class Meta:
        model = SiteSettings
        fields = ("phone", "whatsapp", "email", "address", "opening_hours")
