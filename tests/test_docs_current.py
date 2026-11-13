"""Проверки актуальности руководств без дублирования истории выпусков."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DocumentationCurrentTests(unittest.TestCase):
    """Руководства содержат только действующие правила, история — в CHANGELOG."""

    def test_no_release_note_headings_outside_changelog(self):
        pattern = re.compile(r"(?i)^\s{0,3}#{1,6}\s+(?:v\d+\.\d+|дополнение\s+v\d+|обновление\s+v\d+|.*\(v\d+\.\d+\))")
        for file_path in ROOT.rglob("*.md"):
            if file_path.name == "CHANGELOG.md" or "quality/fixtures" in file_path.as_posix():
                continue
            with self.subTest(file=file_path.relative_to(ROOT)):
                for line_number, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
                    self.assertNotRegex(line, pattern, f"{file_path}:{line_number}")

    def test_no_legacy_documents_or_versioned_protocols(self):
        forbidden = (
            "README-LEGACY.md", "CHANGELOG-LEGACY.md", "VALIDATION-v6.5.md",
            "integration/runtime/V62.md", "integration/runtime/V63.md",
            "integration/runtime/V64.md", "integration/runtime/V65.md",
        )
        for relative_path in forbidden:
            with self.subTest(path=relative_path):
                self.assertFalse((ROOT / relative_path).exists())

    def test_single_current_client_protocol(self):
        self.assertTrue((ROOT / "integration/runtime/CLIENT-TESTING.md").is_file())
        self.assertTrue((ROOT / "skills/audit-workflow/references/runtime-evidence.md").is_file())
        workflow = (ROOT / "skills/audit-workflow/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/runtime-evidence.md", workflow)
        self.assertNotIn("runtime-evidence-v6", workflow)

    def test_changelog_is_only_release_history(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [6.7.1] - 2026-11-13", changelog)
        self.assertIn("## [Unreleased]", changelog)


if __name__ == "__main__":
    unittest.main()
