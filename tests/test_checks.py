import sys

import pytest

from tools import check
from tools.ci_scope import docs_only

pytestmark = pytest.mark.quick


@pytest.mark.parametrize("use_cache", [False, True])
def test_full_runs_the_entire_pytest_collection_once(monkeypatch, tmp_path, use_cache):
    commands = []
    monkeypatch.setattr(check, "run", lambda args, env: commands.append(args))
    monkeypatch.delenv("FILMOTEKA_CI_CACHE", raising=False)
    if use_cache:
        monkeypatch.setenv("FILMOTEKA_CI_CACHE", str(tmp_path))

    check.stack("full", None)

    assert ("compose.ci.yaml" in commands[0]) is use_cache
    assert ("--builder" in commands[0]) is use_cache
    assert [args[args.index("run") :] for args in commands if "pytest" in args] == [
        ["run", "--rm", "--no-deps", "checks", "python", "-m", "pytest", "-q"]
    ]


@pytest.mark.parametrize(("operation_code", "exit_code"), [(7, 7), (None, 9)])
def test_cleanup_preserves_the_primary_failure(monkeypatch, operation_code, exit_code):
    def run(args, env):
        if "down" in args:
            raise SystemExit(9)
        if "build" in args and operation_code:
            raise SystemExit(operation_code)

    monkeypatch.setattr(check, "run", run)

    with pytest.raises(SystemExit) as error:
        check.stack("smoke", None)

    assert error.value.code == exit_code


def test_only_known_documentation_paths_bypass_full():
    assert docs_only(["AGENTS.md", "KB/CURRENT_STATE.md", "CHANGELOG.md"])
    assert not docs_only(["KB/CURRENT_STATE.md", "filmoteka/settings.py"])
    assert not docs_only(["unknown.md"])
    assert not docs_only([])


def test_report_records_failed_command_without_output_or_environment(
    monkeypatch, tmp_path
):
    report = tmp_path / "checks.log"
    monkeypatch.setenv("FILMOTEKA_CHECK_REPORT", str(report))

    with pytest.raises(SystemExit) as error:
        check.run(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ['TEST_PASSWORD']); exit(7)",
            ],
            {"TEST_PASSWORD": "secret-only-in-output"},
        )

    assert error.value.code == 7
    log = report.read_text(encoding="utf-8")
    assert "exit 7" in log
    assert "secret-only-in-output" not in log
