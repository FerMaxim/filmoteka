import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db.backends.postgresql.base import DatabaseWrapper as PostgreSQLWrapper

from filmoteka.test_postgresql.base import DatabaseWrapper

pytestmark = pytest.mark.quick


@pytest.fixture
def isolated_target(monkeypatch):
    marker = "0123456789abcdef"
    env = {
        "DJANGO_SETTINGS_MODULE": "filmoteka.test_settings",
        "FILMOTEKA_TEST_RUN": marker,
        "FILMOTEKA_TEST_PORT": "55432",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "55432",
        "POSTGRES_DB": f"test_{marker}",
        "POSTGRES_USER": f"role_{marker}",
        "POSTGRES_PASSWORD": "unused",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return {
        "host": env["POSTGRES_HOST"],
        "port": env["POSTGRES_PORT"],
        "dbname": env["POSTGRES_DB"],
        "user": env["POSTGRES_USER"],
    }


@pytest.mark.parametrize(
    "override", [{"POSTGRES_HOST": "unreachable.invalid"}, {"POSTGRES_PORT": "5432"}]
)
def test_reject_wrong_target_before_connection(isolated_target, override):
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        env={**os.environ, **override},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Unexpected test database target" in result.stderr


@pytest.mark.parametrize(
    "overrides", [{"dbname": "postgres"}, {"hostaddr": "127.0.0.1"}, {"port": "5432"}]
)
def test_reject_changed_connection_parameters(monkeypatch, isolated_target, overrides):
    connect = MagicMock()
    monkeypatch.setattr(PostgreSQLWrapper, "get_new_connection", connect)

    with pytest.raises(ImproperlyConfigured, match="connection parameters"):
        DatabaseWrapper({}).get_new_connection({**isolated_target, **overrides})

    connect.assert_not_called()


def test_reject_wrong_marker_before_returning_connection(monkeypatch, isolated_target):
    raw_connection = MagicMock()
    cursor = raw_connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (
        isolated_target["dbname"],
        isolated_target["user"],
        "wrong",
    )
    monkeypatch.setattr(
        PostgreSQLWrapper, "get_new_connection", MagicMock(return_value=raw_connection)
    )

    with pytest.raises(ImproperlyConfigured, match="Unexpected test database identity"):
        DatabaseWrapper({}).get_new_connection(isolated_target)

    cursor.execute.assert_called_once()
    raw_connection.close.assert_called_once()


@pytest.mark.parametrize("marker", ["", "0123456789abcdef"])
def test_browser_rejects_normal_settings_before_connection_or_write(tmp_path, marker):
    sentinel = tmp_path / "connected"
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "filmoteka.settings",
        "FILMOTEKA_TEST_RUN": marker,
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import psycopg,runpy,sys; from pathlib import Path; psycopg.connect=lambda *a,path=sys.argv[1],**k: Path(path).write_text('unexpected'); sys.argv=['tools.browser','http://127.0.0.1:1']; runpy.run_module('tools.browser',run_name='__main__')",
            str(sentinel),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "test" in result.stderr.lower()
    assert not sentinel.exists()
