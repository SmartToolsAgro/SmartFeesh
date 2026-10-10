"""Turns the business-rule errors raised by services into ordinary 400 answers."""

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Services raise Django's ValidationError (they know nothing of the API); answer it like a serializer.

    A message per field gives `{"field": ["message"]}`, a plain message gives `{"detail": "message"}`.
    """
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "error_dict"):
            exc = ValidationError(exc.message_dict)
        else:
            exc = ValidationError({"detail": " ".join(exc.messages)})
    return drf_exception_handler(exc, context)
