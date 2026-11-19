"""Тесты валидатора ссылок audit-workflow/scripts/markdown_links.py.

Требует markdown-it-py.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'skills' / 'audit-workflow' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

try:
    import markdown_it  # noqa: F401
    HAS_MARKDOWN_IT = True
except ImportError:
    HAS_MARKDOWN_IT = False


def _load_markdown_links():
    spec = importlib.util.spec_from_file_location('markdown_links', SCRIPTS / 'markdown_links.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAS_MARKDOWN_IT, 'требуется markdown-it-py')
class MarkdownLinksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ml = _load_markdown_links()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def test_valid_local_link(self):
        self._write('a.md', '[b](b.md)')
        self._write('b.md', '# B')
        errors, warnings = self.ml.check_markdown_links(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_local_link(self):
        self._write('a.md', '[b](missing.md)')
        errors, _ = self.ml.check_markdown_links(self.root)
        self.assertTrue(any('missing local link target' in e for e in errors))

    def test_site_root_link_warns(self):
        self._write('a.md', '[x](/abs/path.md)')
        _, warnings = self.ml.check_markdown_links(self.root)
        self.assertTrue(any('site-root' in w for w in warnings))

    def test_external_url_skipped(self):
        self._write('a.md', '[x](https://example.com) and ![i](https://example.com/i.png)')
        errors, warnings = self.ml.check_markdown_links(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_heading_fragment_valid(self):
        self._write('a.md', '[x](b.md#section)')
        self._write('b.md', '# Section')
        errors, _ = self.ml.check_markdown_links(self.root)
        self.assertEqual(errors, [])

    def test_heading_fragment_invalid(self):
        self._write('a.md', '[x](b.md#nope)')
        self._write('b.md', '# Section')
        errors, _ = self.ml.check_markdown_links(self.root)
        self.assertTrue(any('heading fragment' in e for e in errors))

    def test_link_escapes_package(self):
        self._write('a.md', '[x](../outside.md)')
        errors, _ = self.ml.check_markdown_links(self.root)
        self.assertTrue(any('escapes package' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
