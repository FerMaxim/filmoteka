import os
import re

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.postgresql.base import DatabaseWrapper as PostgreSQLWrapper

LOOPBACK = "127.0.0.1"


def validate_target():
    marker = os.environ.get("FILMOTEKA_TEST_RUN", "")
    if not re.fullmatch(r"[0-9a-f]{16}", marker):
        raise ImproperlyConfigured("Invalid test run identifier")
    port = os.environ.get("FILMOTEKA_TEST_PORT", "")
    if not re.fullmatch(r"[1-9][0-9]{3,4}", port) or not 1024 <= int(port) <= 65535:
        raise ImproperlyConfigured("Invalid test database port")
    target = {
        "host": LOOPBACK,
        "port": port,
        "dbname": f"test_{marker}",
        "user": f"role_{marker}",
    }
    expected = {
        "DJANGO_SETTINGS_MODULE": "filmoteka.test_settings",
        "POSTGRES_HOST": target["host"],
        "POSTGRES_PORT": target["port"],
        "POSTGRES_DB": target["dbname"],
        "POSTGRES_USER": target["user"],
    }
    if (
        "DATABASE_URL" in os.environ
        or any(key.upper().startswith("PG") for key in os.environ if key != "PG_BIN")
        or any(os.environ.get(key) != value for key, value in expected.items())
    ):
        raise ImproperlyConfigured("Unexpected test database target")
    return marker, target


def verify_identity(cursor, database, user, marker):
    cursor.execute(
        "SELECT current_database(), current_user, current_setting('filmoteka.run', true)"
    )
    if cursor.fetchone() != (database, user, marker):
        raise ImproperlyConfigured("Unexpected test database identity")


class DatabaseWrapper(PostgreSQLWrapper):
    def get_new_connection(self, conn_params):
        marker, target = validate_target()
        overrides = {"hostaddr", "service", "options"}
        if overrides.intersection(conn_params) or any(
            conn_params.get(key) != value for key, value in target.items()
        ):
            raise ImproperlyConfigured("Unexpected test database connection parameters")

        connection = super().get_new_connection(conn_params)
        try:
            with connection.cursor() as cursor:
                verify_identity(cursor, target["dbname"], target["user"], marker)
            connection.rollback()
        except BaseException:
            connection.close()
            raise
        return connection
