from drf_spectacular.authentication import SessionScheme


class SessionAuthenticationScheme(SessionScheme):  # type: ignore[no-untyped-call]
    """Tells the OpenAPI generator that our session authentication is the standard cookie scheme."""

    target_class = "apps.core.authentication.SessionAuthentication"
