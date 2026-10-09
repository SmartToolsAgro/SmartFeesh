import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_reports_ok_with_database(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_api_requires_login_by_default(client):
    # The schema endpoint uses the default permission (IsAuthenticated).
    response = client.get(reverse("schema"))

    assert response.status_code == 403
