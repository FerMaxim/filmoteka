import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql

from filmoteka.test_postgresql.base import LOOPBACK, validate_target, verify_identity


@contextmanager
def on_exit(cleanup):
    try:
        yield
    except BaseException:
        try:
            cleanup()
        except (Exception, SystemExit) as error:
            print(f"Cleanup failed: {error}", file=sys.stderr)
        raise
    else:
        cleanup()


@contextmanager
def temporary_workspace():
    root = Path(tempfile.gettempdir()).resolve()
    folder = Path(tempfile.mkdtemp(prefix="filmoteka-check-", dir=root))

    def remove_folder():
        resolved = folder.resolve()
        if resolved.parent != root or resolved != folder:
            raise RuntimeError(f"Unexpected test directory: {folder}")
        if (folder / "data" / "postmaster.pid").exists():
            raise RuntimeError(f"PostgreSQL may still be running. Kept {folder}")
        shutil.rmtree(folder)

    with on_exit(remove_folder):
        yield folder


@contextmanager
def postgres_cluster(folder, env, run):
    pg_bin = os.environ.get("PG_BIN")
    postgres = shutil.which("postgres", path=pg_bin)
    if postgres is None:
        raise SystemExit("PostgreSQL 17 binaries are required. Set PG_BIN or PATH.")
    bin_dir = Path(postgres).resolve().parent

    def executable(name):
        path = shutil.which(name, path=str(bin_dir))
        if path is None:
            raise SystemExit(f"PostgreSQL binary not found: {name}")
        return path

    version = subprocess.check_output([postgres, "--version"], text=True, env=env)
    if not re.search(r"\(PostgreSQL\) 17(?:\.|\s|$)", version):
        raise SystemExit(f"Expected PostgreSQL 17, found {version.strip()}")

    marker = secrets.token_hex(8)
    password = secrets.token_urlsafe(32)
    password_file = folder / "password"
    password_file.write_text(password, encoding="ascii")
    data = folder / "data"
    run(
        [
            executable("initdb"),
            "-D",
            str(data),
            "-U",
            f"role_{marker}",
            "--auth=scram-sha-256",
            f"--pwfile={password_file}",
            "--locale=C",
            "--encoding=UTF8",
        ],
        env,
    )
    password_file.unlink()
    with socket.socket() as listener:
        listener.bind((LOOPBACK, 0))
        port = str(listener.getsockname()[1])
    env = {
        **env,
        "DJANGO_SETTINGS_MODULE": "filmoteka.test_settings",
        "FILMOTEKA_TEST_RUN": marker,
        "FILMOTEKA_TEST_PORT": port,
        "POSTGRES_HOST": LOOPBACK,
        "POSTGRES_PORT": port,
        "POSTGRES_DB": f"test_{marker}",
        "POSTGRES_USER": f"role_{marker}",
        "POSTGRES_PASSWORD": password,
    }
    ctl = [executable("pg_ctl"), "-D", str(data), "-w", "-t", "30"]

    def stop():
        if (data / "postmaster.pid").exists():
            run([*ctl, "-m", "fast", "stop"], env)

    with on_exit(stop):
        # pg_ctl's server can inherit the output handle on Windows.
        # Use a file so that waiting for pg_ctl never waits for the server's output.
        with (folder / "pg_ctl.log").open(
            "w+", encoding="utf-8", errors="replace"
        ) as output:
            try:
                run(
                    [
                        *ctl,
                        "-l",
                        str(folder / "postgres.log"),
                        "-o",
                        f"-h {LOOPBACK} -p {port} -c unix_socket_directories= "
                        f"-c filmoteka.run={marker}",
                        "start",
                    ],
                    env,
                    output=output,
                )
            except SystemExit:
                output.seek(0)
                print(output.read(), file=sys.stderr)
                log = folder / "postgres.log"
                if log.exists():
                    print(
                        log.read_text(encoding="utf-8", errors="replace"),
                        file=sys.stderr,
                    )
                raise

        run([sys.executable, "-m", "tools.native"], env)
        yield env


@contextmanager
def django_server(folder, env, root):
    port_file = folder / "http-port"
    process = subprocess.Popen(
        [sys.executable, "-m", "tools.test_web", str(port_file)],
        cwd=root,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
    )

    def stop():
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

    with on_exit(stop):
        deadline = time.monotonic() + 30
        while not port_file.exists():
            if (code := process.poll()) is not None:
                raise SystemExit(code or "Django exited before binding a port")
            if time.monotonic() >= deadline:
                raise SystemExit("Django did not bind a port within 30 seconds")
            time.sleep(0.1)
        yield f"http://{LOOPBACK}:{int(port_file.read_text(encoding='ascii'))}"


def create_database():
    marker, target = validate_target()
    with (
        psycopg.connect(
            host=target["host"],
            port=target["port"],
            dbname="postgres",
            user=target["user"],
            password=os.environ["POSTGRES_PASSWORD"],
            autocommit=True,
            connect_timeout=3,
        ) as conn,
        conn.cursor() as cursor,
    ):
        verify_identity(cursor, "postgres", target["user"], marker)
        cursor.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target["dbname"]))
        )


if __name__ == "__main__":
    create_database()
