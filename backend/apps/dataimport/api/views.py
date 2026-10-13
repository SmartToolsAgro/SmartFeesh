from django.http import Http404, HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Membership, Organization
from apps.core.permissions import IsOwner, membership_of
from apps.dataimport import services
from apps.dataimport.columns import KINDS

from .serializers import ImportReportSerializer, ImportUploadSerializer

# Loading the company's data is the owner's job (D-112): nobody else, not even the manager, may import.
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# The biggest file accepted: 5 000 rows of text are well under it.
MAX_FILE_BYTES = 5 * 1024 * 1024


# A comment, not a docstring: a docstring would describe every endpoint in the schema.
class ImportView(APIView):
    permission_classes: tuple[type[BasePermission], ...] = (IsOwner,)

    @property
    def membership(self) -> Membership:
        membership = membership_of(self.request)
        assert membership is not None  # guaranteed by the permission class
        return membership

    @property
    def organization(self) -> Organization:
        return self.membership.organization


def _kind(kind: str) -> str:
    if kind not in KINDS:
        raise Http404
    return kind


class ImportTemplateView(ImportView):
    # A download link, not a call of the generated client: kept out of the API contract.
    @extend_schema(exclude=True)
    def get(self, request: Request, kind: str) -> HttpResponse:
        name, content = services.template_for(_kind(kind))
        response = HttpResponse(content, content_type=XLSX)
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response


class ImportRunView(ImportView):
    parser_classes = (MultiPartParser,)

    @extend_schema(
        operation_id="runImport",
        request={"multipart/form-data": ImportUploadSerializer},
        responses={200: ImportReportSerializer, 400: OpenApiResponse(description="Not a readable template")},
    )
    def post(self, request: Request, kind: str) -> Response:
        """Check a filled Excel template (`dry_run`, the default: nothing is written) or import it for real.
        The report lists every row: created, skipped (reference already known) or in error with its column.
        A real import is all or nothing: one error anywhere and nothing is saved (`committed` false). Owner only."""
        serializer = ImportUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        if upload.size > MAX_FILE_BYTES:
            return Response({"file": ["Fichier trop gros (5 Mo au plus)."]}, status=400)
        try:
            report = services.run_import(
                organization=self.organization,
                actor=self.membership.user,
                kind_key=_kind(kind),
                content=upload.read(),
                dry_run=serializer.validated_data["dry_run"],
            )
        except services.WorkbookError as error:
            return Response({"file": [str(error)]}, status=400)
        return Response(ImportReportSerializer(report).data)
