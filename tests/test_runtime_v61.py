# Описывает назначение блока в многострочной строке документации.
"""v6.1 evidence preparation and provenance tests: never execute a model client."""
# Импортирует модуль или имена, используемые в этом файле.
import importlib.util
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
import unittest
# Импортирует модуль или имена, используемые в этом файле.
from unittest.mock import patch

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Сохраняет или обновляет вычисленное значение для последующих операций.
spec = importlib.util.spec_from_file_location('real_client', ROOT / 'integration/runtime/real_client.py')
# Сохраняет или обновляет вычисленное значение для последующих операций.
real = importlib.util.module_from_spec(spec)
# Формирует часть выражения или передаёт аргумент в текущую операцию.
spec.loader.exec_module(real)

# Определяет класс и его интерфейс.
class TestRuntimeEvidence(unittest.TestCase):
    # Объявляет функцию test_probe_never_calls_clients и её параметры.
    def test_probe_never_calls_clients(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(real.shutil, 'which', return_value = None) as which:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = real.probe()
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['client_commands_executed'], 0)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(set(r['clients']), set(real.CLIENT_BINS))
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(which.called)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(all(v['actual_skill_execution'] == 'NOT_TESTED' for v in r['clients'].values()))

    # Объявляет функцию test_prepare_all_five_and_assess_without_claim и её параметры.
    def test_prepare_all_five_and_assess_without_claim(self):
        # Перебирает элементы набора для последовательной обработки.
        for platform in real.PLATFORMS:
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.subTest(platform = platform), tempfile.TemporaryDirectory() as d:
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                p = Path(d)
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                prepared = real.prepare(platform, p, 'skill-clean')
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertEqual(prepared['status'], 'READY_FOR_MANUAL_CLIENT_TEST')
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertEqual(prepared['installed_skill_count'], 11)
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertFalse(prepared['client_executed'])
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                r = real.assess(p)
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertTrue(r['source_unchanged'])
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertFalse(r['client_pass_certified'])
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertFalse(r['issues'])
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertEqual(r['checks']['discovery']['operator_assertion'], 'NOT_TESTED')

    # Объявляет функцию test_prepare_requires_empty_workspace и её параметры.
    def test_prepare_requires_empty_workspace(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / 'keep.txt').write_text('DO NOT DELETE')
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaisesRegex(ValueError, 'empty'):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                real.prepare('codex', p, 'skill-clean')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual((p / 'keep.txt').read_text(), 'DO NOT DELETE')

    # Объявляет функцию test_prepare_symlink_workspace_denied и её параметры.
    def test_prepare_symlink_workspace_denied(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            link = p / 'link'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            link.symlink_to(p, target_is_directory = True)
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaisesRegex(ValueError, 'regular'):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                real.prepare('opencode', link, 'skill-clean')

    # Объявляет функцию test_modified_subject_detected и её параметры.
    def test_modified_subject_detected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('claude-code', p, 'skill-clean')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / 'subject/SKILL.md').write_text('modified')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = real.assess(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse(r['source_unchanged'])
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(r['status'], 'FAILED_VALIDATION')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue(any('AUDITED_SOURCE_CHANGED' in x for x in r['issues']))

    # Объявляет функцию test_fake_pass_without_log_rejected и её параметры.
    def test_fake_pass_without_log_rejected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('codex', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            f = p / '.integration-test/evidence.json'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            data = json.loads(f.read_text())
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            data['checks']['discovery']['status'] = 'PASS'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.write_text(json.dumps(data))
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = real.assess(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(r['status'], 'FAILED_VALIDATION')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue(any('UNSUPPORTED_PASS: discovery' in x for x in r['issues']))

    # Объявляет функцию test_attested_pass_still_requires_independent_review и её параметры.
    def test_attested_pass_still_requires_independent_review(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('opencode', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            evidence = p / '.integration-test/evidence.json'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            data = json.loads(evidence.read_text())
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / '.integration-test/session.log').write_text('synthetic test log', encoding = 'utf-8')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            data['checks']['discovery'].update(status = 'PASS', evidence_files = ['.integration-test/session.log'])
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            evidence.write_text(json.dumps(data))
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = real.assess(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(r['status'], 'EVIDENCE_REVIEW_REQUIRED')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(r['checks']['discovery']['independent_client_verification'], 'REVIEW_REQUIRED')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse(r['client_pass_certified'])

    # Объявляет функцию test_evidence_path_traversal_rejected и её параметры.
    def test_evidence_path_traversal_rejected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('cursor', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            f = p / '.integration-test/evidence.json'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            data = json.loads(f.read_text())
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            data['checks']['discovery'].update(status = 'PASS', evidence_files = ['../escape.log'])
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.write_text(json.dumps(data))
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaisesRegex(ValueError, 'escapes'):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                real.assess(p)

    # Объявляет функцию test_evidence_symlink_rejected и её параметры.
    def test_evidence_symlink_rejected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('codex', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            z = Path(outside) / 'log.txt'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            z.write_text('outside')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / '.integration-test/link.log').symlink_to(z)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            f = p / '.integration-test/evidence.json'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            data = json.loads(f.read_text())
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            data['checks']['discovery'].update(status = 'PASS', evidence_files = ['.integration-test/link.log'])
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.write_text(json.dumps(data))
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaisesRegex(ValueError, 'symlink'):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                real.assess(p)

    # Объявляет функцию test_report_assertion_requires_actual_readme и её параметры.
    def test_report_assertion_requires_actual_readme(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('deepseek-harness', p, 'skill-clean')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / '.integration-test/session.log').write_text('observed, but no report')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            f = p / '.integration-test/evidence.json'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            data = json.loads(f.read_text())
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            data['checks']['reports'].update(status = 'PASS', evidence_files = ['.integration-test/session.log'])
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.write_text(json.dumps(data))
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = real.assess(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue(any('no audit/README.md' in s for s in r['issues']))

    # Объявляет функцию test_invalid_check_status_rejected и её параметры.
    def test_invalid_check_status_rejected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('codex', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            f = p / '.integration-test/evidence.json'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            data = json.loads(f.read_text())
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            data['checks']['quality']['status'] = 'SHOULD_PASS'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.write_text(json.dumps(data))
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaisesRegex(ValueError, 'unknown status'):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                real.assess(p)

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Запускает автоматические проверки при прямом запуске файла.
    unittest.main()

# Определяет класс и его интерфейс.
class TestReportIsolation(unittest.TestCase):
    # Объявляет функцию test_report_created_under_subject_does_not_count_as_source_modification и её параметры.
    def test_report_created_under_subject_does_not_count_as_source_modification(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('codex', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            out = p / 'subject/audit'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            out.mkdir()
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (out / 'README.md').write_text('# Audit\n', encoding = 'utf-8')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = real.assess(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue(r['source_unchanged'])
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(r['status'], 'NOT_TESTED')

    # Объявляет функцию test_extra_non_audit_file_detected и её параметры.
    def test_extra_non_audit_file_detected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('codex', p, 'skill-clean')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / 'subject/unknown.txt').write_text('unexpected')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = real.assess(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(r['status'], 'FAILED_VALIDATION')

    # Объявляет функцию test_assess_follows_no_symlink_to_state_files и её параметры.
    def test_assess_follows_no_symlink_to_state_files(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('codex', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            manifest = p / '.integration-test/baseline.json'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            manifest.unlink()
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            manifest.symlink_to(Path(outside) / 'file.json')
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaisesRegex(ValueError, 'symbolic link'):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                real.assess(p)

# Определяет класс и его интерфейс.
class TestReportSymlinks(unittest.TestCase):
    # Объявляет функцию test_report_symlink_cannot_justify_pass и её параметры.
    def test_report_symlink_cannot_justify_pass(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real.prepare('codex', p, 'skill-clean')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (Path(outside) / 'README.md').write_text('# Wrong report')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / 'audit').symlink_to(outside, target_is_directory = True)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / '.integration-test/log.txt').write_text('placeholder')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            f = p / '.integration-test/evidence.json'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            data = json.loads(f.read_text())
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            data['checks']['reports'].update(status = 'PASS', evidence_files = ['.integration-test/log.txt'])
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.write_text(json.dumps(data))
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = real.assess(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['status'], 'FAILED_VALIDATION')
