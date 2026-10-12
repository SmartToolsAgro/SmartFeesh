from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import translation

from .authentication import AdminLoginThrottle
from .models import User


class UserLanguageMiddleware:
    """Answers a logged-in user in the language saved on their account (fr or ar).

    Runs after LocaleMiddleware, which has already picked a language from the browser for visitors.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if isinstance(user, User):
            translation.activate(user.language)
            request.LANGUAGE_CODE = user.language
        response = self.get_response(request)
        if isinstance(user, User):
            response.headers["Content-Language"] = user.language
        return response


class RequestSizeLimitMiddleware:
    """Refuses an API request whose body is larger than `MAX_REQUEST_BYTES`, before reading it (D-108).

    Photos are checked at 8 MB once they are read (apps/core/images.py), but by then the whole upload has been
    written to the server's disk. This closes that door whatever the reverse proxy does.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if request.path.startswith("/api/") and length > settings.MAX_REQUEST_BYTES:
            return JsonResponse({"detail": "La requête est trop volumineuse."}, status=413)
        return self.get_response(request)


class AdminLoginThrottleMiddleware:
    """The Django admin login answers 429 after too many wrong passwords from one address (D-108).

    Superusers log in there, so it must not be an open door for guessing: the API login has its own limits
    (D-023) but this form is a separate page.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        guessing = request.method == "POST" and request.path.rstrip("/") == "/django-admin/login"
        if guessing and not AdminLoginThrottle().allow_request(request, None):  # type: ignore[arg-type]
            return HttpResponse("Trop de tentatives. Réessayez dans une minute.", status=429)
        return self.get_response(request)
