"""Check repository documentation without third-party dependencies."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATES = {
    "запланировано",
    "в работе",
    "на ревью",
    "нужны исправления",
    "принято",
    "интегрировано",
    "отменено",
}
DEPLOYMENTS = {"не требуется", "не запланирована", "ожидает", "выполнена", "откачена"}
SECTIONS = {
    "Цель и критерии",
    "Реализация",
    "Проверки",
    "Ревью и интеграция",
    "Эксплуатация",
    "Следующий шаг",
}


TERMINAL = {"интегрировано", "отменено"}
TASK_ID = r"T-[0-9]{3,}"
ROW = re.compile(rf"^- \[([ x])\] ({TASK_ID}) (\S.*?)\s+\|\s+(.*)$")


@dataclass(frozen=True)
class Task:
    task_id: str
    title: str
    stage: str
    owner: str
    deployment: str
    blocker: str
    spec: str
    notes: str


def parse_backlog(text, *, historical=False):
    tasks = {}
    errors = []
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        if fenced or not re.match(r"^\s*[-*+]\s+\[", line):
            continue
        label = f"BACKLOG:{number}"
        match = ROW.fullmatch(line)
        if not match:
            errors.append(f"{label}: invalid task row")
            continue
        checked, task_id, title, fields = match.groups()
        values = [field.strip() for field in fields.split("|")]
        previous_format = historical and len(values) == 5
        if previous_format:
            values.insert(1, "—")
        if len(values) != 6 or not all(values):
            errors.append(
                f"{label}: expected stage, owner, deployment, blocker, spec and notes"
            )
            continue
        stage, owner, deployment, blocker, spec, notes = values
        if task_id in tasks:
            errors.append(f"{label}: duplicate ID {task_id}")
            continue
        tasks[task_id] = Task(
            task_id, title, stage, owner, deployment, blocker, spec, notes
        )
        if stage not in STATES:
            errors.append(f"{label}: invalid stage")
        if (checked == "x") != (stage in TERMINAL):
            errors.append(f"{label}: checkbox disagrees with stage")
        if not previous_format and owner not in {
            "разработчик",
            "ревьюер",
            "эксплуатация",
        }:
            errors.append(f"{label}: invalid owner")
        if not previous_format and blocker != "нет":
            scopes = []
            for entry in blocker.split("; "):
                match = re.fullmatch(r"(реализация|приёмка|выкладка): \S.*", entry)
                if not match or match[1] in scopes:
                    errors.append(f"{label}: invalid or duplicate blocker scope")
                    break
                scopes.append(match[1])
        if deployment not in DEPLOYMENTS:
            errors.append(f"{label}: invalid deployment status")
        if spec != "—":
            target = f"TASKS/{task_id}.md"
            if not re.fullmatch(rf"\[[^\]]+\]\({re.escape(target)}\)", spec):
                errors.append(f"{label}: specification must link to {target}")
    if not tasks:
        errors.append("BACKLOG: no task records")
    return tasks, errors


def read_backlog(root):
    path = root / "KB" / "BACKLOG.md"
    tasks, errors = parse_backlog(path.read_text(encoding="utf-8"))
    for task in tasks.values():
        if (
            task.spec != "—"
            and not (path.parent / "TASKS" / f"{task.task_id}.md").is_file()
        ):
            errors.append(f"BACKLOG: missing specification TASKS/{task.task_id}.md")
    return tasks, errors


def anchors(text):
    result = set()
    counts = {}
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        if fenced:
            continue
        match = re.match(r"^#{1,6} +(.+?)(?: +#+)?$", line)
        if not match:
            continue
        heading = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", match[1])
        slug = "".join(
            c
            for c in heading.lower()
            if c in " _-" or unicodedata.category(c)[0] in {"L", "N", "M"}
        ).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


def check_docs(root):
    tasks, errors = read_backlog(root)
    documents = [root / "AGENTS.md", root / "CHANGELOG.md"]
    documents += sorted((root / "KB").rglob("*.md"))
    for document in documents:
        text = document.read_text(encoding="utf-8")
        prose = re.sub(r"^(```|~~~).*?^\1[^\n]*$", "", text, flags=re.M | re.S)
        for link in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", prose):
            target = urlsplit(link)
            if target.scheme or target.netloc:
                continue
            path = document.parent / unquote(target.path) if target.path else document
            if not path.exists():
                errors.append(f"{document.relative_to(root)}: missing {link}")
            elif target.fragment and path.suffix == ".md":
                if unquote(target.fragment) not in anchors(
                    path.read_text(encoding="utf-8")
                ):
                    errors.append(
                        f"{document.relative_to(root)}: missing anchor {link}"
                    )
        if document.parent != root / "KB" / "TASKS" or document.name == "TEMPLATE.md":
            continue
        task = tasks.get(document.stem)
        if task is None or task.spec == "—":
            errors.append(f"{document.name}: unregistered specification")
        if not re.match(rf"^# {re.escape(document.stem)} · \S", prose):
            errors.append(f"{document.name}: invalid specification ID")
        if re.search(
            r"^(ID|Статус|Исполнитель|Ответственный|Блокировка|Выкладка):", text, re.M
        ):
            errors.append(f"{document.name}: keep task state in BACKLOG")
        for section in SECTIONS:
            if not re.search(rf"^## {re.escape(section)}\s*$", text, re.M):
                errors.append(f"{document.name}: missing section {section}")
    current = (root / "KB" / "CURRENT_STATE.md").read_text(encoding="utf-8")
    if "(BACKLOG.md)" not in current or re.search(r"\bT-[0-9]{3,}\b", current):
        errors.append("CURRENT_STATE: use a pointer to BACKLOG without task records")
    decisions = (root / "KB" / "DECISIONS.md").read_text(encoding="utf-8")
    ids = re.findall(r"^\| (R\d+) \||^## (R\d+)\.", decisions, re.M)
    seen = set()
    for pair in ids:
        decision_id = next(value for value in pair if value)
        if decision_id in seen:
            errors.append(f"DECISIONS: duplicate ID {decision_id}")
        seen.add(decision_id)
    return errors


if __name__ == "__main__":
    try:
        errors = check_docs(ROOT)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    if errors:
        raise SystemExit("\n".join(errors))
    print("Documentation links, anchors and task records OK")
