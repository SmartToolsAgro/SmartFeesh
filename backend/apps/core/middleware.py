from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.utils import translation

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
