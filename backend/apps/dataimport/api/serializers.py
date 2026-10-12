from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.dataimport.columns import KINDS


@extend_schema_field(OpenApiTypes.BINARY)
class UploadedFileField(serializers.FileField):
    """A file sent in a multipart form: a Blob in the generated client, not a URL."""


class ImportUploadSerializer(serializers.Serializer[Any]):
    # The filled Excel template (.xlsx).
    file = UploadedFileField()
    # True (the default): only check the file and report; nothing is written. False: import for real.
    dry_run = serializers.BooleanField(required=False, default=True)


class ImportColumnErrorSerializer(serializers.Serializer[Any]):
    column = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)


class ImportRowSerializer(serializers.Serializer[Any]):
    # The row number in the Excel sheet (the first data row is 2).
    row = serializers.IntegerField(read_only=True)
    status = serializers.ChoiceField(choices=["created", "skipped", "error"], read_only=True)
    reference = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    errors = ImportColumnErrorSerializer(many=True, read_only=True)  # type: ignore[assignment]


class ImportReportSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=list(KINDS), read_only=True)
    dry_run = serializers.BooleanField(read_only=True)
    # True when the rows were really saved (a real import without any error).
    committed = serializers.BooleanField(read_only=True)
    created = serializers.IntegerField(read_only=True)
    skipped = serializers.IntegerField(read_only=True)
    error_count = serializers.IntegerField(read_only=True)
    rows = ImportRowSerializer(many=True, read_only=True)
