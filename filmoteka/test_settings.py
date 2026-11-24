import os
import re

from django.core.exceptions import ImproperlyConfigured


def validate_target(env):
    marker = env.get("FILMOTEKA_TEST_RUN", "")
    if not re.fullmatch(r"[0-9a-f]{16}", marker):
        raise ImproperlyConfigured("Invalid test run identifier")
    expected = {
        "DJANGO_SETTINGS_MODULE": "filmoteka.test_settings",
        "POSTGRES_HOST": "test-db",
        "POSTGRES_DB": f"test_{marker}",
        "POSTGRES_USER": f"role_{marker}",
    }
    if "DATABASE_URL" in env or any(env.get(k) != v for k, v in expected.items()):
        raise ImproperlyConfigured("Unexpected test database target")


validate_target(os.environ)
from .settings import *  # noqa: E402,F403

DATABASES["default"]["TEST"] = {"NAME": os.environ["POSTGRES_DB"]}  # noqa: F405
