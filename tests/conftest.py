import pytest
from django.db import connection


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    # check.py migrates the database that Compose creates for this run.
    # Let Django isolate tests with transactions and let Compose remove the database.
    with django_db_blocker.unblock():
        connection.ensure_connection()
