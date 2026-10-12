from .base import *  # noqa: F403
from .base import MIDDLEWARE, REST_FRAMEWORK, env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")  # required: fails loudly if missing
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
# Required: the login throttle must count across all server processes, not per process (D-108).
_ = env("DJANGO_CACHE_URL")

# HTTPS settings. Staging has no domain yet, so it runs on plain HTTP with these switched off in its
# .env (D-027). Production must keep the defaults.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = env.bool("DJANGO_SECURE_COOKIES", default=True)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Static files of the Django admin, served by the app itself (the front ends are served by nginx).
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Number of proxies in front of the app, so login throttling sees the visitor's address (D-023).
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": env.int("DJANGO_NUM_PROXIES", default=1)}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env("SENTRY_ENVIRONMENT", default="production"),
        send_default_pii=False,  # no customer or user data leaves the server
        traces_sample_rate=0.0,
    )
