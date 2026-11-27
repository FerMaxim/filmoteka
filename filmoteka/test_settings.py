import os

from .test_postgresql.base import validate_target

validate_target()

from .settings import *  # noqa: E402,F403
from .settings import DATABASES  # noqa: E402

DATABASES = {
    "default": {
        **DATABASES["default"],
        "ENGINE": "filmoteka.test_postgresql",
        "TEST": {"NAME": DATABASES["default"]["NAME"]},
    }
}

# Guarded disposable database only; never contact the real provider in tests.
KINOPOISK_ENABLED = True
KINOPOISK_DATA_APPROVED = os.environ.get("FILMOTEKA_TEST_DATA_APPROVED", "1") == "1"
KINOPOISK_API_KEY = "synthetic-fixture-key"
KINOPOISK_REQUEST_BUDGET = 450
KINOPOISK_POSTERS_APPROVED = True
KINOPOISK_TEST_FIXTURES = True
