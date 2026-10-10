from io import StringIO

from django.core.management import call_command


def test_openapi_schema_is_valid_and_has_no_warnings():
    # The TypeScript client is generated from this schema: a warning here is a wrong type there.
    call_command("spectacular", "--validate", "--fail-on-warn", stdout=StringIO())
