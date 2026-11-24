import pytest
from django.db import connection


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    # check.py creates and migrates this run's database and owns its cleanup.
    with django_db_blocker.unblock():
        connection.ensure_connection()
