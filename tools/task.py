"""Read-only task preflight and handoff from repository evidence."""

import argparse
import re
import subprocess
from pathlib import Path

if not __package__:
    from docs import ROOT, read_backlog
else:
    from tools.docs import ROOT, read_backlog


def git(*args):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )


def required(*args):
    result = git(*args)
    if result.returncode:
        raise ValueError(f"git {args[0]} failed (exit {result.returncode})")
    return result.stdout.strip()


def identity():
    return required("branch", "--show-current") or "(detached)", required(
        "rev-parse", "HEAD"
    )


def preflight(task, branch, head, offline):
    problems = []
    status = required("status", "--porcelain=v1", "--untracked-files=all")
    print(f"Рабочее дерево: {'есть изменения' if status else 'чистое'}")
    if status:
        problems.append("Сверить незакоммиченные изменения.")

    tracked = required("rev-parse", "origin/main")
    print(f"Кэш origin/main: {tracked}")
    base = tracked
    pattern = re.compile(rf"(?<![A-Za-z0-9]){task.task_id}(?![A-Za-z0-9])", re.I)
    aliases = set(re.findall(r"Ветка `([^`]+)`", task.notes))
    remote = None
    if not offline:
        remote = git(
            "ls-remote",
            "--exit-code",
            "origin",
            "refs/heads/main",
            f"refs/heads/*{task.task_id}*",
            f"refs/heads/{branch}",
            *(f"refs/heads/{alias}" for alias in sorted(aliases)),
        )
    if remote is not None and remote.returncode == 0:
        refs = {}
        for line in remote.stdout.splitlines():
            sha, ref = line.split()
            refs[ref.removeprefix("refs/heads/")] = sha
        base = refs.get("main", "")
        if not re.fullmatch(r"[0-9a-f]{40}", base):
            raise ValueError("unexpected main advertisement")
        print(f"Сверено с origin: {base}")
        for name, sha in refs.items():
            if name == branch and name != "main" and sha != head:
                print(f"Опубликованный head: {name} {sha}")
                problems.append("Локальный и опубликованный head различаются.")
            if name != branch and (pattern.search(name) or name in aliases):
                print(f"Опубликованная ветка задачи: {name} {sha}")
                problems.append("Сверить существующую ветку задачи.")
        if base != tracked:
            problems.append("origin/main устарел. Сверить базу после обновления refs.")
    else:
        print("Свежесть origin/main не подтверждена.")
        problems.append("Сверить main с origin.")

    declared_base = re.search(r"База `([0-9a-f]{40})`", task.notes)
    if declared_base and declared_base[1] != base:
        problems.append(
            f"Переданная база {declared_base[1]} отличается от известного main."
        )

    distances = git("rev-list", "--left-right", "--count", f"{base}...{head}")
    if distances.returncode:
        problems.append("История актуальной базы недоступна локально.")
    else:
        behind, ahead = map(int, distances.stdout.split())
        print(f"Относительно main: позади {behind}, впереди {ahead}")
        if behind:
            problems.append("Ветка отстаёт от main. Сверить интегрированные изменения.")
        if ahead:
            print(required("log", "-5", "--oneline", f"{base}..{head}"))
            if not (pattern.search(branch) or branch in aliases):
                problems.append("HEAD содержит коммиты вне main в ветке без ID задачи.")
    if branch == "(detached)":
        problems.append("HEAD не привязан к ветке.")

    branches = required(
        "for-each-ref",
        "--format=%(refname:short) %(objectname)",
        "refs/heads",
        "refs/remotes/origin",
    )
    for line in branches.splitlines():
        name, sha = line.rsplit(" ", 1)
        if (
            pattern.search(name) or name.removeprefix("origin/") in aliases
        ) and name not in {branch, f"origin/{branch}"}:
            print(f"Другая ветка задачи: {name} {sha}")
            problems.append("Сверить существующую ветку задачи.")
        if remote is None or remote.returncode:
            if name != f"origin/{branch}" or sha == head:
                continue
            print(f"Опубликованный head (локальный ref): {sha}")
            problems.append("Локальный и известный опубликованный head различаются.")

    for record in required("worktree", "list", "--porcelain", "-z").split("\0\0"):
        fields = dict(
            field.split(" ", 1) for field in record.split("\0") if " " in field
        )
        path = fields.get("worktree")
        if not path or Path(path).resolve() == ROOT:
            continue
        other_branch = fields.get("branch", "")
        if (
            pattern.search(other_branch)
            or pattern.search(path)
            or other_branch.removeprefix("refs/heads/") in aliases
        ):
            print(
                f"Другая рабочая копия: {path} {other_branch} {fields.get('HEAD', '')}"
            )
            problems.append("Сверить работу в другом worktree.")

    if task.stage not in {"запланировано", "в работе", "нужны исправления"}:
        problems.append("Стадия требует сверки перед реализацией.")
    if task.blocker != "нет":
        problems.append(f"Уточнить ограничение: {task.blocker}")
    for problem in dict.fromkeys(problems):
        print(f"Проверить: {problem}")
    if not problems:
        print("По доступным данным расхождений нет.")
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    start = actions.add_parser("start")
    start.add_argument("id")
    start.add_argument("--offline", action="store_true")
    handoff = actions.add_parser("handoff")
    handoff.add_argument("id")
    handoff.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    try:
        tasks, errors = read_backlog(ROOT)
        if errors:
            raise ValueError("\n".join(errors))
        task = tasks.get(args.id.upper())
        if task is None:
            raise ValueError(f"unknown task {args.id}")
        branch, head = identity()
        print(f"{task.task_id} · {task.title} · {task.stage}")
        print(f"Ветка: {branch}\nHEAD: {head}\nВыкладка: {task.deployment}")
        print("Источники: KB/BACKLOG.md, KB/WORKFLOW.md, KB/ENGINEERING.md")
        print(f"Спецификация и источники: {task.spec} · {task.notes}")
        if args.action == "start":
            return preflight(task, branch, head, args.offline)
        report = args.report.read_text(encoding="utf-8").strip()
        if not report:
            raise ValueError("empty check.py report")
        if required("status", "--porcelain=v1", "--untracked-files=all"):
            raise ValueError("commit task changes before generating a handoff")
        print(
            f"\nПроверки из {args.report.name} (сверить с проверенным SHA):\n{report}"
        )
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
