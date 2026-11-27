import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
report_stream = None
report_checks = 0
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
        write_report("check", code=1, message=message)
        raise SystemExit(message) from error
    command = " ".join([Path(args[0]).name, *args[1:]])
    message = f"{command}: exit {result.returncode}, {time.monotonic() - start:.1f}s"
    print(message, flush=True)
    write_report("check", code=result.returncode, message=message)
    if result.returncode:
        raise SystemExit(result.returncode)


def git_snapshot(root):
    def git(*args):
        return subprocess.check_output(
            ["git", "--no-optional-locks", "-C", str(root), *args], timeout=15
        )

    sha = git("rev-parse", "HEAD").decode("ascii").strip()
    clean = not git("status", "--porcelain=v1", "--untracked-files=all")
    return {"sha": sha, "clean": clean}


def write_report(event, **fields):
    global report_checks
    if report_stream is not None:
        print(
            json.dumps({"event": event, **fields}, ensure_ascii=False),
            file=report_stream,
            flush=True,
        )
        report_checks += event == "check"


def execute(args):
    if args.mode == "docs":
        run([PYTHON, "tools/docs.py"])
    elif args.mode == "quick":
        quick()
    else:
        stack(args.mode, args.node)


def with_report(args, path):
    global report_stream, report_checks
    before = git_snapshot(ROOT)
    with Path(path).open("x", encoding="utf-8") as stream:
        report_stream = stream
        report_checks = 0
        try:
            write_report("start", version=1, suite=args.mode, **before)
            code = 1
            try:
                execute(args)
                code = 0
            except SystemExit as error:
                code = (
                    error.code
                    if type(error.code) is int
                    else int(error.code is not None)
                )
                raise
            finally:
                try:
                    after = git_snapshot(ROOT)
                    write_report("finish", code=code, checks=report_checks, **after)
                except (OSError, subprocess.SubprocessError):
                    if code == 0:
                        raise
                    print("Could not finish check report", file=sys.stderr)
        finally:
            report_stream = None


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
                ("PG", "POSTGRES_", "DJANGO_", "FILMOTEKA_TEST_", "KINOPOISK_")
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

    if mode == "full":
        upgrade_env = test_env()
        if "PG_BIN" in os.environ:
            upgrade_env["PG_BIN"] = os.environ["PG_BIN"]
        run([PYTHON, "-m", "tools.upgrade_check"], upgrade_env)
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
                run(
                    [
                        PYTHON,
                        "-m",
                        "tools.browser",
                        url,
                        str(folder / "browser-state.json"),
                    ],
                    env,
                )
        if mode in {"browser", "full"}:
            with django_server(folder, env, ROOT) as url:
                run(
                    [
                        PYTHON,
                        "-m",
                        "tools.browser",
                        url,
                        str(folder / "browser-state.json"),
                        "reopen",
                    ],
                    env,
                )

            revoked_env = {**env, "FILMOTEKA_TEST_DATA_APPROVED": "0"}
            with django_server(folder, revoked_env, ROOT) as url:
                run(
                    [
                        PYTHON,
                        "-m",
                        "tools.browser",
                        url,
                        str(folder / "browser-state.json"),
                        "revoked",
                    ],
                    revoked_env,
                )


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
    if args.mode == "target" and not args.node:
        parser.error("target requires a pytest node ID")
    if report_path := os.environ.get("FILMOTEKA_CHECK_REPORT"):
        try:
            with_report(args, report_path)
        except (OSError, subprocess.SubprocessError) as error:
            parser.exit(1, f"Could not complete check report: {error}\n")
    else:
        execute(args)
