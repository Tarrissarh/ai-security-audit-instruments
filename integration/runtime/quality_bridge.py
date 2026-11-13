#!/usr/bin/env python3
"""v6.5: offline evaluation of externally supplied audit predictions.

Never invokes a model/client, executes a fixture, or certifies client behavior.
The caller puts one predictions.json in each disposable integration workspace
under .integration-test/ after an *independently run* AI audit. Fixture gold
stays outside all client workspaces and is read only for full 12-case scoring.
"""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations
# Импортирует модуль или имена, используемые в этом файле.
import argparse
# Импортирует модуль или имена, используемые в этом файле.
import importlib.util
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import sys

# Импортирует модуль или имена, используемые в этом файле.
from real_client import SAFE_FIXTURES, assess, inventory
# Импортирует модуль или имена, используемые в этом файле.
from cli_e2e import verify

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[2]
# Сохраняет или обновляет вычисленное значение для последующих операций.
GOLD = ROOT / 'quality/gold/cases.json'
# Сохраняет или обновляет вычисленное значение для последующих операций.
EVALUATOR = ROOT / 'quality/scripts/evaluate.py'
# Сохраняет или обновляет вычисленное значение для последующих операций.
MAX_PREDICTION_BYTES = 2 * 1024 * 1024


# Объявляет функцию read_predictions и её параметры.
def read_predictions(workspace: Path) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = Path(workspace)
    # Проверяет условие перед выполнением следующего блока.
    if root.is_symlink() or not root.is_dir():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('workspace must be a normal directory')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = root.resolve(strict = True)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    folder = root / '.integration-test'
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    candidate = folder / 'predictions.json'
    # Проверяет условие перед выполнением следующего блока.
    if folder.is_symlink() or candidate.is_symlink() or not candidate.is_file():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('predictions.json missing or symlinked')
    # Проверяет условие перед выполнением следующего блока.
    if candidate.stat().st_size > MAX_PREDICTION_BYTES:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('predictions.json exceeds size limit')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    prediction = json.loads(candidate.read_text('utf-8'))
    # Проверяет условие перед выполнением следующего блока.
    if not isinstance(prediction, dict) or not isinstance(prediction.get('case_id'), str):
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('predictions.json requires a case_id string')
    # Проверяет условие перед выполнением следующего блока.
    if not isinstance(prediction.get('findings'), list) or not isinstance(prediction.get('recommendations'), list):
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('predictions.json requires findings[] and recommendations[]')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    a = assess(root)
    # Проверяет условие перед выполнением следующего блока.
    if a['issues'] or not a['source_unchanged']:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError(f'fixture altered or evidence invalid: {a["issues"]}')
    # Проверяет условие перед выполнением следующего блока.
    if prediction['case_id'] != a['fixture']:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('predicted case_id does not match workspace fixture')
    # Проверяет условие перед выполнением следующего блока.
    if a['fixture'] not in SAFE_FIXTURES:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('unknown fixture')
    # The log check is informational only. A valid hash cannot establish a real AI session.
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    logs = verify(root)
    # Возвращает вычисленный результат вызывающему коду.
    return {'case_id': a['fixture'], 'prediction': prediction,
            # Устанавливает поле client в словаре или описании.
            'client': a['platform'], 'log_status': logs['status'],
            # Устанавливает поле source_unchanged в словаре или описании.
            'source_unchanged': True}


# Объявляет функцию report и её параметры.
def report(workspaces: list[Path], * , score: bool = False) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    observed = []
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    invalid = []
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    by_case = {}
    # Перебирает элементы набора для последовательной обработки.
    for path in workspaces:
        # Начинает блок с контролируемой обработкой исключений.
        try:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            item = read_predictions(path)
            # Проверяет условие перед выполнением следующего блока.
            if item['case_id'] in by_case:
                # Прерывает операцию с диагностическим исключением.
                raise ValueError(f'duplicate fixture: {item["case_id"]}')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            by_case[item['case_id']] = item['prediction']
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            observed.append({'case_id': item['case_id'], 'client': item['client'],
                             # Устанавливает поле log_status в словаре или описании.
                             'log_status': item['log_status'],
                             # Устанавливает поле session_authenticity в словаре или описании.
                             'session_authenticity': 'NOT_VERIFIED'})
        # Перехватывает указанное исключение для безопасной обработки.
        except (ValueError, OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            invalid.append({'input_index': len(observed) + len(invalid) + 1,
                            # Устанавливает поле reason в словаре или описании.
                            'reason': f'{type(exc).__name__}: {exc}'})
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    missing = sorted(SAFE_FIXTURES - set(by_case))
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    status = ('INVALID_INPUT' if invalid else
              # Формирует часть выражения или передаёт аргумент в текущую операцию.
              'NOT_TESTED' if not by_case else
              # Формирует часть выражения или передаёт аргумент в текущую операцию.
              'INCOMPLETE' if missing else 'COMPLETE_SUBMISSION_UNVERIFIED')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    result = {
        # Устанавливает поле status в словаре или описании.
        'status': status, 'submitted_cases': sorted(by_case), 'missing_cases': missing,
        # Устанавливает поле observations в словаре или описании.
        'observations': observed, 'invalid_inputs': invalid,
        # Устанавливает поле actual_client_execution_confirmed в словаре или описании.
        'actual_client_execution_confirmed': False, 'client_pass_certified': False,
        # Устанавливает поле quality_metrics в словаре или описании.
        'quality_metrics': None,
        # Устанавливает поле limitations в словаре или описании.
        'limitations': [
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            'Predictions and logs are operator-provided data; provenance is not authenticated.',
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            'No AI model or client is executed by this program.',
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            'Benchmark scores describe only the 12 synthetic fixtures; they do not certify security or platform compatibility.',
        ],
    }
    # Проверяет условие перед выполнением следующего блока.
    if score and not invalid and not missing:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        spec = importlib.util.spec_from_file_location('audit_quality_evaluator_v65', EVALUATOR)
        # Проверяет условие перед выполнением следующего блока.
        if spec is None or spec.loader is None:
            # Прерывает операцию с диагностическим исключением.
            raise RuntimeError('Cannot load local evaluator')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        module = importlib.util.module_from_spec(spec)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        spec.loader.exec_module(module)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        gold = json.loads(GOLD.read_text('utf-8'))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        measurements = module.evaluate(gold, {'cases': list(by_case.values())}, ROOT)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        result['quality_metrics'] = measurements
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        result['status'] = 'SCORED_UNVERIFIED_CLIENT_OUTPUT'
    # Возвращает вычисленный результат вызывающему коду.
    return result


# Объявляет функцию main и её параметры.
def main(argv = None) -> int:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    parser = argparse.ArgumentParser(description = __doc__)
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--workspace', action = 'append', type = Path, default = [], required = True)
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--score', action = 'store_true', help = 'only after all 12 responses have been collected')
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--output', type = Path, help = 'optional JSON report; never overwrites existing files')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args = parser.parse_args(argv)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = report(args.workspace, score = args.score)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        data = json.dumps(result, ensure_ascii = False, indent = 2) + '\n'
        # Проверяет условие перед выполнением следующего блока.
        if args.output:
            # Проверяет условие перед выполнением следующего блока.
            if args.output.is_symlink() or args.output.exists():
                # Прерывает операцию с диагностическим исключением.
                raise ValueError('output exists or is symlinked; choose a fresh path')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            args.output.parent.mkdir(parents = True, exist_ok = True)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            args.output.write_text(data, 'utf-8')
        # Выводит диагностическую информацию о результате выполнения.
        print(data, end = '')
        # Возвращает вычисленный результат вызывающему коду.
        return 2 if result['invalid_inputs'] else 0
    # Перехватывает указанное исключение для безопасной обработки.
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False), file = sys.stderr)
        # Возвращает вычисленный результат вызывающему коду.
        return 1

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit(main())
