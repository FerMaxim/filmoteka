"""Documentation regressions runnable with stdlib unittest as well as pytest."""

import tempfile
import unittest
from pathlib import Path

from tools.ci_scope import docs_only
from tools.docs import SECTIONS, anchors, check_docs


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("AGENTS.md", "# Rules")
        self.write("CHANGELOG.md", "# Changes")
        self.write("KB/DECISIONS.md", "## R01. Decision")
        self.write("KB/CURRENT_STATE.md", "## Активная задача\n[Task](TASKS/T-001.md)")
        self.card = (
            "# Task\nID: T-001\nСтатус: в работе\nИсполнитель: разработчик\n"
            "Блокировка: нет\nВыкладка: не требуется\n\n"
            + "\n\n".join(f"## {section}\nContent" for section in sorted(SECTIONS))
            + "\n"
        )
        self.write("KB/TASKS/T-001.md", self.card)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_valid_nested_task_and_fragment(self):
        self.write("AGENTS.md", "[Task](KB/TASKS/T-001.md#проверки)")
        self.assertEqual(check_docs(self.root), [])

    def test_missing_file_and_anchor_are_reported(self):
        self.write("AGENTS.md", "[Gone](gone.md) [Anchor](CHANGELOG.md#gone)")
        errors = check_docs(self.root)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("missing anchor" in error for error in errors))

    def test_closed_task_cannot_be_active(self):
        self.write("KB/TASKS/T-001.md", self.card.replace("в работе", "интегрировано"))
        self.assertTrue(any("closed active task" in e for e in check_docs(self.root)))

    def test_invalid_card_fields_and_missing_sections(self):
        self.write("KB/TASKS/T-001.md", "ID: T-002\nСтатус: готово\n")
        errors = check_docs(self.root)
        for expected in (
            "invalid ID",
            "invalid status",
            "missing section",
            "missing Исполнитель",
        ):
            self.assertTrue(any(expected in error for error in errors), expected)

    def test_duplicate_decision_is_reported(self):
        self.write("KB/DECISIONS.md", "| R01 | One |\n## R01. Two")
        self.assertTrue(any("duplicate ID R01" in e for e in check_docs(self.root)))

    def test_cyrillic_duplicate_headings_and_code_blocks(self):
        self.assertEqual(
            anchors("## Проверки · сейчас\n## Проверки · сейчас\n```\n## Code\n```"),
            {"проверки--сейчас", "проверки--сейчас-1"},
        )

    def test_known_task_docs_skip_full_but_unknown_files_do_not(self):
        self.assertTrue(docs_only(["KB/TASKS/T-001.md", "KB/OPERATIONS.md"]))
        for path in ("KB/TASKS/run.py", "KB/unknown/deep.md", "tools/docs.py"):
            self.assertFalse(docs_only([path]))


if __name__ == "__main__":
    unittest.main()
