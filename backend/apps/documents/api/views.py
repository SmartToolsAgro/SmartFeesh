from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import ReadOfficeWriteOwnerOrManager, membership_of
from apps.documents import services

PdfState = inline_serializer("PdfState", {"status": serializers.ChoiceField(choices=["pending", "failed"])})


class DocumentPdfView(APIView):
    permission_classes: tuple[type[BasePermission], ...] = (ReadOfficeWriteOwnerOrManager,)

    @extend_schema(
        operation_id="getDocumentPdf",
        parameters=[OpenApiParameter("retry", bool, description="Try again after a failure.")],
        responses={(200, "application/pdf"): OpenApiTypes.BINARY, 202: PdfState, 500: PdfState},
    )
    def get(self, request: Request, kind: str, object_id: int) -> Response | FileResponse:
        """The PDF of a quote (`quote`), invoice (`invoice`), credit note (`credit_note`) or customer payment
        receipt (`receipt`). 200 is the file; 202 `pending` means it is being made (ask again in a second);
        500 `failed` means the last attempt failed (`?retry=1` tries again). Office data: drivers get 403."""
        membership = membership_of(request)
        assert membership is not None  # guaranteed by the permission class
        organization = membership.organization
        if not services.is_known(kind):
            raise Http404
        if not services.may_read(kind, membership.role):
            raise PermissionDenied
        retry = request.query_params.get("retry") in {"1", "true"}
        try:
            row = services.request_pdf(organization=organization, kind=kind, object_id=object_id, retry=retry)
            current = services.printable(organization, kind, object_id)
        except ObjectDoesNotExist:
            raise Http404 from None
        if row is None:
            row = services.current_file(organization=organization, kind=kind, object_id=object_id)
        if row is None:
            if services.failure_of(organization=organization, kind=kind, object_id=object_id):
                return Response({"status": "failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"status": "pending"}, status=status.HTTP_202_ACCEPTED)
        response = FileResponse(row.file.open("rb"), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{current.filename}"'
        response["Cache-Control"] = "private, no-store"
        return response
