# Описывает назначение блока в многострочной строке документации.
"""Standalone CLI smoke tests against a temporary mock Skill."""
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

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Сохраняет или обновляет вычисленное значение для последующих операций.
SCRIPT = ROOT / 'skills' / 'audit-workflow' / 'scripts' / 'workflow_state.py'


# Определяет класс и его интерфейс.
class CliSmoke(unittest.TestCase):
    # Объявляет функцию run_cli и её параметры.
    def run_cli(self, * args, ok = True):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        completed = subprocess.run([sys.executable, str(SCRIPT), * map(str, args)],
                                   # Сохраняет или обновляет вычисленное значение для последующих операций.
                                   text = True, capture_output = True, timeout = 20, check = False)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(completed.returncode, 0 if ok else 1, completed.stdout + completed.stderr)
        # Возвращает вычисленный результат вызывающему коду.
        return json.loads(completed.stdout)

    # Объявляет функцию test_end_to_end_preflight_and_resume и её параметры.
    def test_end_to_end_preflight_and_resume(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as directory:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(directory)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            target = root / 'sample-skill'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            target.mkdir()
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (target / 'SKILL.md').write_text('---\nname: sample\ndescription: audit fixture\n---\n# Example\n', encoding = 'utf8')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            report = target / 'audit'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            manifest = self.run_cli('init', '--target', target, '--type', 'skill', '--report-dir', report)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(self.run_cli('resume', '--report-dir', report)['next_stage'], 'PREFLIGHT')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            payload = root / 'preflight.json'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            data = {
                # Устанавливает поле schema_version в словаре или описании.
                'schema_version': '1.0', 'run_id': manifest['run_id'], 'stage': 'PREFLIGHT',
                # Устанавливает поле status в словаре или описании.
                'status': 'COMPLETE', 'method': 'LOCAL_ANALYSIS', 'evidence': ['SKILL.md:1'],
                # Устанавливает поле output_files в словаре или описании.
                'output_files': [], 'invocations': [],
                # Устанавливает поле data в словаре или описании.
                'data': {'host_profile': {'platform': 'other'}}, 'limitations': []
            }
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            payload.write_text(json.dumps(data), encoding = 'utf8')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(self.run_cli('record', '--report-dir', report, '--payload', payload)['status'], 'RECORDED')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(self.run_cli('resume', '--report-dir', report)['next_stage'], 'AUDIT')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(self.run_cli('finalize', '--report-dir', report)['status'], 'PARTIAL')

    # Объявляет функцию test_invalid_result_fails_without_traceback и её параметры.
    def test_invalid_result_fails_without_traceback(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as directory:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = Path(directory)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            target = root / 'sample'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            target.mkdir()
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (target / 'SKILL.md').write_text('# Example', encoding = 'utf8')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            report = target / 'audit'
            # Вызывает проверку или метод текущего объекта.
            self.run_cli('init', '--target', target, '--type', 'skill', '--report-dir', report)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            payload = root / 'invalid.json'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            payload.write_text('{nope}', encoding = 'utf8')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = self.run_cli('record', '--report-dir', report, '--payload', payload, ok = False)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['status'], 'ERROR')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertIn('invalid payload JSON', result['message'])

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    unittest.main()
