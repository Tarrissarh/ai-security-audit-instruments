"""Regression tests for strict metadata, CommonMark links and safe writing."""
from __future__ import annotations

from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'audit-docs' / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_skills import read_frontmatter
from markdown_links import check_markdown_links
import safe_writer
from safe_writer import publish, PublishError

class TestStrictYAML(unittest.TestCase):
    def parse(self, source: str):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'SKILL.md'
            path.write_text(source, encoding = 'utf-8')
            return read_frontmatter(path)

    def test_valid_folded_yaml(self):
        fm, issues = self.parse('---\nname: valid-skill\ndescription: >-\n  Нормальное описание:\n  много строк\ndisable-model-invocation: true\n---\n# Doc\n')
        self.assertEqual(issues, [])
        self.assertEqual(fm['name'], 'valid-skill')
        self.assertEqual(fm['disable-model-invocation'], 'true')
        self.assertIn('много строк', fm['description'])

    def test_unclosed_flow_sequence_is_rejected(self):
        _, issues = self.parse('---\nname: valid-skill\ndescription: [one, two\n---\n')
        self.assertTrue(issues)

    def test_duplicate_yaml_keys_are_rejected(self):
        _, issues = self.parse('---\nname: valid-skill\nname: evil-skill\ndescription: hi\n---\n')
        self.assertIn('duplicate YAML key', ' '.join(issues))

    def test_incorrect_flag_type_rejected(self):
        _, issues = self.parse('---\nname: valid-skill\ndescription: hello\ndisable-model-invocation: "true"\n---\n')
        self.assertIn('must be boolean', ' '.join(issues))

    def test_non_mapping_yaml_rejected(self):
        _, issues = self.parse('---\n- name: bad\n- description: no\n---\n')
        self.assertTrue(issues)

    def test_disallow_python_object_tag(self):
        _, issues = self.parse('---\nname: skill\ndescription: !!python/object/apply:os.system ["echo hi"]\n---\n')
        self.assertTrue(issues)

    def test_missing_delimiter(self):
        _, issues = self.parse('---\nname: valid-skill\ndescription: hi\n')
        self.assertIn('closing marker', ' '.join(issues))

class TestMarkdownLinks(unittest.TestCase):
    def verify(self, files: dict[str, str]):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents = True, exist_ok = True)
                path.write_text(content, encoding = 'utf-8')
            return check_markdown_links(root)

    def test_inline_image_and_reference_are_checked(self):
        errors, _ = self.verify({'README.md': '![image](missing.png)\n\n[details][docs]\n\n[docs]: missing.md\n'})
        self.assertEqual(len(errors), 2)

    def test_ignore_fences_inline_code(self):
        errors, _ = self.verify({'README.md': '```md\n[broken](missing.md)\n```\n\n`[ignored](missing.md)`\n'})
        self.assertEqual(errors, [])

    def test_valid_reference_nested_parentheses_and_fragments(self):
        errors, _ = self.verify({'README.md': '[ref][r]\n\n[r]: <docs/a(b).md#схема-работы>\n',
                              'docs/a(b).md': '# Схема работы\n'})
        self.assertFalse(errors)

    def test_relative_reference_and_nonexistent_anchor(self):
        errors, _ = self.verify({'README.md': '[x](docs/x.md#несуществующий)\n',
                              'docs/x.md': '# Существующий\n'})
        self.assertIn('unknown Markdown heading fragment', ' '.join(errors))

    def test_duplicate_heading_slug(self):
        errors, _ = self.verify({'README.md': '# Example\n# Example\n[x](#example-1)\n'})
        self.assertEqual(errors, [])

    def test_reject_escape_outside_root(self):
        errors, _ = self.verify({'README.md': '[escape](../../etc/passwd)\n'})
        self.assertIn('escapes package', ' '.join(errors))

    def test_site_root_link_is_warning(self):
        errors, warnings = self.verify({'README.md': '[internal](/assets/app.svg)\n'})
        self.assertFalse(errors)
        self.assertTrue(warnings)

    def test_remote_link_is_not_validated(self):
        errors, _ = self.verify({'README.md': '[remote](https://example.org/any)\n'})
        self.assertFalse(errors)

class TestSafeWriter(unittest.TestCase):
    def make_staging(self, root: Path):
        stage = root / 'staging'
        stage.mkdir()
        (stage / 'README.md').write_text('# Report\n[Details](docs/architecture.md)\n', encoding = 'utf-8')
        (stage / 'docs').mkdir()
        (stage / 'docs/architecture.md').write_text('# Architecture\n[Back](../README.md)\n', encoding = 'utf-8')
        return stage

    def test_publishes_only_report_md(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = self.make_staging(root)
            out = root / 'target' / 'audit'
            result = publish(stage, out)
            self.assertEqual(result['status'], 'COMPLETE')
            self.assertEqual(len(result['files_written']), 2)
            self.assertTrue((out / 'docs/architecture.md').is_file())

    def test_refuse_overwrite_without_explicit_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = self.make_staging(root)
            out = root / 'audit'
            out.mkdir()
            (out / 'README.md').write_text('ORIGINAL', encoding = 'utf-8')
            with self.assertRaises(PublishError):
                publish(stage, out)
            self.assertEqual((out / 'README.md').read_text(), 'ORIGINAL')

    def test_backup_before_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = self.make_staging(root)
            out = root / 'audit'
            out.mkdir()
            original = b'ORIGINAL README\n'
            (out / 'README.md').write_bytes(original)
            result = publish(stage, out, overwrite = True)
            self.assertTrue(result['backups'])
            self.assertEqual((Path(result['backups']) / 'README.md').read_bytes(), original)
            self.assertEqual(hashlib.sha256((Path(result['backups']) / 'README.md').read_bytes()).digest(), hashlib.sha256(original).digest())

    def test_rollback_after_second_write_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = self.make_staging(root)
            out = root / 'audit'
            out.mkdir()
            (out / 'README.md').write_bytes(b'ORIGINAL')
            original_atomic = safe_writer._atomic_replace
            failed = [False]
            def fail_only_second(dest, data, mode):
                if dest.name == 'architecture.md' and not failed[0]:
                    failed[0] = True
                    raise OSError('injected failure')
                return original_atomic(dest, data, mode)
            with patch.object(safe_writer, '_atomic_replace', new = fail_only_second):
                with self.assertRaises(PublishError):
                    publish(stage, out, overwrite = True)
            self.assertEqual((out / 'README.md').read_bytes(), b'ORIGINAL')
            self.assertFalse((out / 'docs/architecture.md').exists())

    def test_deny_symlinked_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = self.make_staging(root)
            (root / 'actual').mkdir()
            link = root / 'audit'
            try:
                link.symlink_to(root / 'actual', target_is_directory = True)
            except (OSError, NotImplementedError):
                self.skipTest('cannot create symlink on current OS')
            with self.assertRaises(PublishError):
                publish(stage, link)

    def test_deny_symlinked_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = self.make_staging(root)
            (stage / 'translations').mkdir()
            try:
                (stage / 'translations' / 'bad.md').symlink_to(root / 'secret.md')
            except (OSError, NotImplementedError):
                self.skipTest('cannot create symlink on current OS')
            with self.assertRaises(PublishError):
                publish(stage, root / 'audit')

    def test_deny_non_markdown_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = self.make_staging(root)
            (stage / 'script.py').write_text('print(123)', encoding = 'utf-8')
            with self.assertRaises(PublishError):
                publish(stage, root / 'audit')

    def test_deny_broken_links(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = self.make_staging(root)
            (stage / 'README.md').write_text('[x](docs/missing.md)', encoding = 'utf-8')
            with self.assertRaises(PublishError):
                publish(stage, root / 'audit')

    def test_deny_nested_output_in_staging(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = self.make_staging(root)
            with self.assertRaises(PublishError):
                publish(stage, stage / 'audit')

if __name__ == '__main__':
    unittest.main()
