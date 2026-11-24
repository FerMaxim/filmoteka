import argparse
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
if not __package__:
    sys.path.insert(0, str(ROOT))


def run(args, env=None, *, output=None):
    start = time.monotonic()
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT if output is not None else None,
        )
    except FileNotFoundError as error:
        message = f"Command unavailable: {Path(args[0]).name}"
        write_report(message)
        raise SystemExit(message) from error
    command = " ".join([Path(args[0]).name, *args[1:]])
    message = f"{command}: exit {result.returncode}, {time.monotonic() - start:.1f}s"
    print(message, flush=True)
    write_report(message)
    if result.returncode:
        raise SystemExit(result.returncode)


def write_report(message):
    if path := os.environ.get("FILMOTEKA_CHECK_REPORT"):
        try:
            with Path(path).open("a", encoding="utf-8") as report:
                report.write(f"{message}\n")
        except OSError as error:
            print(f"Could not write the check report: {error}", file=sys.stderr)


def check_code(env=None):
    for args in [
        ["-m", "ruff", "check", "."],
        ["-m", "ruff", "format", "--check", "."],
        ["manage.py", "check"],
        ["manage.py", "makemigrations", "--check", "--dry-run"],
    ]:
        run([PYTHON, *args], env)


def test_env():
    return {
        **{
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith(
                ("PG", "POSTGRES_", "DJANGO_", "FILMOTEKA_TEST_")
            )
            and key.upper() != "DATABASE_URL"
        },
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
        "DJANGO_ALLOWED_HOSTS": "testserver,127.0.0.1",
    }


def quick():
    env = {**test_env(), "DJANGO_SETTINGS_MODULE": "filmoteka.quick_settings"}
    check_code(env)
    run([PYTHON, "-m", "pytest", "-q", "-m", "quick"], env)


def stack(mode, node):
    from tools.native import django_server, postgres_cluster, temporary_workspace

    with (
        temporary_workspace() as folder,
        postgres_cluster(folder, test_env(), run) as env,
    ):
        if mode == "full":
            check_code(env)
        run([PYTHON, "manage.py", "migrate", "--noinput"], env)
        if mode == "target":
            run([PYTHON, "-m", "pytest", "-q", node], env)
            return
        if mode == "full":
            run([PYTHON, "-m", "pytest", "-q"], env)
        with django_server(folder, env, ROOT) as url:
            run([PYTHON, "-m", "tools.smoke", url], env)
            if mode in {"browser", "full"}:
                run([PYTHON, "-m", "tools.browser", url], env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=[
            "docs",
            "quick",
            "full",
            "browser",
            "smoke",
            "target",
        ],
    )
    parser.add_argument("node", nargs="?")
    args = parser.parse_args()
    if args.mode == "docs":
        run([PYTHON, "tools/docs.py"])
    elif args.mode == "quick":
        quick()
    elif args.mode == "target" and not args.node:
        parser.error("target requires a pytest node ID")
    else:
        stack(args.mode, args.node)
