import logging

from celery import shared_task

from apps.core.models import Organization

from . import services

logger = logging.getLogger(__name__)


@shared_task(name="documents.generate_pdf")  # type: ignore[untyped-decorator]
def generate_pdf(organization_id: int, kind: str, object_id: int) -> None:
    """Make the PDF of one document and store it. A failure is kept on the document (the screen shows it)."""
    organization = Organization.objects.get(pk=organization_id)
    try:
        services.generate_pdf_now(organization=organization, kind=kind, object_id=object_id)
    except Exception as error:
        logger.exception("PDF %s #%s failed", kind, object_id)
        services.record_failure(organization=organization, kind=kind, object_id=object_id, error=repr(error))
