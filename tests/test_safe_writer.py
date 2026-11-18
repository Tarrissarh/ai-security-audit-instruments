"""Тесты публикатора отчётов audit-docs/scripts/safe_writer.py.

Требует markdown-it-py (валидация ссылок внутри safe_writer).
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'skills' / 'audit-docs' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

try:
    import markdown_it  # noqa: F401
    HAS_MARKDOWN_IT = True
except ImportError:
    HAS_MARKDOWN_IT = False


def _load_safe_writer():
    spec = importlib.util.spec_from_file_location('safe_writer', SCRIPTS / 'safe_writer.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAS_MARKDOWN_IT, 'требуется markdown-it-py')
class SafeWriterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sw = _load_safe_writer()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.staging = self.base / 'staging'
        self.staging.mkdir()
        self.output = self.base / 'out'
        (self.staging / 'README.md').write_text('# Report\n\nText.\n', encoding='utf-8')

    def tearDown(self):
        self._tmp.cleanup()

    def test_publish_readme(self):
        result = self.sw.publish(self.staging, self.output)
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertTrue((self.output / 'README.md').is_file())

    def test_requires_readme(self):
        (self.staging / 'README.md').unlink()
        with self.assertRaises(self.sw.PublishError):
            self.sw.publish(self.staging, self.output)

    def test_rejects_empty_file(self):
        (self.staging / 'README.md').write_text('   ', encoding='utf-8')
        with self.assertRaises(self.sw.PublishError):
            self.sw.publish(self.staging, self.output)

    def test_rejects_non_utf8(self):
        (self.staging / 'README.md').write_bytes(b'\xff\xfe\x00\x00 not utf8')
        with self.assertRaises(self.sw.PublishError):
            self.sw.publish(self.staging, self.output)

    def test_rejects_unexpected_file(self):
        (self.staging / 'notes.txt').write_text('x', encoding='utf-8')
        with self.assertRaises(self.sw.PublishError):
            self.sw.publish(self.staging, self.output)

    def test_publish_findings_json_and_sarif(self):
        (self.staging / 'findings.json').write_text('{"a": 1}', encoding='utf-8')
        (self.staging / 'report.sarif').write_text('{"b": 2}', encoding='utf-8')
        result = self.sw.publish(self.staging, self.output)
        self.assertTrue((self.output / 'findings.json').is_file())
        self.assertTrue((self.output / 'report.sarif').is_file())
        self.assertEqual(result['status'], 'COMPLETE')

    def test_overwrite_requires_flag(self):
        self.sw.publish(self.staging, self.output)
        with self.assertRaises(self.sw.PublishError):
            self.sw.publish(self.staging, self.output)

    def test_overwrite_creates_backup(self):
        self.sw.publish(self.staging, self.output)
        (self.staging / 'README.md').write_text('# New\n', encoding='utf-8')
        result = self.sw.publish(self.staging, self.output, overwrite=True)
        self.assertEqual((self.output / 'README.md').read_text(encoding='utf-8'), '# New\n')
        self.assertIsNotNone(result['backups'])

    def test_disjoint_staging_output(self):
        out = self.base / 'out2'
        out.mkdir()
        inner = out / 'staging'
        inner.mkdir()
        (inner / 'README.md').write_text('x', encoding='utf-8')
        with self.assertRaises(self.sw.PublishError):
            self.sw.publish(inner, out)

    def test_rejects_symlink_in_staging(self):
        link = self.staging / 'link.md'
        try:
            link.symlink_to(self.base / 'target.md')
        except (OSError, NotImplementedError):
            self.skipTest('не удалось создать symlink')
        with self.assertRaises(self.sw.PublishError):
            self.sw.publish(self.staging, self.output)


if __name__ == '__main__':
    unittest.main()
