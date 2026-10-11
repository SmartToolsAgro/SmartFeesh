"""Settings shared by every environment. Environment-specific files import from here."""

from pathlib import Path

import django_stubs_ext
import environ

# Lets typed code write ModelAdmin[Model], DecimalField[...] and similar at runtime.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent

env = environ.Env()
# A .env file at the repository root is optional; real environments use real env vars.
environ.Env.read_env(REPO_ROOT / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
]
LOCAL_APPS = [
    "apps.core",
    "apps.catalog",
    "apps.partners",
    "apps.inventory",
    "apps.fleet",
    "apps.purchasing",
    "apps.sales",
    "apps.hr",
    "apps.expenses",
    "apps.demo",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.UserLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://frutti:frutti@localhost:5432/frutti"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False  # transactions are explicit, in services
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# French first; Arabic is planned (right-to-left), see docs/phases/00-foundations.md P0-T08.
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français"), ("ar", "العربية")]
TIME_ZONE = "Africa/Tunis"
USE_I18N = True
# Server messages are written in French; other languages get .po files here (needs GNU gettext).
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Business-rule errors raised by services become 400 answers (apps/core/api/exceptions.py).
    "EXCEPTION_HANDLER": "apps.core.api.exceptions.exception_handler",
    # Amounts travel as strings so no precision is lost (docs/ARCHITECTURE.md rule 1).
    "COERCE_DECIMAL_TO_STRING": True,
    # Login attempts, per address and per account (apps/core/authentication.py).
    "DEFAULT_THROTTLE_RATES": {"login_ip": "30/min", "login_username": "8/min"},
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Frutti Del Mare ERP API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # The schema is generated offline for the TS client (make gen-api); online it needs a login.
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    # Choice sets get stable names after their model, not their field: several models have a `kind`,
    # and "status" and "method" will exist on sales documents too.
    "ENUM_NAME_OVERRIDES": {
        "CustomerKindEnum": "apps.partners.models.CustomerKind",
        "SupplierInvoiceStatusEnum": "apps.purchasing.models.SupplierInvoiceStatus",
        "PaymentMethodEnum": "apps.purchasing.models.PaymentMethod",
        "StockLocationKindEnum": "apps.inventory.models.LocationKind",
        "TransferKindEnum": "apps.inventory.models.TransferKind",
        "TransferStatusEnum": "apps.inventory.models.TransferStatus",
        "LossStatusEnum": "apps.inventory.models.LossStatus",
        "LossReasonEnum": "apps.inventory.models.LossReason",
        "CountStatusEnum": "apps.inventory.models.CountStatus",
        "QuoteStatusEnum": "apps.sales.models.QuoteStatus",
        # P2-T04 · sales
        "SaleStatusEnum": "apps.sales.models.SaleStatus",
        "SalePaymentMethodEnum": "apps.sales.models.SalePaymentMethod",
        "SalePriceSourceEnum": "apps.sales.models.PriceSource",
        # P2-T05 · invoices
        "InvoiceStatusEnum": "apps.sales.models.InvoiceStatus",
        "EInvoiceStatusEnum": "apps.sales.models.EInvoiceStatus",
        "CreditNoteKindEnum": "apps.sales.models.CreditNoteKind",
        "SalaryStatusEnum": "apps.hr.models.SalaryStatus",
        "SalaryPaymentMethodEnum": "apps.hr.models.SalaryPaymentMethod",
        "ExpenseStatusEnum": "apps.expenses.models.ExpenseStatus",
        "LotCostKindEnum": "apps.expenses.models.LotCostKind",
        "WorkTypeEnum": "apps.expenses.models.WorkType",
    },
}
