from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


@extend_schema(
    responses=inline_serializer(
        "Health",
        fields={"status": serializers.CharField(), "database": serializers.CharField()},
    ),
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """Liveness + database check, used by Docker, the load balancer and uptime monitoring."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database = "ok"
    except Exception:  # noqa: BLE001 - any DB failure means "down"
        database = "unavailable"
    status_code = 200 if database == "ok" else 503
    return Response({"status": "ok" if status_code == 200 else "degraded", "database": database}, status=status_code)
