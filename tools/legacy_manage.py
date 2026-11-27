"""Run the pre-T-005 model configuration against the guarded test database only."""

import sys
from django.conf import settings
from django.core.management import execute_from_command_line
from filmoteka.test_postgresql.base import validate_target

validate_target()
settings.INSTALLED_APPS = [
    app
    for app in settings.INSTALLED_APPS
    if app not in {"accounts", "catalog", "collection"}
]
settings.AUTH_USER_MODEL = "auth.User"
settings.ROOT_URLCONF = "tests.legacy_urls"
execute_from_command_line(sys.argv)
