"""Offline-only regression tests for v6.2 real-client runner.
All client subprocesses are mocked. Never tests real LLM skill discovery.
"""
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import importlib.util
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
import os
# Импортирует модуль или имена, используемые в этом файле.
from unittest.mock import patch
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
import subprocess
# Импортирует модуль или имена, используемые в этом файле.
import unittest

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Сохраняет или обновляет вычисленное значение для последующих операций.
modpath = ROOT / 'integration/runtime/cli_e2e.py'
# Сохраняет или обновляет вычисленное значение для последующих операций.
spec = importlib.util.spec_from_file_location('cli_e2e', modpath)
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(modpath.parent))
# Сохраняет или обновляет вычисленное значение для последующих операций.
cli = importlib.util.module_from_spec(spec)
# Формирует часть выражения или передаёт аргумент в текущую операцию.
spec.loader.exec_module(cli)
# Импортирует модуль или имена, используемые в этом файле.
import real_client

# Определяет класс и его интерфейс.
class TestExplicitClientRunner(unittest.TestCase):
    # Объявляет функцию setUp и её параметры.
    def setUp(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.tmp = tempfile.TemporaryDirectory()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.path = Path(self.tmp.name)
    # Объявляет функцию tearDown и её параметры.
    def tearDown(self):
        # Вызывает проверку или метод текущего объекта.
        self.tmp.cleanup()
    # Объявляет функцию prepare и её параметры.
    def prepare(self, platform = 'codex', fixture = 'skill-clean'):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare(platform, self.path, fixture)

    # Объявляет функцию test_commands_have_explicit_read_only_modes и её параметры.
    def test_commands_have_explicit_read_only_modes(self):
        # Перебирает элементы набора для последовательной обработки.
        for platform in cli.BINARY_NAMES:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            argv = cli.command_for(platform)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(argv[ - 1], cli.PROMPT)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse(any(x in argv for x in ['--full-auto', '--force', '--dangerously-skip-permissions', '--auto']))
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('read-only', cli.command_for('codex'))
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('plan', cli.command_for('claude-code'))
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(cli.command_for('deepseek-harness')[: 3], ['dsh', '--profile', 'headless'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('--mode=ask', cli.command_for('cursor'))
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(cli.command_for('opencode')[4], 'plan')

    # Объявляет функцию test_missing_binary_does_not_execute и её параметры.
    def test_missing_binary_does_not_execute(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = None), patch.object(cli.subprocess, 'run') as sub:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = cli.run(self.path, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['status'], 'BLOCKED_CLI_NOT_FOUND')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(r['client_executed'])
        # Настраивает аргументы, параметры или состояние объекта.
        sub.assert_not_called()

    # Объявляет функцию test_plan_never_executes_and_marks_not_tested и её параметры.
    def test_plan_never_executes_and_marks_not_tested(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare('cursor')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.subprocess, 'run') as sub, patch.object(cli.shutil, 'which', return_value = None):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = cli.plan(self.path)
        # Настраивает аргументы, параметры или состояние объекта.
        sub.assert_not_called()
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(p['status'], 'BLOCKED_CLI_NOT_FOUND')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(p['client_skill_discovery'], 'NOT_TESTED')

    # Объявляет функцию test_consent_required и её параметры.
    def test_consent_required(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.subprocess, 'run') as sub:
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaisesRegex(ValueError, 'BOTH'):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                cli.run(self.path, execute = True, consent = False)
            # Настраивает аргументы, параметры или состояние объекта.
            sub.assert_not_called()

    # Объявляет функцию test_implicit_run_is_plan и её параметры.
    def test_implicit_run_is_plan(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = None), patch.object(cli.subprocess, 'run') as sub:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = cli.run(self.path)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['status'], 'BLOCKED_CLI_NOT_FOUND')
        # Настраивает аргументы, параметры или состояние объекта.
        sub.assert_not_called()

    # Объявляет функцию test_modified_source_blocks_launch и её параметры.
    def test_modified_source_blocks_launch(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.path / 'subject/SKILL.md').write_text('corrupted', encoding = 'utf-8')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.subprocess, 'run') as sub:
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaisesRegex(ValueError, 'fixture was changed'):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                cli.run(self.path, execute = True, consent = True)
            # Настраивает аргументы, параметры или состояние объекта.
            sub.assert_not_called()

    # Объявляет функцию test_client_binary_restrictions и её параметры.
    def test_client_binary_restrictions(self):
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertNotIn('cursor', cli.BINARY_NAMES['cursor'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertNotIn('cursor', real_client.CLIENT_BINS['cursor'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(set(cli.BINARY_NAMES), set(real_client.PLATFORMS))

    # Объявляет функцию test_opencode_denies_risky_tools и её параметры.
    def test_opencode_denies_risky_tools(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare('opencode')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = cli._read_only_opencode_config(self.path)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        blocked = {x['resource'] for x in result['policies']}
        # Перебирает элементы набора для последовательной обработки.
        for item in ('shell:*', 'edit:*', 'external_directory:*', 'webfetch:*', 'websearch:*', 'execute:*'):
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertIn(item, blocked)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.path / 'opencode.json').write_text('already exists', encoding = 'utf-8')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(ValueError, 'existing'):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            cli._read_only_opencode_config(self.path)

    # Объявляет функцию test_isolated_environment_does_not_inherit_random_secrets и её параметры.
    def test_isolated_environment_does_not_inherit_random_secrets(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.dict(os.environ, {'UNRELATED_PASSWORD': 'private value'}, clear = False):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            env = cli._isolated_env(self.path)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertNotIn('UNRELATED_PASSWORD', env)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(Path(env['HOME']), self.path / '.integration-test/client-home')

    # Объявляет функцию test_api_key_redacted и её параметры.
    def test_api_key_redacted(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        env = {'OPENAI_API_KEY': 'sk-FICTIONALabcdefghijklmno'}
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        redacted = cli._redact(b'API key sk-FICTIONALabcdefghijklmno', env)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertNotIn('abcdefghijklmno', redacted)

    # Объявляет функцию test_mocked_success_does_not_certify_client и её параметры.
    def test_mocked_success_does_not_certify_client(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare('claude-code')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fake = subprocess.CompletedProcess(['claude'], 0, stdout = b'{"status":"success"}', stderr = b'')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = '/fake/claude'), patch.object(cli.subprocess, 'run', return_value = fake) as sub:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = cli.run(self.path, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['process_status'], 'EXIT_ZERO')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(r['client_pass_certified'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['client_skill_activation'], 'REVIEW_REQUIRED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(r['source_unchanged'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(sub.call_args.kwargs['cwd'], self.path.resolve())
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(sub.call_args.kwargs.get('shell', False))
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue((self.path / r['stdout_file']).is_file())

    # Объявляет функцию test_nonzero_execution_is_not_skill_test и её параметры.
    def test_nonzero_execution_is_not_skill_test(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare('codex')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fake = subprocess.CompletedProcess(['codex'], 1, stdout = b'', stderr = b'auth failed')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = '/fake/codex'), patch.object(cli.subprocess, 'run', return_value = fake):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = cli.run(self.path, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['process_status'], 'NONZERO_EXIT')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['client_skill_activation'], 'NOT_TESTED')

    # Объявляет функцию test_timeout_recorded_without_certification и её параметры.
    def test_timeout_recorded_without_certification(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare('claude-code')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = '/fake/claude'), patch.object(cli.subprocess, 'run', side_effect = subprocess.TimeoutExpired(cmd = 'claude', timeout = 60)):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = cli.run(self.path, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['process_status'], 'TIMEOUT')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(r['client_pass_certified'])

    # Объявляет функцию test_out_of_range_timeout и её параметры.
    def test_out_of_range_timeout(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(ValueError, 'timeout'):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            cli.run(self.path, execute = True, consent = True, timeout = 0)

    # Объявляет функцию test_log_writer_never_overwrites и её параметры.
    def test_log_writer_never_overwrites(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        path = self.path / 'file.txt'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        cli._write_private(path, 'one')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(ValueError, 'overwriting'):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            cli._write_private(path, 'two')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(path.read_text(), 'one')

    # Объявляет функцию test_detect_symlink_fixture и её параметры.
    def test_detect_symlink_fixture(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        other = self.path / 'other'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        other.write_text('outside')
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.path / 'subject/unsafe-link').symlink_to(other)
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaises(ValueError):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            cli.plan(self.path)

    # Объявляет функцию test_executed_opencode_writes_restricted_config_only и её параметры.
    def test_executed_opencode_writes_restricted_config_only(self):
        # Вызывает проверку или метод текущего объекта.
        self.prepare('opencode')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fake = subprocess.CompletedProcess(['opencode'], 0, stdout = b'{}', stderr = b'')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = '/fake/opencode'), patch.object(cli.subprocess, 'run', return_value = fake):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = cli.run(self.path, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue((self.path / 'opencode.json').is_file())
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(r['source_unchanged'])
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli.shutil, 'which', return_value = '/fake/opencode'), patch.object(cli.subprocess, 'run', return_value = fake):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            second = cli.run(self.path, execute = True, consent = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(second['process_status'], 'EXIT_ZERO')

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Запускает автоматические проверки при прямом запуске файла.
    unittest.main()

# Определяет класс и его интерфейс.
class TestEvidenceCheck(unittest.TestCase):
    # Объявляет функцию test_no_run_remains_not_tested и её параметры.
    def test_no_run_remains_not_tested(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real_client.prepare('codex', p, 'skill-clean')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(cli.verify(p)['status'], 'NOT_TESTED')

    # Объявляет функцию test_mock_run_logs_verified_but_not_certified и её параметры.
    def test_mock_run_logs_verified_but_not_certified(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real_client.prepare('codex', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            fake = subprocess.CompletedProcess(['codex'], 0, stdout = b'{"text":"a"}', stderr = b'')
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with patch.object(cli.shutil, 'which', return_value = '/fake/codex'), patch.object(cli.subprocess, 'run', return_value = fake):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                cli.run(p, execute = True, consent = True)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = cli.verify(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['status'], 'LOCAL_LOGS_VERIFIED_CLIENT_REVIEW_REQUIRED')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse(result['client_pass_certified'])

    # Объявляет функцию test_tampered_log_is_detected и её параметры.
    def test_tampered_log_is_detected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real_client.prepare('codex', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            fake = subprocess.CompletedProcess(['codex'], 0, stdout = b'{"text":"a"}', stderr = b'')
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with patch.object(cli.shutil, 'which', return_value = '/fake/codex'), patch.object(cli.subprocess, 'run', return_value = fake):
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                record = cli.run(p, execute = True, consent = True)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / record['stdout_file']).write_text('tampered', encoding = 'utf-8')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = cli.verify(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['status'], 'FAILED_LOG_INTEGRITY')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue(any('LOG_CHANGED' in x for x in result['issues']))

    # Объявляет функцию test_unsafe_log_path_is_detected и её параметры.
    def test_unsafe_log_path_is_detected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            real_client.prepare('codex', p, 'skill-clean')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            out = p / '.integration-test/client-runs'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            out.mkdir()
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = {'platform': 'codex', 'client_pass_certified': False, 'stdout_file': '../../etc/passwd', 'stderr_file': '../../etc/passwd'}
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (out / 'fake.json').write_text(json.dumps(r), encoding = 'utf-8')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = cli.verify(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['status'], 'FAILED_LOG_INTEGRITY')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue(any('INVALID_PATH' in x for x in result['issues']))
