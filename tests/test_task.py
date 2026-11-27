import json
import subprocess
from dataclasses import replace

import pytest

from tools import task
from tools.docs import Task

pytestmark = pytest.mark.quick

BASE = "a" * 40
LATER = "b" * 40


@pytest.fixture
def repo(monkeypatch):
    calls = {
        "status": (0, ""),
        "rev-parse": (0, BASE),
        "ls-remote": (0, f"{BASE}\trefs/heads/main\n"),
        "rev-list": (0, "0 0"),
        "for-each-ref": (0, ""),
        "worktree": (0, ""),
        "cat-file": (0, ""),
        "show": (1, ""),
    }

    def git(*args):
        result, stdout = calls[args[0]]
        return subprocess.CompletedProcess(args, result, stdout, "")

    monkeypatch.setattr(task, "git", git)
    return calls


@pytest.fixture
def record():
    return Task(
        "T-010",
        "Example",
        "запланировано",
        "разработчик",
        "не требуется",
        "нет",
        "—",
        "Criteria",
    )


def test_correct_start_uses_id_or_alias(repo, record):
    assert task.preflight(record, "codex/T-010-example", BASE, False) == 0
    assert (
        task.preflight(
            replace(record, notes="Ветка `codex/example`"),
            "codex/example",
            BASE,
            False,
        )
        == 0
    )


@pytest.mark.parametrize("stage", ["отменено", "интегрировано"])
def test_closed_task(repo, record, stage):
    assert task.preflight(replace(record, stage=stage), "codex/T-010", BASE, False) == 1


@pytest.mark.parametrize("branch", ["main", "codex/T-0100", "(detached)"])
def test_wrong_branch_even_without_commits(repo, record, branch):
    assert task.preflight(record, branch, BASE, False) == 1


def test_parallel_worktree_and_record_divergence(repo, record, capsys):
    repo["worktree"] = (
        0,
        f"worktree /other/T-010\0HEAD {LATER}\0branch refs/heads/codex/T-010-other\0\0",
    )
    repo["for-each-ref"] = (0, f"codex/T-010-other {LATER}")
    repo["show"] = (
        0,
        "- [ ] T-010 Example | в работе | разработчик | не требуется | нет | — | Criteria",
    )
    assert task.preflight(record, "codex/T-010", BASE, False) == 1
    output = capsys.readouterr().out
    assert "Другая рабочая копия" in output
    assert "отличается от main" in output
    assert "отличается от ref codex/T-010-other" in output


@pytest.mark.parametrize("remote", [(0, f"{LATER}\trefs/heads/main\n"), (1, "")])
def test_stale_or_unavailable_main(repo, record, remote, capsys):
    repo["ls-remote"] = remote
    repo["rev-list"] = (1, "")
    assert task.preflight(record, "codex/T-010", BASE, False) == 1
    assert "История актуальной базы недоступна" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("scope", "expected"), [("реализация", 1), ("приёмка", 0), ("выкладка", 0)]
)
def test_scoped_blockers(repo, record, scope, expected):
    assert (
        task.preflight(
            replace(record, blocker=f"{scope}: причина"),
            "codex/T-010",
            BASE,
            False,
        )
        == expected
    )


@pytest.fixture
def report(tmp_path):
    rows = [
        {"event": "start", "version": 1, "suite": "full", "sha": BASE, "clean": True},
        {"event": "check", "code": 0, "message": "pytest: exit 0"},
        {"event": "finish", "code": 0, "checks": 1, "sha": BASE, "clean": True},
    ]
    return tmp_path / "report.jsonl", rows


def write_report(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_report_matches_head_and_suite(report):
    path, rows = report
    write_report(path, rows)
    assert task.verified_report(path, "full", BASE) == ["pytest: exit 0"]
    with pytest.raises(ValueError, match="набора docs"):
        task.verified_report(path, "docs", BASE)
    with pytest.raises(ValueError, match="SHA"):
        task.verified_report(path, "full", LATER)


@pytest.mark.parametrize(
    ("index", "field", "value", "error"),
    [
        (0, "clean", False, "рабочее дерево"),
        (2, "sha", LATER, "SHA"),
        (2, "clean", False, "рабочее дерево"),
        (1, "code", 7, "неуспешную"),
        (2, "code", 7, "неуспешную"),
        (2, "checks", 2, "неполный"),
    ],
)
def test_invalid_report(report, index, field, value, error):
    path, rows = report
    rows[index][field] = value
    write_report(path, rows)
    with pytest.raises(ValueError, match=error):
        task.verified_report(path, "full", BASE)


def test_report_without_completion(report):
    path, rows = report
    write_report(path, rows[:-1])
    with pytest.raises(ValueError, match="неполный"):
        task.verified_report(path, "full", BASE)
