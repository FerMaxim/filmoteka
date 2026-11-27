import sys
from argparse import Namespace
from contextlib import nullcontext

import pytest

from tools import check, native
from tools.ci_scope import docs_only

pytestmark = pytest.mark.quick


def test_full_runs_the_entire_pytest_collection_once(monkeypatch):
    commands = []
    monkeypatch.setattr(check, "run", lambda args, env: commands.append(args))
    monkeypatch.setattr(native, "postgres_cluster", lambda *args: nullcontext({}))
    monkeypatch.setattr(
        native, "django_server", lambda *args: nullcontext("http://test")
    )

    check.stack("full", None)

    assert [args[1:] for args in commands if "pytest" in args] == [
        ["-m", "pytest", "-q"]
    ]


@pytest.mark.parametrize(("operation_code", "exit_code"), [(7, 7), (None, 9)])
def test_cleanup_preserves_the_primary_failure(operation_code, exit_code):
    def cleanup():
        raise SystemExit(9)

    with pytest.raises(SystemExit) as error, native.on_exit(cleanup):
        if operation_code:
            raise SystemExit(operation_code)

    assert error.value.code == exit_code


def test_dev_database_environment_is_not_inherited(monkeypatch):
    for key in ("DATABASE_URL", "POSTGRES_PASSWORD", "PGPASSWORD", "PGHOSTADDR"):
        monkeypatch.setenv(key, "dev-value")
        assert key not in check.test_env()


def test_only_known_documentation_paths_bypass_full():
    assert docs_only(["AGENTS.md", "KB/CURRENT_STATE.md", "CHANGELOG.md"])
    assert not docs_only(["KB/CURRENT_STATE.md", "filmoteka/settings.py"])
    assert not docs_only(["unknown.md"])
    assert not docs_only([])


def test_report_records_failed_command_without_output_or_environment(
    monkeypatch, tmp_path
):
    report = tmp_path / "checks.log"
    monkeypatch.setattr(
        check, "git_snapshot", lambda root: {"sha": "a" * 40, "clean": True}
    )

    def fail(args):
        check.run(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ['TEST_PASSWORD']); exit(7)",
            ],
            {"TEST_PASSWORD": "secret-only-in-output"},
        )

    monkeypatch.setattr(check, "execute", fail)
    with pytest.raises(SystemExit) as error:
        check.with_report(Namespace(mode="docs"), report)
    assert error.value.code == 7
    log = report.read_text(encoding="utf-8")
    assert "exit 7" in log
    assert "secret-only-in-output" not in log
