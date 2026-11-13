# Описывает назначение блока в многострочной строке документации.
"""v6.4 offline evidence aggregation; fake client runs use mock subprocess only."""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import subprocess
# Импортирует модуль или имена, используемые в этом файле.
import sys
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
import real_client
# Импортирует модуль или имена, используемые в этом файле.
import cli_e2e
# Импортирует модуль или имена, используемые в этом файле.
import compatibility_report as review


# Определяет класс и его интерфейс.
class TestReviewV64(unittest.TestCase):
    # Объявляет функцию setUp и её параметры.
    def setUp(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.tmp = tempfile.TemporaryDirectory()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.workspace = Path(self.tmp.name)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare('codex', self.workspace, 'skill-clean')

    # Объявляет функцию tearDown и её параметры.
    def tearDown(self):
        # Вызывает проверку или метод текущего объекта.
        self.tmp.cleanup()

    # Объявляет функцию _fake_run и её параметры.
    def _fake_run(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fake = subprocess.CompletedProcess(['codex'], 0, stdout = b'{"observations":[]}', stderr = b'')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with patch.object(cli_e2e.shutil, 'which', return_value = '/fake/codex'), \
             patch.object(cli_e2e.subprocess, 'run', return_value = fake):
            # Возвращает вычисленный результат вызывающему коду.
            return cli_e2e.run(self.workspace, execute = True, consent = True)

    # Объявляет функцию test_no_logs_no_assertions_stays_not_tested и её параметры.
    def test_no_logs_no_assertions_stays_not_tested(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = review.create_report([self.workspace], include_probe = False)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['overall_status'], 'NOT_TESTED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['client_matrix']['codex']['supplied_workspaces'], 1)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['client_matrix']['cursor']['supplied_workspaces'], 0)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['client_pass_certified'])

    # Объявляет функцию test_empty_workspaces_never_certifies и её параметры.
    def test_empty_workspaces_never_certifies(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = review.create_report([], include_probe = False)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['overall_status'], 'NOT_TESTED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(len(r['client_matrix']), 5)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(all(v['actual_client_e2e'] == 'NOT_TESTED' for v in r['client_matrix'].values()))

    # Объявляет функцию test_operator_pass_with_log_never_becomes_client_pass и её параметры.
    def test_operator_pass_with_log_never_becomes_client_pass(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        run = self._fake_run()
        # Проверяет инвариант или ожидаемый результат теста.
        assert cli_e2e.verify(self.workspace)['status'] == 'LOCAL_LOGS_VERIFIED_CLIENT_REVIEW_REQUIRED'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        file = self.workspace / '.integration-test/evidence.json'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        evidence = json.loads(file.read_text())
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        evidence['checks']['activation'] = {
            # Устанавливает поле status в словаре или описании.
            'status': 'PASS', 'notes': 'human claims success',
            # Устанавливает поле evidence_files в словаре или описании.
            'evidence_files': [run['stdout_file']],
        }
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        file.write_text(json.dumps(evidence), encoding = 'utf-8')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = review.create_report([self.workspace], include_probe = False)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['overall_status'], 'REVIEW_REQUIRED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['workspaces'][0]['checks']['activation']['independent_status'], 'REVIEW_REQUIRED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['client_matrix']['codex']['actual_client_e2e'], 'NOT_TESTED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['client_pass_certified'])

    # Объявляет функцию test_missing_log_invalid_evidence и её параметры.
    def test_missing_log_invalid_evidence(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        file = self.workspace / '.integration-test/evidence.json'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        evidence = json.loads(file.read_text())
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        evidence['checks']['reports'] = {
            # Устанавливает поле status в словаре или описании.
            'status': 'PASS', 'notes': 'not real',
            # Устанавливает поле evidence_files в словаре или описании.
            'evidence_files': ['.integration-test/nonexistent.log'],
        }
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        file.write_text(json.dumps(evidence), encoding = 'utf-8')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = review.create_report([self.workspace], include_probe = False)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['overall_status'], 'INVALID_EVIDENCE')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['client_pass_certified'])

    # Объявляет функцию test_modified_subject_invalid и её параметры.
    def test_modified_subject_invalid(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.workspace / 'subject/SKILL.md').write_text('# modified', encoding = 'utf-8')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = review.create_report([self.workspace], include_probe = False)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['overall_status'], 'INVALID_EVIDENCE')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['client_pass_certified'])

    # Объявляет функцию test_invalid_workspace_safe_failure и её параметры.
    def test_invalid_workspace_safe_failure(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = review.evaluate_workspace(self.workspace / 'no-such-workspace')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['integration_status'], 'INVALID_EVIDENCE')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['client_pass_certified'])

    # Объявляет функцию test_mismatching_run_name_is_detected и её параметры.
    def test_mismatching_run_name_is_detected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        run = self._fake_run()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.workspace / '.integration-test/client-runs' / f"{run['run_id']}.json"
        # Настраивает аргументы, параметры или состояние объекта.
        p.rename(p.with_name('f' * 32 + '.json'))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        checked = cli_e2e.verify(self.workspace)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(checked['status'], 'FAILED_LOG_INTEGRITY')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(any('INVALID_RUN_ID' in x for x in checked['issues']))

    # Объявляет функцию test_forged_record_metadata_is_detected и её параметры.
    def test_forged_record_metadata_is_detected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        run = self._fake_run()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.workspace / '.integration-test/client-runs' / f"{run['run_id']}.json"
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        data = json.loads(p.read_text())
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        data['execution_attempted'] = False
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        data['started_at'] = 'not-a-date'
        # Настраивает аргументы, параметры или состояние объекта.
        p.write_text(json.dumps(data))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        checked = cli_e2e.verify(self.workspace)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(checked['status'], 'FAILED_LOG_INTEGRITY')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(any('INVALID_TIMESTAMP' in x for x in checked['issues']))
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(any('UNTRUSTED_RECORD_FIELDS' in x for x in checked['issues']))

    # Объявляет функцию test_wrong_log_reference_from_valid_run_is_detected и её параметры.
    def test_wrong_log_reference_from_valid_run_is_detected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        run = self._fake_run()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.workspace / '.integration-test/client-runs' / f"{run['run_id']}.json"
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        data = json.loads(p.read_text())
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        data['stdout_file'] = '.integration-test/client-runs/something-else.stdout.txt'
        # Настраивает аргументы, параметры или состояние объекта.
        p.write_text(json.dumps(data))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        checked = cli_e2e.verify(self.workspace)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(any('INVALID_PATH' in x for x in checked['issues']))

    # Объявляет функцию test_symlinked_evidence_invalid и её параметры.
    def test_symlinked_evidence_invalid(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        run = self._fake_run()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        evidence = json.loads((self.workspace / '.integration-test/evidence.json').read_text())
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        linked = self.workspace / '.integration-test/link.log'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        linked.symlink_to(self.workspace / run['stdout_file'])
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        evidence['checks']['discovery'].update(status = 'PASS', evidence_files = ['.integration-test/link.log'])
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.workspace / '.integration-test/evidence.json').write_text(json.dumps(evidence))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = review.create_report([self.workspace], include_probe = False)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['overall_status'], 'INVALID_EVIDENCE')


# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    unittest.main()
