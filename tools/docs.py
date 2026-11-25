"""Check repository documentation without third-party dependencies."""

import re
import unicodedata
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
    errors = []
    documents = [root / "AGENTS.md", root / "CHANGELOG.md"]
    documents += sorted((root / "KB").rglob("*.md"))
    tasks = {}
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for link in re.findall(r"\]\(([^)]+)\)", text):
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
        fields = dict(re.findall(r"^([^:\n]+): (.+)$", text, re.M))
        task_id = fields.get("ID", "")
        if not re.fullmatch(r"T-\d{3,}", task_id) or document.stem != task_id:
            errors.append(f"{document.name}: invalid ID")
        if task_id in tasks:
            errors.append(f"{document.name}: duplicate ID {task_id}")
        tasks[task_id] = fields
        for field in ("Исполнитель", "Блокировка"):
            if not fields.get(field, "").strip():
                errors.append(f"{document.name}: missing {field}")
        if fields.get("Статус") not in STATES:
            errors.append(f"{document.name}: invalid status")
        if fields.get("Выкладка") not in DEPLOYMENTS:
            errors.append(f"{document.name}: invalid deployment status")
        for section in SECTIONS:
            if f"## {section}\n" not in text:
                errors.append(f"{document.name}: missing section {section}")
    current = (root / "KB" / "CURRENT_STATE.md").read_text(encoding="utf-8")
    active = re.search(r"^## Активная задача\n(.*?)(?=^## |\Z)", current, re.M | re.S)
    if not active:
        errors.append("CURRENT_STATE: missing active task section")
    else:
        for task_id in re.findall(r"TASKS/(T-\d{3,})\.md", active[1]):
            if tasks.get(task_id, {}).get("Статус") in {"интегрировано", "отменено"}:
                errors.append(f"CURRENT_STATE: closed active task {task_id}")
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
    errors = check_docs(ROOT)
    if errors:
        raise SystemExit("\n".join(errors))
    print("Documentation links, anchors and task records OK")
