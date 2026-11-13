"""v6.3 regressions for client launcher and evidence verification.

All tests are mocked or local-only: NO actual AI client/model is invoked.
"""
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import importlib.util
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
import subprocess
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
import unittest
# Импортирует модуль или имена, используемые в этом файле.
from unittest.mock import patch

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(ROOT / 'integration' / 'runtime'))
# Импортирует модуль или имена, используемые в этом файле.
import cli_e2e as cli
# Импортирует модуль или имена, используемые в этом файле.
import real_client

# Определяет класс и его интерфейс.
class TestV63Safety(unittest.TestCase):
    # Объявляет функцию setUp и её параметры.
    def setUp(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.t = tempfile.TemporaryDirectory()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.root = Path(self.t.name)
    # Объявляет функцию tearDown и её параметры.
    def tearDown(self):
        # Вызывает проверку или метод текущего объекта.
        self.t.cleanup()

    # Объявляет функцию test_deepseek_documented_headless_command_has_no_invented_flags и её параметры.
    def test_deepseek_documented_headless_command_has_no_invented_flags(self):
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(cli.command_for('deepseek-harness')[: 3], ['dsh', '--profile', 'headless'])
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        argv = cli.command_for('deepseek-harness')
        # Перебирает элементы набора для последовательной обработки.
        for fake in ('--permission-mode', '--approval-policy', '--json', 'read-only'):
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertNotIn(fake, argv)

    # Объявляет функцию test_deepseek_launch_blocked_without_verified_read_only_policy и её параметры.
    def test_deepseek_launch_blocked_without_verified_read_only_policy(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare('deepseek-harness', self.root, 'skill-clean')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = '/bin/dsh'), patch.object(cli.subprocess, 'run') as execution:
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(cli.plan(self.root)['status'], 'BLOCKED_READ_ONLY_UNVERIFIED')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = cli.run(self.root, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['status'], 'BLOCKED_READ_ONLY_UNVERIFIED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['client_executed'])
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        execution.assert_not_called()

    # Объявляет функцию test_symlink_inside_audit_folder_is_rejected и её параметры.
    def test_symlink_inside_audit_folder_is_rejected(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare('codex', self.root, 'skill-clean')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        target = self.root / 'elsewhere'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        target.mkdir()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        audit = self.root / 'subject/audit'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        audit.mkdir()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (audit / 'leak').symlink_to(target, target_is_directory = True)
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(ValueError, 'symlink forbidden'):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            cli.plan(self.root)

    # Объявляет функцию test_symlink_audit_root_is_rejected и её параметры.
    def test_symlink_audit_root_is_rejected(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare('codex', self.root, 'skill-clean')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        outside = self.root / 'elsewhere'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        outside.mkdir()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.root / 'subject/audit').symlink_to(outside, target_is_directory = True)
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(ValueError, 'symlink forbidden'):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real_client.assess(self.root)

    # Объявляет функцию test_normal_report_directory_remains_ignored и её параметры.
    def test_normal_report_directory_remains_ignored(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare('codex', self.root, 'skill-clean')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        audit = self.root / 'subject/audit'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        audit.mkdir()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (audit / 'README.md').write_text('# report', encoding = 'utf-8')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(cli.plan(self.root)['source_unchanged'])

    # Объявляет функцию test_helpful_but_unverified_mock_execution_does_not_certify и её параметры.
    def test_helpful_but_unverified_mock_execution_does_not_certify(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare('codex', self.root, 'skill-issues')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        mock_response = subprocess.CompletedProcess(['codex'], 0, stdout = b'{"skill_name":"audit-workflow"}', stderr = b'')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = '/mock/codex'), patch.object(cli.subprocess, 'run', return_value = mock_response):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = cli.run(self.root, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['client_pass_certified'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['client_skill_activation'], 'REVIEW_REQUIRED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(cli.verify(self.root)['status'], 'LOCAL_LOGS_VERIFIED_CLIENT_REVIEW_REQUIRED')

    # Объявляет функцию test_large_logs_flagged_for_truncation и её параметры.
    def test_large_logs_flagged_for_truncation(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare('codex', self.root, 'skill-clean')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        mock_response = subprocess.CompletedProcess(['codex'], 0, stdout = b'a' * (cli.MAX_STDIO + 1), stderr = b'')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = '/mock/codex'), patch.object(cli.subprocess, 'run', return_value = mock_response):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = cli.run(self.root, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(result['truncated'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['stdout_raw_bytes'], cli.MAX_STDIO + 1)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertLessEqual((self.root / result['stdout_file']).stat().st_size, cli.MAX_STDIO)

    # Объявляет функцию test_binary_not_present_keeps_not_tested и её параметры.
    def test_binary_not_present_keeps_not_tested(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare('cursor', self.root, 'skill-clean')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = None), patch.object(cli.subprocess, 'run') as execution:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = cli.run(self.root, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['status'], 'BLOCKED_CLI_NOT_FOUND')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['client_executed'])
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        execution.assert_not_called()

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Запускает автоматические проверки при прямом запуске файла.
    unittest.main()
