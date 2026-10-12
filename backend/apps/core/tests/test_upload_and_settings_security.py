"""Uploads, request size, login throttling and production settings (P4 go-live review, D-108)."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.core.models import Role

from .factories import MembershipFactory, OrganizationFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return OrganizationFactory.create()


@pytest.fixture
def owner(company):
    membership = MembershipFactory.create(role=Role.OWNER, organization=company, user=UserFactory.create())
    client = APIClient()
    client.force_authenticate(membership.user)
    return client


def _product(company) -> int:
    from apps.catalog import services

    category = services.create_category(organization=company, actor=None, name="Poissons")
    return services.create_product(
        organization=company,
        actor=None,
        reference="DOR",
        name="Dorade",
        category=category,
        sale_price="12.000",
    ).pk


def _png(size=(40, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "red").save(buffer, format="PNG")
    return buffer.getvalue()


def _put_photo(owner, product_id: int, name: str, content: bytes, content_type: str):
    return owner.put(
        f"/api/v1/products/{product_id}/photo",
        {"photo": SimpleUploadedFile(name, content, content_type=content_type)},
        format="multipart",
    )


def test_a_photo_must_really_be_a_small_jpeg_png_or_webp(owner, company):
    product = _product(company)
    bomb = io.BytesIO()
    Image.new("L", (8000, 8000)).save(bomb, format="PNG")  # a few KB on the wire, 64 million pixels
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    too_big = _png() + b"\0" * (9 * 1024 * 1024)
    refused = {
        "a script renamed .jpg": ("a.jpg", b"<script>alert(1)</script>", "image/jpeg"),
        "an SVG": ("a.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>1</script></svg>', "image/svg+xml"),
        "a GIF": ("a.gif", gif.getvalue(), "image/gif"),
        "a pixel bomb": ("a.png", bomb.getvalue(), "image/png"),
        "9 MB": ("a.png", too_big, "image/png"),
    }
    for label, (name, content, content_type) in refused.items():
        answer = _put_photo(owner, product, name, content, content_type)
        assert answer.status_code == 400, (label, answer.status_code)

    accepted = _put_photo(owner, product, "a.png", _png(), "image/png")
    assert accepted.status_code == 200


def test_an_upload_larger_than_the_limit_is_refused_before_it_is_read(owner, company):
    product = _product(company)
    answer = _put_photo(owner, product, "a.png", _png() + b"\0" * (11 * 1024 * 1024), "image/png")
    assert answer.status_code == 413


def _production_settings(monkeypatch, **env):
    import importlib
    import sys

    for name, value in {
        "DJANGO_SECRET_KEY": "k" * 60,
        "DJANGO_ALLOWED_HOSTS": "example.org",
        "DJANGO_CACHE_URL": "redis://redis:6379/1",
        **env,
    }.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    # Read again from scratch: the test settings already imported `base` with their own environment.
    base = sys.modules.get("config.settings.base")
    monkeypatch.delitem(sys.modules, "config.settings.prod", raising=False)
    monkeypatch.delitem(sys.modules, "config.settings.base", raising=False)
    try:
        return importlib.import_module("config.settings.prod")
    finally:
        sys.modules.pop("config.settings.prod", None)
        sys.modules.pop("config.settings.base", None)
        if base is not None:
            sys.modules["config.settings.base"] = base


def test_the_login_limits_count_in_a_cache_shared_by_all_server_processes(monkeypatch):
    """Three gunicorn workers each kept their own in-process counters: 8 attempts a minute became 24 (D-023)."""
    assert _production_settings(monkeypatch).CACHES["default"]["BACKEND"].endswith("RedisCache")


def test_production_refuses_to_start_without_the_shared_cache(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        _production_settings(monkeypatch, DJANGO_CACHE_URL=None)


def test_production_is_https_only_with_protected_cookies(monkeypatch):
    """Staging switches these off in its own .env (D-027); a production that forgets to must be safe."""
    for name in ("DJANGO_SECURE_SSL_REDIRECT", "DJANGO_SECURE_COOKIES", "DJANGO_SECURE_HSTS_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    prod = _production_settings(monkeypatch)
    assert prod.DEBUG is False
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_HSTS_SECONDS >= 60 * 60 * 24 * 30
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.SESSION_COOKIE_HTTPONLY is True
    assert prod.SESSION_COOKIE_SAMESITE in {"Lax", "Strict"}
    assert prod.CACHES["default"]["BACKEND"].endswith("RedisCache")


def test_a_logged_in_session_still_needs_the_csrf_token_to_write():
    """A page on another site must not be able to make the owner's browser change data."""
    membership = MembershipFactory.create(
        role=Role.OWNER, organization=OrganizationFactory.create(), user=UserFactory.create(username="boss")
    )
    del membership
    strict = APIClient(enforce_csrf_checks=True)
    strict.get("/api/v1/auth/csrf")
    token = strict.cookies["csrftoken"].value
    login = strict.post(
        "/api/v1/auth/login", {"username": "boss", "password": "test-password"}, format="json", HTTP_X_CSRFTOKEN=token
    )
    assert login.status_code == 200
    token = strict.cookies["csrftoken"].value
    assert strict.post("/api/v1/categories", {"name": "Sans jeton"}, format="json").status_code == 403
    assert (
        strict.post("/api/v1/categories", {"name": "Avec jeton"}, format="json", HTTP_X_CSRFTOKEN=token).status_code
        == 201
    )


def test_the_django_admin_login_is_throttled_like_the_api_login(client):
    """/django-admin/login/ takes superuser passwords and had no limit at all: it could be guessed at will."""
    from django.core.cache import cache

    cache.clear()
    answers = [
        client.post("/django-admin/login/", {"username": "root", "password": f"guess-{n}"}).status_code
        for n in range(12)
    ]
    assert answers[:8] == [200] * 8
    assert set(answers[8:]) == {429}
    cache.clear()
