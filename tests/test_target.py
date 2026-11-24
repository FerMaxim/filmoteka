import os
import subprocess
import sys


def test_reject_wrong_host_before_connection():
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "filmoteka.test_settings",
        "FILMOTEKA_TEST_RUN": "0123456789abcdef",
        "POSTGRES_HOST": "unreachable.invalid",
        "POSTGRES_DB": "test_0123456789abcdef",
        "POSTGRES_USER": "role_0123456789abcdef",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check"], env=env, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "Unexpected test database target" in result.stderr
