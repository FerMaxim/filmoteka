"""Documentation regressions runnable with stdlib unittest as well as pytest."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.ci_scope import classify, docs_only
from tools.docs import SECTIONS, anchors, check_docs


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("AGENTS.md", "# Rules")
        self.write("CHANGELOG.md", "# Changes")
        self.write("KB/DECISIONS.md", "## R01. Decision")
        self.write("KB/CURRENT_STATE.md", "[Backlog](BACKLOG.md)")
        self.row = (
            "- [ ] T-001 Task | в работе | разработчик | не требуется | нет | "
            "[Spec](TASKS/T-001.md) | Criteria"
        )
        self.write("KB/BACKLOG.md", self.row)
        self.card = (
            "# T-001 · Task\n\n"
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

    def test_stage_checkbox_and_duplicate_active_state(self):
        self.write("KB/BACKLOG.md", self.row + "\n" + self.row.replace("[ ]", "[x]"))
        self.assertTrue(any("duplicate ID" in e for e in check_docs(self.root)))
        self.write("KB/BACKLOG.md", self.row.replace("в работе", "отменено"))
        self.assertTrue(any("checkbox disagrees" in e for e in check_docs(self.root)))
        self.write(
            "KB/BACKLOG.md",
            self.row.replace("в работе", "отменено").replace("[ ]", "[x]"),
        )
        self.assertEqual(check_docs(self.root), [])
        self.write(
            "KB/CURRENT_STATE.md", "[Backlog](BACKLOG.md)\n## Активная задача\nT-001"
        )
        self.assertTrue(any("CURRENT_STATE:" in e for e in check_docs(self.root)))

    def test_simple_task_and_specification_links(self):
        self.write(
            "KB/BACKLOG.md",
            self.row
            + "\n- [ ] T-002 Simple | запланировано | разработчик | не требуется | нет | — | Write instructions",
        )
        self.assertEqual(check_docs(self.root), [])
        self.write(
            "KB/BACKLOG.md", self.row.replace("TASKS/T-001.md", "TASKS/T-002.md")
        )
        self.assertTrue(
            any("specification must link" in e for e in check_docs(self.root))
        )
        self.write("KB/BACKLOG.md", self.row)
        (self.root / "KB/TASKS/T-001.md").unlink()
        self.assertTrue(
            any("missing specification" in e for e in check_docs(self.root))
        )

    def test_archived_specification_requires_a_terminal_record_and_valid_links(self):
        archive = "KB/ARCHIVE/T-001.md"
        (self.root / "KB/CURRENT_STATE.md").unlink()
        (self.root / "KB/TASKS/T-001.md").unlink()
        self.write(archive, self.card)
        row = self.row.replace("TASKS/T-001.md", "ARCHIVE/T-001.md")
        self.write("KB/BACKLOG.md", row)
        self.assertTrue(
            any("specification must link" in e for e in check_docs(self.root))
        )

        row = row.replace("[ ]", "[x]").replace("в работе", "интегрировано")
        self.write("KB/BACKLOG.md", row)
        self.write("AGENTS.md", f"[Evidence]({archive}#проверки)")
        self.assertEqual(check_docs(self.root), [])

        self.write(archive, self.card + "\n[Evidence](missing.png)\n")
        self.assertTrue(any("missing missing.png" in e for e in check_docs(self.root)))

        self.write(
            "KB/BACKLOG.md",
            self.row.replace("в работе", "интегрировано").replace("[ ]", "[x]"),
        )
        self.assertTrue(
            any("unregistered specification" in e for e in check_docs(self.root))
        )

    def test_invalid_specification_fields_and_missing_sections(self):
        self.write("KB/TASKS/T-001.md", "# T-002 · Task\nСтатус: на ревью\n")
        errors = check_docs(self.root)
        for expected in (
            "invalid specification ID",
            "keep task state",
            "missing section",
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
        self.assertTrue(
            docs_only(
                [
                    "KB/TASKS/T-001.md",
                    "KB/ARCHIVE/T-001.md",
                    "KB/OPERATIONS.md",
                    "KB/BACKLOG.md",
                ]
            )
        )
        for path in (
            "KB/TASKS/run.py",
            "KB/ARCHIVE/run.py",
            "KB/ARCHIVE/unknown.md",
            "KB/ASSETS/DESIGN/SVET-04/HANDOFF.md",
            "KB/unknown/deep.md",
            "KB/unknown.md",
            "KB/TASKS/random.md",
            "tools/docs.py",
            "tools/task.py",
        ):
            self.assertFalse(docs_only([path]))

    def test_ci_classification_errors_require_full(self):
        with patch("tools.ci_scope.subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(classify("a" * 40), "full")
        self.assertEqual(classify("--cached"), "full")


if __name__ == "__main__":
    unittest.main()
