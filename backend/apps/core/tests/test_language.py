import pytest
from django.urls import path, reverse
from django.utils import translation
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from apps.core.models import Role

from .factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


class ActiveLanguageView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response({"language": translation.get_language()})


urlpatterns = [path("active-language", ActiveLanguageView.as_view())]


def client_for(**user_fields):
    membership = MembershipFactory.create(role=Role.DRIVER, user=UserFactory.create(**user_fields))
    client = APIClient()
    client.force_login(membership.user)
    return client, membership.user


def test_a_user_can_switch_the_apps_to_arabic_and_back():
    client, user = client_for()

    response = client.patch(reverse("me"), {"language": "ar"}, format="json")

    assert response.status_code == 200
    assert response.json()["user"]["language"] == "ar"
    user.refresh_from_db()
    assert user.language == "ar"
    assert client.get(reverse("me")).json()["user"]["language"] == "ar"

    assert client.patch(reverse("me"), {"language": "fr"}, format="json").json()["user"]["language"] == "fr"


def test_an_unknown_language_is_refused_and_nothing_else_can_be_changed():
    client, user = client_for(username="sami")

    assert client.patch(reverse("me"), {"language": "de"}, format="json").status_code == 400
    assert client.patch(reverse("me"), {"username": "hacker"}, format="json").status_code == 400
    user.refresh_from_db()
    assert (user.language, user.username) == ("fr", "sami")


def test_changing_the_language_requires_a_login():
    assert APIClient().patch(reverse("me"), {"language": "ar"}, format="json").status_code == 401


@pytest.mark.urls(__name__)
def test_the_server_answers_in_the_language_saved_on_the_account():
    arabic_client, _ = client_for(language="ar")
    french_client, _ = client_for(language="fr")

    arabic = arabic_client.get("/active-language", HTTP_ACCEPT_LANGUAGE="fr")
    french = french_client.get("/active-language", HTTP_ACCEPT_LANGUAGE="ar")

    assert (arabic.json()["language"], arabic.headers["Content-Language"]) == ("ar", "ar")
    assert (french.json()["language"], french.headers["Content-Language"]) == ("fr", "fr")


@pytest.mark.urls(__name__)
def test_a_visitor_gets_the_browser_language_or_french():
    assert APIClient().get("/active-language", HTTP_ACCEPT_LANGUAGE="ar").json() == {"language": "ar"}
    assert APIClient().get("/active-language", HTTP_ACCEPT_LANGUAGE="de").json() == {"language": "fr"}
