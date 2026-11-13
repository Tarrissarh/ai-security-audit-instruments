"""Regression tests for portable package layout and Windows documentation."""

from pathlib import Path
import tempfile
import unittest
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'skills'
SCRIPT = ROOT / 'scripts' / 'platform_compat.py'
SPEC = importlib.util.spec_from_file_location('platform_compat_v66', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class TestPortableLayout(unittest.TestCase):
    def test_only_skill_directories_in_installable_root(self):
        names = {item.name for item in SKILLS.iterdir()}
        self.assertEqual(names, set(MODULE.IDS))
        for identifier in MODULE.IDS:
            self.assertTrue((SKILLS / identifier / 'SKILL.md').is_file())
            self.assertFalse((ROOT / identifier / 'SKILL.md').exists())

    def test_installer_does_not_copy_developer_docs(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            result = MODULE.stage('claude-code', project, apply=True)
            self.assertEqual(result['status'], 'LOCAL_INSTALL_PASS')
            destination = project / '.claude' / 'skills'
            self.assertEqual({item.name for item in destination.iterdir()}, set(MODULE.IDS))
            for unrelated in ('WINDOWS.md', 'CHANGELOG.md', 'quality', 'integration', 'tests'):
                self.assertFalse((destination / unrelated).exists())

    def test_windows_documentation_has_user_profile_variants(self):
        content = (ROOT / 'WINDOWS.md').read_text(encoding='utf-8')
        self.assertIn('%USERPROFILE%', content)
        self.assertIn('DSH_HOME', content)
        self.assertIn('XDG', content)
        self.assertIn('py -3', content)

    def test_keep_a_changelog(self):
        changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        self.assertTrue(changelog.startswith('# Changelog'))
        self.assertIn('## [Unreleased]', changelog)
        self.assertIn('## [Unreleased]', changelog)
        self.assertFalse((ROOT / 'CHANGELOG-LEGACY.md').exists())

if __name__ == '__main__':
    unittest.main()
