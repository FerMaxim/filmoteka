"""Temporary WSGI probe, distinct from application smoke; run as root."""

from contextlib import contextmanager
from pathlib import Path
import tempfile
import os
import subprocess
import time
import urllib.request
import ssl


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def database_probe():
    env = os.environ.copy()
    settings = dict(
        line.split("=", 1)
        for line in Path("/etc/filmoteka/app.env").read_text().splitlines()
    )
    env.update(
        PGHOST=settings["POSTGRES_HOST"],
        PGPORT=settings["POSTGRES_PORT"],
        PGDATABASE=settings["POSTGRES_DB"],
        PGUSER=settings["POSTGRES_USER"],
        PGPASSWORD=settings["POSTGRES_PASSWORD"],
    )
    query = "SELECT current_database()='filmoteka' AND current_user='filmoteka_app' AND pg_encoding_to_char(encoding)='UTF8' FROM pg_database WHERE datname=current_database();"
    result = run(
        "psql",
        "-XAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        query,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "t", "runtime identity/encoding mismatch"
    result = subprocess.run(
        [
            "psql",
            "-XAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "BEGIN; CREATE TABLE public.ops_ddl_forbidden(id integer); ROLLBACK;",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "permission denied" in result.stderr, (
        "runtime DDL not denied"
    )
    print("Runtime SCRAM connection, exact identity, UTF8 and DDL denial OK")


PROBE_SOURCE = """def application(environ, start_response):
    if environ['PATH_INFO'] != '/__ops_probe':
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'not an application health endpoint']
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [('infra-probe:' + environ['wsgi.url_scheme']).encode()]
"""


@contextmanager
def probe_service(base_dir=Path("/opt/filmoteka")):
    # An exclusive directory reserves this run's namespace, including its unit name.
    directory = Path(tempfile.mkdtemp(prefix="filmoteka-infra-probe-", dir=base_dir))
    directory.chmod(0o755)
    probe = directory / "infra_probe.py"
    unit = directory.name
    started = False
    try:
        with probe.open("x") as stream:
            stream.write(PROBE_SOURCE)
        probe.chmod(0o644)
        run(
            "systemd-run",
            "--unit=" + unit,
            "--collect",
            "--property=User=filmoteka",
            "--property=Group=filmoteka",
            "--property=WorkingDirectory=" + str(directory),
            "--property=NoNewPrivileges=yes",
            # Avoid generated __pycache__ files in the exclusively owned directory.
            "--property=Environment=PYTHONDONTWRITEBYTECODE=1",
            "/opt/filmoteka/probe-venv/bin/python",
            "-m",
            "gunicorn",
            "infra_probe:application",
            "--bind",
            "127.0.0.1:8000",
            "--workers",
            "1",
            "--threads",
            "2",
        )
        started = True
        yield
    finally:
        # A failed start may mean unit-name conflict: never stop that existing unit.
        # If stopping our unit fails, preserve its files for safe manual diagnosis.
        if started:
            run("systemctl", "stop", unit)
        probe.unlink(missing_ok=True)
        directory.rmdir()


def main():
    database_probe()
    with probe_service():
        ip = os.environ["SSH_CONNECTION"].split()[2]
        ctx = ssl.create_default_context(cafile="/etc/filmoteka/tls/server.crt")
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx)
        )
        for attempt in range(20):
            try:
                with opener.open(
                    "http://127.0.0.1:8080/__ops_probe", timeout=3
                ) as response:
                    assert response.read() == b"infra-probe:http"
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise RuntimeError("probe did not start")
        with opener.open("https://" + ip + "/__ops_probe", timeout=5) as response:
            assert response.read() == b"infra-probe:https", (
                "HTTPS scheme not conveyed to WSGI"
            )
        print("nginx -> Gunicorn HTTP/verified IP TLS and WSGI HTTPS scheme OK")
    print("Temporary probe stopped; application release remains absent")


if __name__ == "__main__":
    main()
