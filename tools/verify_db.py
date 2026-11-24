import os

import django

if os.environ.get("DJANGO_SETTINGS_MODULE") != "filmoteka.test_settings":
    raise SystemExit("Expected isolated test settings")
django.setup()
from django.db import connection  # noqa: E402

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT current_database(), current_user, current_setting('filmoteka.run')"
    )
    expected = (
        os.environ["POSTGRES_DB"],
        os.environ["POSTGRES_USER"],
        os.environ["FILMOTEKA_TEST_RUN"],
    )
    if cursor.fetchone() != expected:
        raise SystemExit("Unexpected database identity")
