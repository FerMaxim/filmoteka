import pytest
from django.contrib.sessions.models import Session
from django.db import connection


@pytest.mark.django_db
def test_ready_reads_migrated_postgresql(client):
    assert connection.vendor == "postgresql"
    assert Session.objects.count() == 0
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
