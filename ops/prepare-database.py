"""Run once as root on the inventoried server; never prints credentials."""

import grp
import os
from pathlib import Path
import secrets
import subprocess


def sql(statement, database="postgres"):
    result = subprocess.run(
        [
            "runuser",
            "-u",
            "postgres",
            "--",
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            database,
        ],
        input=statement,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise SystemExit(
            "Database provisioning failed; inspect locally without disclosing SQL or secrets"
        )
    return result.stdout.strip()


if os.geteuid() != 0:
    raise SystemExit("root required")
if Path("/etc/filmoteka/app.env").exists():
    raise SystemExit(
        "Existing configuration preserved; use a reviewed update procedure"
    )
if (
    sql(
        "SELECT count(*) FROM pg_roles WHERE rolname IN ('filmoteka_app','filmoteka_migrate')"
    )
    != "0"
):
    raise SystemExit("Existing roles preserved; investigate before provisioning")
if sql("SELECT count(*) FROM pg_database WHERE datname='filmoteka'") != "0":
    raise SystemExit("Existing database preserved")

app_password = secrets.token_urlsafe(48)
migration_password = secrets.token_urlsafe(48)
sql(
    f"CREATE ROLE filmoteka_migrate LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD '{migration_password}';"
    f"CREATE ROLE filmoteka_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD '{app_password}';"
)
sql(
    "CREATE DATABASE filmoteka OWNER filmoteka_migrate TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8';"
)
sql(
    "REVOKE ALL ON DATABASE filmoteka FROM PUBLIC; GRANT CONNECT ON DATABASE filmoteka TO filmoteka_app;"
)
sql(
    "REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO filmoteka_app;"
    "ALTER DEFAULT PRIVILEGES FOR ROLE filmoteka_migrate IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO filmoteka_app;"
    "ALTER DEFAULT PRIVILEGES FOR ROLE filmoteka_migrate IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO filmoteka_app;",
    "filmoteka",
)


def save(path, value, group, mode):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)
    os.chown(path, 0, grp.getgrnam(group).gr_gid)


common = "POSTGRES_HOST=127.0.0.1\nPOSTGRES_PORT=5432\nPOSTGRES_DB=filmoteka\n"
save(
    "/etc/filmoteka/app.env",
    common + "POSTGRES_USER=filmoteka_app\n"
    f"POSTGRES_PASSWORD={app_password}\nDJANGO_SECRET_KEY={secrets.token_urlsafe(64)}\n"
    "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\n",
    "filmoteka",
    0o640,
)
save(
    "/etc/filmoteka/migrate.env",
    common + "POSTGRES_USER=filmoteka_migrate\n"
    f"POSTGRES_PASSWORD={migration_password}\n",
    "root",
    0o600,
)
print(
    "Created isolated database, migration/runtime roles and protected configuration; no release deployed"
)
