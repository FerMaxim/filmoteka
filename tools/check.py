import argparse
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(args, env=None):
    start = time.monotonic()
    try:
        result = subprocess.run(args, cwd=ROOT, env=env)
    except FileNotFoundError as error:
        raise SystemExit(f"Command unavailable: {args[0]}") from error
    print(
        f"{args[0]} {args[-1]}: exit {result.returncode}, {time.monotonic() - start:.1f}s",
        flush=True,
    )
    if result.returncode:
        raise SystemExit(result.returncode)


def check_code(env=None):
    for args in [
        ["-m", "ruff", "check", "."],
        ["-m", "ruff", "format", "--check", "."],
        ["manage.py", "check"],
        ["manage.py", "makemigrations", "--check", "--dry-run"],
    ]:
        run([PYTHON, *args], env)


def quick():
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "filmoteka.quick_settings",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
        "DJANGO_ALLOWED_HOSTS": "testserver,localhost",
    }
    check_code(env)
    run([PYTHON, "-m", "pytest", "-q", "-m", "quick"], env)


def stack(mode, node):
    marker = secrets.token_hex(8)
    env = {
        **os.environ,
        "TEST_RUN": marker,
        "TEST_PASSWORD": secrets.token_urlsafe(32),
        "TEST_SECRET": secrets.token_urlsafe(48),
    }
    compose = [
        "docker",
        "compose",
        "-p",
        f"filmoteka-{marker}",
        "-f",
        "compose.test.yaml",
    ]

    def command(*args):
        run([*compose, *args], env)

    def check(*args):
        command("run", "--rm", "--no-deps", "checks", "python", *args)

    primary_failed = False
    try:
        command("build", "checks", "web")
        command("up", "-d", "--wait", "--wait-timeout", "90", "test-db")
        if mode == "full":
            check("tools/check.py", "code-in-container")
        check("manage.py", "migrate", "--noinput")
        if mode == "target":
            check("-m", "pytest", "-q", node)
            return
        if mode == "full":
            check("-m", "pytest", "-q")
        command("up", "-d", "web")
        check("-m", "tools.smoke")
        if mode in {"browser", "full"}:
            check("-m", "tools.browser")
    except BaseException:
        primary_failed = True
        raise
    finally:
        try:
            command("down", "-v", "--remove-orphans")
        except (OSError, SystemExit) as cleanup_error:
            if not primary_failed:
                raise
            print(f"Compose cleanup failed: {cleanup_error}", file=sys.stderr)


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
            "code-in-container",
        ],
    )
    parser.add_argument("node", nargs="?")
    args = parser.parse_args()
    if "DATABASE_URL" in os.environ and args.mode != "docs":
        parser.error("Unset DATABASE_URL before running checks")
    if args.mode == "docs":
        run([PYTHON, "tools/docs.py"])
    elif args.mode == "quick":
        quick()
    elif args.mode == "code-in-container":
        if os.environ.get("DJANGO_SETTINGS_MODULE") != "filmoteka.test_settings":
            parser.error("code-in-container requires isolated test settings")
        check_code()
    elif args.mode == "target" and not args.node:
        parser.error("target requires a pytest node ID")
    else:
        stack(args.mode, args.node)
