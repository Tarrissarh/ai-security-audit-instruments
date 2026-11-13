# Описывает назначение блока в многострочной строке документации.
"""Regression tests for v5.1: strict metadata, CommonMark links and safe writing."""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations

# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import hashlib
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
import unittest
# Импортирует модуль или имена, используемые в этом файле.
from unittest.mock import patch

# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'audit-docs' / 'scripts'))
# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
# Импортирует модуль или имена, используемые в этом файле.
from validate_skills import read_frontmatter
# Импортирует модуль или имена, используемые в этом файле.
from markdown_links import check_markdown_links
# Импортирует модуль или имена, используемые в этом файле.
import safe_writer
# Импортирует модуль или имена, используемые в этом файле.
from safe_writer import publish, PublishError


# Определяет класс и его интерфейс.
class TestStrictYAML(unittest.TestCase):
    # Объявляет функцию parse и её параметры.
    def parse(self, source: str):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            path = Path(d) / 'SKILL.md'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            path.write_text(source, encoding = 'utf-8')
            # Возвращает вычисленный результат вызывающему коду.
            return read_frontmatter(path)

    # Объявляет функцию test_valid_folded_yaml и её параметры.
    def test_valid_folded_yaml(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fm, issues = self.parse('---\nname: valid-skill\ndescription: >-\n  Нормальное описание:\n  много строк\ndisable-model-invocation: true\n---\n# Doc\n')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(issues, [])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(fm['name'], 'valid-skill')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(fm['disable-model-invocation'], 'true')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('много строк', fm['description'])

    # Объявляет функцию test_unclosed_flow_sequence_is_rejected и её параметры.
    def test_unclosed_flow_sequence_is_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        _, issues = self.parse('---\nname: valid-skill\ndescription: [one, two\n---\n')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(issues)

    # Объявляет функцию test_duplicate_yaml_keys_are_rejected и её параметры.
    def test_duplicate_yaml_keys_are_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        _, issues = self.parse('---\nname: valid-skill\nname: evil-skill\ndescription: hi\n---\n')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('duplicate YAML key', ' '.join(issues))

    # Объявляет функцию test_incorrect_flag_type_rejected и её параметры.
    def test_incorrect_flag_type_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        _, issues = self.parse('---\nname: valid-skill\ndescription: hello\ndisable-model-invocation: "true"\n---\n')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('must be boolean', ' '.join(issues))

    # Объявляет функцию test_non_mapping_yaml_rejected и её параметры.
    def test_non_mapping_yaml_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        _, issues = self.parse('---\n- name: bad\n- description: no\n---\n')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(issues)

    # Объявляет функцию test_disallow_python_object_tag и её параметры.
    def test_disallow_python_object_tag(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        _, issues = self.parse('---\nname: skill\ndescription: !!python/object/apply:os.system ["echo hi"]\n---\n')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(issues)

    # Объявляет функцию test_missing_delimiter и её параметры.
    def test_missing_delimiter(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        _, issues = self.parse('---\nname: valid-skill\ndescription: hi\n')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('closing marker', ' '.join(issues))


# Определяет класс и его интерфейс.
class TestMarkdownLinks(unittest.TestCase):
    # Объявляет функцию verify и её параметры.
    def verify(self, files: dict[str, str]):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Перебирает элементы набора для последовательной обработки.
            for name, content in files.items():
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                path = root / name
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                path.parent.mkdir(parents = True, exist_ok = True)
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                path.write_text(content, encoding = 'utf-8')
            # Возвращает вычисленный результат вызывающему коду.
            return check_markdown_links(root)

    # Объявляет функцию test_inline_image_and_reference_are_checked и её параметры.
    def test_inline_image_and_reference_are_checked(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        errors, _ = self.verify({'README.md': '![image](missing.png)\n\n[details][docs]\n\n[docs]: missing.md\n'})
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(len(errors), 2)

    # Объявляет функцию test_ignore_fences_inline_code и её параметры.
    def test_ignore_fences_inline_code(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        errors, _ = self.verify({'README.md': '```md\n[broken](missing.md)\n```\n\n`[ignored](missing.md)`\n'})
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(errors, [])

    # Объявляет функцию test_valid_reference_nested_parentheses_and_fragments и её параметры.
    def test_valid_reference_nested_parentheses_and_fragments(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        errors, _ = self.verify({'README.md': '[ref][r]\n\n[r]: <docs/a(b).md#схема-работы>\n',
                              # Формирует часть выражения или передаёт аргумент в текущую операцию.
                              'docs/a(b).md': '# Схема работы\n'})
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(errors)

    # Объявляет функцию test_relative_reference_and_nonexistent_anchor и её параметры.
    def test_relative_reference_and_nonexistent_anchor(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        errors, _ = self.verify({'README.md': '[x](docs/x.md#несуществующий)\n',
                              # Устанавливает поле docs/x.md в словаре или описании.
                              'docs/x.md': '# Существующий\n'})
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('unknown Markdown heading fragment', ' '.join(errors))

    # Объявляет функцию test_duplicate_heading_slug и её параметры.
    def test_duplicate_heading_slug(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        errors, _ = self.verify({'README.md': '# Example\n# Example\n[x](#example-1)\n'})
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(errors, [])

    # Объявляет функцию test_reject_escape_outside_root и её параметры.
    def test_reject_escape_outside_root(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        errors, _ = self.verify({'README.md': '[escape](../../etc/passwd)\n'})
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('escapes package', ' '.join(errors))

    # Объявляет функцию test_site_root_link_is_warning и её параметры.
    def test_site_root_link_is_warning(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        errors, warnings = self.verify({'README.md': '[internal](/assets/app.svg)\n'})
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(errors)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(warnings)

    # Объявляет функцию test_remote_link_is_not_validated и её параметры.
    def test_remote_link_is_not_validated(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        errors, _ = self.verify({'README.md': '[remote](https://example.org/any)\n'})
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(errors)


# Определяет класс и его интерфейс.
class TestSafeWriter(unittest.TestCase):
    # Объявляет функцию make_staging и её параметры.
    def make_staging(self, root: Path):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        stage = root / 'staging'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        stage.mkdir()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (stage / 'README.md').write_text('# Report\n[Details](docs/architecture.md)\n', encoding = 'utf-8')
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (stage / 'docs').mkdir()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (stage / 'docs/architecture.md').write_text('# Architecture\n[Back](../README.md)\n', encoding = 'utf-8')
        # Возвращает вычисленный результат вызывающему коду.
        return stage

    # Объявляет функцию test_publishes_only_report_md и её параметры.
    def test_publishes_only_report_md(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            stage = self.make_staging(root)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            out = root / 'target' / 'audit'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = publish(stage, out)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['status'], 'COMPLETE')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(len(result['files_written']), 2)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue((out / 'docs/architecture.md').is_file())

    # Объявляет функцию test_refuse_overwrite_without_explicit_flag и её параметры.
    def test_refuse_overwrite_without_explicit_flag(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            stage = self.make_staging(root)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            out = root / 'audit'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            out.mkdir()
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (out / 'README.md').write_text('ORIGINAL', encoding = 'utf-8')
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaises(PublishError):
                # Вызывает функцию для выполнения операции.
                publish(stage, out)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual((out / 'README.md').read_text(), 'ORIGINAL')

    # Объявляет функцию test_backup_before_overwrite и её параметры.
    def test_backup_before_overwrite(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            stage = self.make_staging(root)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            out = root / 'audit'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            out.mkdir()
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            original = b'ORIGINAL README\n'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (out / 'README.md').write_bytes(original)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = publish(stage, out, overwrite = True)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue(result['backups'])
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual((Path(result['backups']) / 'README.md').read_bytes(), original)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(hashlib.sha256((Path(result['backups']) / 'README.md').read_bytes()).digest(), hashlib.sha256(original).digest())

    # Объявляет функцию test_rollback_after_second_write_failure и её параметры.
    def test_rollback_after_second_write_failure(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            stage = self.make_staging(root)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            out = root / 'audit'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            out.mkdir()
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (out / 'README.md').write_bytes(b'ORIGINAL')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            original_atomic = safe_writer._atomic_replace
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            failed = [False]
            # Объявляет функцию fail_only_second и её параметры.
            def fail_only_second(dest, data, mode):
                # Проверяет условие перед выполнением следующего блока.
                if dest.name == 'architecture.md' and not failed[0]:
                    # Сохраняет или обновляет вычисленное значение для последующих операций.
                    failed[0] = True
                    # Прерывает операцию с диагностическим исключением.
                    raise OSError('injected failure')
                # Возвращает вычисленный результат вызывающему коду.
                return original_atomic(dest, data, mode)
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with patch.object(safe_writer, '_atomic_replace', new = fail_only_second):
                # Открывает управляемый контекст и гарантирует его корректное завершение.
                with self.assertRaises(PublishError):
                    # Вызывает функцию для выполнения операции.
                    publish(stage, out, overwrite = True)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual((out / 'README.md').read_bytes(), b'ORIGINAL')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse((out / 'docs/architecture.md').exists())

    # Объявляет функцию test_deny_symlinked_output и её параметры.
    def test_deny_symlinked_output(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            stage = self.make_staging(root)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (root / 'actual').mkdir()
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            link = root / 'audit'
            # Начинает блок с контролируемой обработкой исключений.
            try:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                link.symlink_to(root / 'actual', target_is_directory = True)
            # Перехватывает указанное исключение для безопасной обработки.
            except (OSError, NotImplementedError):
                # Вызывает проверку или метод текущего объекта.
                self.skipTest('cannot create symlink on current OS')
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaises(PublishError):
                # Вызывает функцию для выполнения операции.
                publish(stage, link)

    # Объявляет функцию test_deny_symlinked_source и её параметры.
    def test_deny_symlinked_source(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            stage = self.make_staging(root)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (stage / 'translations').mkdir()
            # Начинает блок с контролируемой обработкой исключений.
            try:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                (stage / 'translations' / 'bad.md').symlink_to(root / 'secret.md')
            # Перехватывает указанное исключение для безопасной обработки.
            except (OSError, NotImplementedError):
                # Вызывает проверку или метод текущего объекта.
                self.skipTest('cannot create symlink on current OS')
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaises(PublishError):
                # Вызывает функцию для выполнения операции.
                publish(stage, root / 'audit')

    # Объявляет функцию test_deny_non_markdown_files и её параметры.
    def test_deny_non_markdown_files(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            stage = self.make_staging(root)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (stage / 'script.py').write_text('print(123)', encoding = 'utf-8')
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaises(PublishError):
                # Вызывает функцию для выполнения операции.
                publish(stage, root / 'audit')

    # Объявляет функцию test_deny_broken_links и её параметры.
    def test_deny_broken_links(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            stage = self.make_staging(root)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (stage / 'README.md').write_text('[x](docs/missing.md)', encoding = 'utf-8')
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaises(PublishError):
                # Вызывает функцию для выполнения операции.
                publish(stage, root / 'audit')

    # Объявляет функцию test_deny_nested_output_in_staging и её параметры.
    def test_deny_nested_output_in_staging(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            stage = self.make_staging(root)
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaises(PublishError):
                # Вызывает функцию для выполнения операции.
                publish(stage, stage / 'audit')


# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Запускает автоматические проверки при прямом запуске файла.
    unittest.main()
