from typing import TYPE_CHECKING

from rest_framework import authentication
from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle

if TYPE_CHECKING:
    # Settings load this module while rest_framework.views is still importing.
    from rest_framework.views import APIView


class SessionAuthentication(authentication.SessionAuthentication):
    """Session cookie + CSRF (D-008), answering 401 instead of 403 when nobody is logged in.

    The front ends rely on the difference: 401 means "show the login screen", 403 means "not allowed".
    """

    def authenticate_header(self, request: Request) -> str:
        return "Session"


class LoginIPThrottle(SimpleRateThrottle):
    """Limits login attempts coming from one address, whatever the username."""

    scope = "login_ip"

    def get_cache_key(self, request: Request, view: "APIView") -> str | None:
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginUsernameThrottle(SimpleRateThrottle):
    """Limits attempts on one account, whatever address they come from."""

    scope = "login_username"

    def get_cache_key(self, request: Request, view: "APIView") -> str | None:
        username = request.data.get("username") if isinstance(request.data, dict) else None
        if not isinstance(username, str) or not username:
            return None
        return self.cache_format % {"scope": self.scope, "ident": username.strip().lower()}


class AdminLoginThrottle(LoginIPThrottle):
    """Limits password attempts on the Django admin's own login form, which has no throttle of its own (D-108)."""

    scope = "admin_login"
