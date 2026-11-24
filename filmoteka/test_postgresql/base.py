import os
import re

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.postgresql.base import DatabaseWrapper as PostgreSQLWrapper


def validate_target():
    marker = os.environ.get("FILMOTEKA_TEST_RUN", "")
    if not re.fullmatch(r"[0-9a-f]{16}", marker):
        raise ImproperlyConfigured("Invalid test run identifier")
    expected = {
        "DJANGO_SETTINGS_MODULE": "filmoteka.test_settings",
        "POSTGRES_HOST": "test-db",
        "POSTGRES_DB": f"test_{marker}",
        "POSTGRES_USER": f"role_{marker}",
    }
    forbidden = {"DATABASE_URL", "PGHOSTADDR", "PGSERVICE", "PGOPTIONS"}
    if forbidden.intersection(os.environ) or any(
        os.environ.get(key) != value for key, value in expected.items()
    ):
        raise ImproperlyConfigured("Unexpected test database target")
    return marker


class DatabaseWrapper(PostgreSQLWrapper):
    def get_new_connection(self, conn_params):
        marker = validate_target()
        target = {
            "host": "test-db",
            "port": "5432",
            "dbname": f"test_{marker}",
            "user": f"role_{marker}",
        }
        overrides = {"hostaddr", "service", "options"}
        if overrides.intersection(conn_params) or any(
            conn_params.get(key) != value for key, value in target.items()
        ):
            raise ImproperlyConfigured("Unexpected test database connection parameters")

        connection = super().get_new_connection(conn_params)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), current_user, "
                    "current_setting('filmoteka.run', true)"
                )
                identity = cursor.fetchone()
            connection.rollback()
            if identity != (target["dbname"], target["user"], marker):
                raise ImproperlyConfigured("Unexpected test database identity")
        except BaseException:
            connection.close()
            raise
        return connection
