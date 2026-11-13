"""Regression tests for Windows/Linux portability without running AI clients."""

import importlib.util
import os
from pathlib import Path, PureWindowsPath
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
WRITER_SCRIPTS = ROOT / 'skills' / 'audit-docs' / 'scripts'

for directory in (SCRIPTS, WRITER_SCRIPTS):
    directory_text = str(directory)
    if directory_text not in sys.path:
        sys.path.insert(0, directory_text)

import portable_names
import safe_writer

SPEC = importlib.util.spec_from_file_location('platform_compat_portable', SCRIPTS / 'platform_compat.py')
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)

class PortableNameTests(unittest.TestCase):
    def test_windows_device_names(self):
        for filename in ('CON.md', 'prn.txt', 'AUX', 'LPT9.md', 'com1.py', 'COM¹.md', 'nul.json'):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    portable_names.validate_component(filename)

    def test_forbidden_names_and_characters(self):
        for filename in ('report.', 'report ', 'a:b.md', 'a?.md', 'bad\x01.md'):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    portable_names.validate_component(filename)

    def test_windows_utf16_component_length(self):
        too_long = '🔍' * 128
        with self.assertRaises(ValueError):
            portable_names.validate_component(too_long)

    def test_portable_unicode_names(self):
        path = Path('docs') / 'Обзор_日本語.md'
        self.assertTrue(portable_names.portable_key(path))

    def test_casefold_collision(self):
        errors = portable_names.find_collisions([Path('docs/Report.md'), Path('docs/report.md')])
        self.assertTrue(any('collision' in error for error in errors))

    def test_unicode_normalization_collision(self):
        errors = portable_names.find_collisions([Path('docs/é.md'), Path('docs/e\u0301.md')])
        self.assertTrue(any('collision' in error for error in errors))

    def test_installed_writer_matches_root_portability_rules(self):
        spec = importlib.util.spec_from_file_location('writer_portable_names', WRITER_SCRIPTS / 'portable_names.py')
        installed_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installed_module)
        samples = [Path('docs/é.md'), Path('docs/e\u0301.md'), Path('docs/readme.md')]
        self.assertEqual(portable_names.find_collisions(samples), installed_module.find_collisions(samples))

    def test_windows_reparse_attribute(self):
        fake_metadata = mock.Mock(st_file_attributes=0x400)
        with mock.patch.object(Path, 'is_symlink', return_value=False):
            with mock.patch.object(Path, 'lstat', return_value=fake_metadata):
                self.assertTrue(portable_names.is_link_or_reparse_point(Path('test-junction')))

    def test_pure_windows_project_path(self):
        root = PureWindowsPath(r'C:\Work\Проект')
        self.assertEqual(str(root / '.claude' / 'skills'), r'C:\Work\Проект\.claude\skills')

class PortableInstallerTests(unittest.TestCase):
    def test_existing_case_variant_blocks_install(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / '.claude/skills/Audit-Docs').mkdir(parents=True)
            result = INSTALLER.stage('claude-code', project)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertTrue(any('alias' in item for item in result['errors']))
            self.assertFalse((project / '.claude/skills/audit-workflow').exists())

    def test_source_reserved_filename_blocks_install(self):
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / 'skills'
            shutil.copytree(ROOT / 'skills', clone)
            (clone / 'audit-docs/references/CON.md').write_text('test', encoding='utf-8')
            issues = INSTALLER.validate_bundle(clone)
            self.assertTrue(any('reserved device' in issue for issue in issues))

class PortableWriterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.staging = self.root / 'staging'
        self.output = self.root / 'output'
        self.staging.mkdir()
        (self.staging / 'README.md').write_text('# Отчёт\n', encoding='utf-8')

    def tearDown(self):
        self.temporary.cleanup()

    def test_utf8_bom_crlf_and_unicode_preserved(self):
        content = b'\xef\xbb\xbf' + '# Отчёт\r\nОписание ✅\r\n'.encode('utf-8')
        (self.staging / 'README.md').write_bytes(content)
        result = safe_writer.publish(self.staging, self.output)
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertEqual((self.output / 'README.md').read_bytes(), content)

    def test_backup_bytes_preserved(self):
        old = '# Старый отчёт\r\n'.encode('utf-8')
        self.output.mkdir()
        (self.output / 'README.md').write_bytes(old)
        result = safe_writer.publish(self.staging, self.output, overwrite=True)
        self.assertIsNotNone(result['backups'])
        self.assertEqual((Path(result['backups']) / 'README.md').read_bytes(), old)
        self.assertIn('Отчёт', (self.output / 'README.md').read_text(encoding='utf-8'))

    def test_read_only_existing_report_blocked(self):
        self.output.mkdir()
        target = self.output / 'README.md'
        target.write_bytes(b'# Original\n')
        target.chmod(0o444)
        try:
            with self.assertRaises(safe_writer.PublishError):
                safe_writer.publish(self.staging, self.output, overwrite=True)
            self.assertEqual(target.read_bytes(), b'# Original\n')
        finally:
            target.chmod(0o644)

    def test_existing_case_variant_blocks_publish(self):
        self.output.mkdir()
        (self.output / 'readme.md').write_text('# Existing\n', encoding='utf-8')
        with self.assertRaises(safe_writer.PublishError):
            safe_writer.publish(self.staging, self.output)

    def test_locked_destination_is_not_overwritten(self):
        self.output.mkdir()
        target = self.output / 'README.md'
        target.write_bytes(b'# Original\n')
        with mock.patch.object(safe_writer.os, 'replace', side_effect=PermissionError('locked')):
            with self.assertRaises(safe_writer.PublishError):
                safe_writer.publish(self.staging, self.output, overwrite=True)
        self.assertEqual(target.read_bytes(), b'# Original\n')

    @unittest.skipIf(os.name == 'nt', 'Windows cannot create reserved device file in normal filesystem')
    def test_reserved_device_file_blocked_before_write(self):
        folder = self.staging / 'docs'
        folder.mkdir()
        (folder / 'CON.md').write_text('Document\n', encoding='utf-8')
        with self.assertRaises(safe_writer.PublishError):
            safe_writer.publish(self.staging, self.output)
        self.assertFalse(self.output.exists())

if __name__ == '__main__':
    unittest.main()
