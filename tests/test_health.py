from unittest.mock import patch

import pytest
from django.db import OperationalError

pytestmark = pytest.mark.quick


def test_live(client):
    assert client.get("/health/live").json() == {"status": "ok"}


def test_ready_failure(client):
    with patch("filmoteka.urls.connection.cursor", side_effect=OperationalError):
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
