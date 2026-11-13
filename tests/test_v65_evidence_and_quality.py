# Описывает назначение блока в многострочной строке документации.
"""v6.5 fixture-only tests; fake outputs are never labeled real client runs."""
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
import unittest
# Импортирует модуль или имена, используемые в этом файле.
from zipfile import ZipFile

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(ROOT / 'integration/runtime'))
# Импортирует модуль или имена, используемые в этом файле.
import real_client  # noqa
# Импортирует модуль или имена, используемые в этом файле.
import quality_bridge  # noqa
# Импортирует модуль или имена, используемые в этом файле.
import evidence_export  # noqa


# Определяет класс и его интерфейс.
class V65FixtureTests(unittest.TestCase):
    # Объявляет функцию setUp и её параметры.
    def setUp(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.tmp = tempfile.TemporaryDirectory()
        # Вызывает проверку или метод текущего объекта.
        self.addCleanup(self.tmp.cleanup)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.parent = Path(self.tmp.name)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.created = []

    # Объявляет функцию prep и её параметры.
    def prep(self, case = 'skill-clean', platform = 'codex', prediction = None):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        folder = self.parent / f'sandbox-{len(self.created)}'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        folder.mkdir()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        real_client.prepare(platform, folder, case)
        # Проверяет условие перед выполнением следующего блока.
        if prediction is not None:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (folder / '.integration-test/predictions.json').write_text(
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                json.dumps(prediction, ensure_ascii = False), encoding = 'utf-8')
        # Вызывает проверку или метод текущего объекта.
        self.created.append(folder)
        # Возвращает вычисленный результат вызывающему коду.
        return folder

    # Объявляет функцию prediction и её параметры.
    def prediction(self, cid):
        # Возвращает вычисленный результат вызывающему коду.
        return {'case_id': cid, 'findings': [], 'recommendations': []}

    # Объявляет функцию test_prediction_missing_returns_invalid_not_zero и её параметры.
    def test_prediction_missing_returns_invalid_not_zero(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = quality_bridge.report([self.prep()])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['status'], 'INVALID_INPUT')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(r['client_pass_certified'])

    # Объявляет функцию test_single_prediction_is_incomplete и её параметры.
    def test_single_prediction_is_incomplete(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.prep(prediction = self.prediction('skill-clean'))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = quality_bridge.report([p])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['status'], 'INCOMPLETE')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('skill-issues', r['missing_cases'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIsNone(r['quality_metrics'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(r['actual_client_execution_confirmed'])

    # Объявляет функцию test_mismatched_case_rejected и её параметры.
    def test_mismatched_case_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.prep(prediction = self.prediction('skill-issues'))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = quality_bridge.report([p])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['status'], 'INVALID_INPUT')

    # Объявляет функцию test_duplicate_case_rejected и её параметры.
    def test_duplicate_case_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p1 = self.prep(prediction = self.prediction('skill-clean'))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p2 = self.prep(prediction = self.prediction('skill-clean'))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = quality_bridge.report([p1, p2])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['status'], 'INVALID_INPUT')

    # Объявляет функцию test_changed_source_rejected и её параметры.
    def test_changed_source_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.prep(prediction = self.prediction('skill-clean'))
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (p / 'subject/SKILL.md').write_text('tampered', encoding = 'utf-8')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = quality_bridge.report([p])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['status'], 'INVALID_INPUT')

    # Объявляет функцию test_symlinked_prediction_rejected и её параметры.
    def test_symlinked_prediction_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.prep()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        external = self.parent / 'outside.json'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        external.write_text(json.dumps(self.prediction('skill-clean')))
        # Начинает блок с контролируемой обработкой исключений.
        try:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / '.integration-test/predictions.json').symlink_to(external)
        # Перехватывает указанное исключение для безопасной обработки.
        except (OSError, NotImplementedError):
            # Вызывает проверку или метод текущего объекта.
            self.skipTest('symlinks unsupported')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = quality_bridge.report([p])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['status'], 'INVALID_INPUT')

    # Объявляет функцию test_all_twelve_synthetic_scores_but_not_client_pass и её параметры.
    def test_all_twelve_synthetic_scores_but_not_client_pass(self):
        # Built-in 'perfect' data is intentionally synthetic; test evaluator only.
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        perfect = json.loads((ROOT / 'quality/examples/predictions-perfect.json').read_text('utf-8'))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        paths = []
        # Перебирает элементы набора для последовательной обработки.
        for case in perfect['cases']:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            paths.append(self.prep(case['case_id'], prediction = case))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = quality_bridge.report(paths, score = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['status'], 'SCORED_UNVERIFIED_CLIENT_OUTPUT')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['quality_metrics']['metrics']['f1'], 1)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['client_pass_certified'])

    # Объявляет функцию test_export_summary_only_no_private_workspace_path и её параметры.
    def test_export_summary_only_no_private_workspace_path(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.prep()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        z = self.parent / 'export.zip'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = evidence_export.export([p], z)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['status'], 'EXPORTED_UNVERIFIED_EVIDENCE')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with ZipFile(z) as f:
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(sorted(f.namelist()), ['README.txt', 'SUMMARY.json'])
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            s = f.read('SUMMARY.json').decode()
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertNotIn(str(self.parent), s)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse(json.loads(s)['client_pass_certified'])

    # Объявляет функцию test_export_does_not_overwrite и её параметры.
    def test_export_does_not_overwrite(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.prep()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        z = self.parent / 'export.zip'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        evidence_export.export([p], z)
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaises(ValueError):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            evidence_export.export([p], z)

    # Объявляет функцию test_logs_require_separate_privacy_acknowledgement и её параметры.
    def test_logs_require_separate_privacy_acknowledgement(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.prep()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaises(ValueError):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            evidence_export.export([p], self.parent / 'evidence.zip', include_logs = True)

    # Объявляет функцию test_untracked_logs_not_exported и её параметры.
    def test_untracked_logs_not_exported(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.prep()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        d = p / '.integration-test/client-runs'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        d.mkdir(parents = True)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (d / 'untracked.stdout.txt').write_text('PRIVATE TEST TEXT')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        z = self.parent / 'evidence.zip'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        evidence_export.export([p], z, include_logs = True, privacy_reviewed = True)
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with ZipFile(z) as f:
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(sorted(f.namelist()), ['README.txt', 'SUMMARY.json'])


# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    unittest.main()
