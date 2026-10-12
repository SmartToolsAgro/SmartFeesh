from typing import Any

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.documents import DOCUMENT_TYPE_CHOICES, PARTNER_SIDE_CHOICES, TONE_CHOICES


class DocumentFilterSerializer(serializers.Serializer[Any]):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)
    # Comma separated: "BL,FA". Empty: every type.
    types = serializers.CharField(required=False, default="", allow_blank=True, max_length=50)
    tone = serializers.ChoiceField(choices=TONE_CHOICES, required=False)

    def validate_types(self, value: str) -> frozenset[str]:
        known = {code for code, _label in DOCUMENT_TYPE_CHOICES}
        asked = {part.strip().upper() for part in value.split(",") if part.strip()}
        unknown = sorted(asked - known)
        if unknown:
            raise serializers.ValidationError(_("Type inconnu : %(types)s.") % {"types": ", ".join(unknown)})
        return frozenset(asked)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start, end = attrs.get("date_from"), attrs.get("date_to")
        if start and end and end < start:
            raise serializers.ValidationError({"date_to": _("La date de fin est avant la date de début.")})
        return attrs


class DocumentRowSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    type = serializers.ChoiceField(choices=DOCUMENT_TYPE_CHOICES)
    id = serializers.IntegerField()
    # Empty for a draft customer invoice: it gets its number when issued.
    number = serializers.CharField(allow_blank=True)
    partner_side = serializers.ChoiceField(choices=PARTNER_SIDE_CHOICES)
    partner_id = serializers.IntegerField()
    partner_name = serializers.CharField()
    date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=3)
    status = serializers.CharField()
    status_label = serializers.CharField()
    tone = serializers.ChoiceField(choices=TONE_CHOICES)
    parents = serializers.ListField(child=serializers.CharField())
    actions = serializers.ListField(child=serializers.CharField())
    pdf = serializers.CharField(allow_blank=True)


class DocumentListSerializer(serializers.Serializer[Any]):
    results = DocumentRowSerializer(many=True)
    total = serializers.IntegerField()
    truncated = serializers.BooleanField()
