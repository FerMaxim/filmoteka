"""Read-only task preflight and handoff from repository evidence."""

import argparse
import json
import re
import subprocess
from dataclasses import replace
from pathlib import Path

if not __package__:
    from check import git_snapshot
    from docs import ROOT, parse_backlog, read_backlog
else:
    from tools.check import git_snapshot
    from tools.docs import ROOT, parse_backlog, read_backlog


def git(*args):
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(ROOT), *args],
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


def compare_record(task, ref, sha, problems):
    if git("cat-file", "-e", f"{sha}^{{commit}}").returncode:
        print(f"Неполные сведения: объект {ref} {sha} недоступен локально.")
        return
    result = git("show", f"{sha}:KB/BACKLOG.md")
    if result.returncode == 0:
        tasks, errors = parse_backlog(result.stdout, historical=True)
        if errors:
            problems.append(f"Сверить реестр {ref}: запись не удалось разобрать.")
            return
        other = tasks.get(task.task_id)
        if other is not None:
            if other.owner == "—":
                print(f"Неполные сведения: {ref} использует прежний формат реестра.")
                other = replace(other, owner=task.owner)
                task = replace(
                    task,
                    blocker=re.sub(
                        r"(?:реализация|приёмка|выкладка): ", "", task.blocker
                    ),
                )
            if other != task:
                problems.append(
                    f"Запись {task.task_id} отличается от {ref} "
                    f"(стадия там: {other.stage})."
                )
            return
    else:
        legacy = git("show", f"{sha}:KB/TASKS/{task.task_id}.md")
        if legacy.returncode == 0:
            values = dict(re.findall(r"^(Статус|Выкладка): (.+)$", legacy.stdout, re.M))
            if values:
                print(
                    f"Неполные сведения: {ref} содержит прежнюю карточку; "
                    "сверены только стадия и выкладка."
                )
                expected = {"Статус": task.stage, "Выкладка": task.deployment}
                if any(expected[key] != value for key, value in values.items()):
                    problems.append(
                        f"Запись {task.task_id} отличается от прежней карточки {ref}."
                    )
                return
    print(f"Неполные сведения: {ref} не содержит записи {task.task_id}.")


def preflight(task, branch, head, offline):
    problems = []
    print(
        "Пределы проверки: доступные Git refs и зарегистрированные worktree "
        "по ID или alias. Другие клоны, незарегистрированные копии и чаты не видны."
    )
    status = required("status", "--porcelain=v1", "--untracked-files=all")
    print(f"Рабочее дерево: {'есть изменения' if status else 'чистое'}")
    if status:
        problems.append("Сверить незакоммиченные изменения.")

    cached = git("rev-parse", "--verify", "refs/remotes/origin/main")
    tracked = cached.stdout.strip() if cached.returncode == 0 else None
    print(f"Кэш origin/main: {tracked or 'недоступен'}")
    base = tracked
    pattern = re.compile(rf"(?<![A-Za-z0-9]){task.task_id}(?![A-Za-z0-9])", re.I)
    aliases = set(re.findall(r"Ветка `([^`]+)`", task.notes))
    if branch == "main" or not (pattern.search(branch) or branch in aliases):
        problems.append(
            "Для реализации нужна рабочая ветка с ID задачи или её alias; main запрещена."
        )
    remote = None
    refs = {}
    if not offline:
        try:
            remote = git(
                "ls-remote",
                "--exit-code",
                "origin",
                "refs/heads/main",
                f"refs/heads/*{task.task_id}*",
                f"refs/heads/{branch}",
                *(f"refs/heads/{alias}" for alias in sorted(aliases)),
            )
        except subprocess.TimeoutExpired:
            print("Неполные сведения: origin не ответил вовремя.")
    if remote is not None and remote.returncode == 0:
        for line in remote.stdout.splitlines():
            sha, ref = line.split()
            refs[ref.removeprefix("refs/heads/")] = sha
        base = refs.get("main")
        if base is None or not re.fullmatch(r"[0-9a-f]{40}", base):
            raise ValueError("origin не сообщил SHA main")
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

    distances = (
        git("rev-list", "--left-right", "--count", f"{base}...{head}") if base else None
    )
    if distances is None or distances.returncode:
        problems.append("История актуальной базы недоступна локально.")
    else:
        behind, ahead = map(int, distances.stdout.split())
        print(f"Относительно main: позади {behind}, впереди {ahead}")
        if behind:
            problems.append("Ветка отстаёт от main. Сверить интегрированные изменения.")
        if ahead:
            print(required("log", "-5", "--oneline", f"{base}..{head}"))
    if branch == "(detached)":
        problems.append("HEAD не привязан к ветке.")

    comparisons = {"main": base} if base else {}
    if tracked and tracked != base:
        comparisons["кэш origin/main"] = tracked
    comparisons.update(
        {
            name: sha
            for name, sha in refs.items()
            if name != "main" and (pattern.search(name) or name in aliases)
        }
    )
    branches = required(
        "for-each-ref",
        "--format=%(refname:short) %(objectname)",
        "refs/heads",
        "refs/remotes/origin",
    )
    for line in branches.splitlines():
        name, sha = line.rsplit(" ", 1)
        if name == "main" and not base:
            comparisons["локальный main"] = sha
        if name != branch and (
            pattern.search(name) or name.removeprefix("origin/") in aliases
        ):
            comparisons[f"ref {name}"] = sha
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
            if re.fullmatch(r"[0-9a-f]{40}", fields.get("HEAD", "")):
                comparisons[f"worktree {path}"] = fields["HEAD"]
            problems.append("Сверить работу в другом worktree.")

    compared = set()
    for ref, sha in comparisons.items():
        if sha not in compared:
            compare_record(task, ref, sha, problems)
            compared.add(sha)

    if task.stage not in {"запланировано", "в работе", "нужны исправления"}:
        problems.append("Стадия требует сверки перед реализацией.")
    if task.blocker != "нет":
        for blocker in task.blocker.split("; "):
            print(f"Блокировка — {blocker}")
            if blocker.startswith("реализация: "):
                problems.append("Снять блокировку реализации.")
    for problem in dict.fromkeys(problems):
        print(f"Проверить: {problem}")
    if not problems:
        print("По доступным данным расхождений нет.")
    return 1 if problems else 0


def verified_report(path, suite, head):
    try:
        with path.open(encoding="utf-8") as stream:
            records = [json.loads(line) for line in stream]
    except json.JSONDecodeError as error:
        raise ValueError("неполный отчёт или неизвестный формат check.py") from error
    if len(records) < 3 or any(not isinstance(row, dict) for row in records):
        raise ValueError("неполный отчёт check.py")
    start, *checks, finish = records
    if (
        start.get("event") != "start"
        or start.get("version") != 1
        or finish.get("event") != "finish"
        or type(finish.get("checks")) is not int
        or finish["checks"] != len(checks)
        or any(
            row.get("event") != "check"
            or type(row.get("code")) is not int
            or not isinstance(row.get("message"), str)
            for row in checks
        )
        or type(finish.get("code")) is not int
    ):
        raise ValueError("неполный отчёт или неизвестный формат check.py")
    if start.get("suite") != suite:
        raise ValueError(f"ожидается отчёт набора {suite}")
    if any(row.get("sha") != head for row in (start, finish)):
        raise ValueError("SHA отчёта отличается от передаваемого HEAD")
    if any(row.get("clean") is not True for row in (start, finish)):
        raise ValueError("во время снимка Git рабочее дерево проверки было изменено")
    if finish["code"] or any(row["code"] for row in checks):
        raise ValueError("отчёт содержит неуспешную проверку")
    return [row["message"] for row in checks]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    start = actions.add_parser("start")
    start.add_argument("id")
    start.add_argument("--offline", action="store_true")
    handoff = actions.add_parser("handoff")
    handoff.add_argument("id")
    handoff.add_argument("--report", type=Path, required=True)
    handoff.add_argument("--suite", choices=["full", "docs"], default="full")
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
        print(f"Ответственный: {task.owner}")
        print("Источники: KB/BACKLOG.md, KB/WORKFLOW.md, KB/ENGINEERING.md")
        print(f"Спецификация и источники: {task.spec} · {task.notes}")
        if args.action == "start":
            return preflight(task, branch, head, args.offline)
        snapshot = git_snapshot(ROOT)
        if not snapshot["clean"] or snapshot["sha"] != head:
            raise ValueError("для передачи нужен текущий HEAD с чистым рабочим деревом")
        checks = verified_report(args.report, args.suite, head)
        print(f"\nНабор {args.suite} прошёл на {head}:")
        print("\n".join(checks))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
