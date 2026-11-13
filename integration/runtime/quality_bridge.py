#!/usr/bin/env python3
"""Offline evaluation of externally supplied audit predictions.

Never invokes a model/client, executes a fixture, or certifies client behavior.
The caller puts one predictions.json in each disposable integration workspace
under .integration-test/ after an *independently run* AI audit. Fixture gold
stays outside all client workspaces and is read only for full 12-case scoring.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys

from real_client import SAFE_FIXTURES, assess, inventory
from cli_e2e import verify

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / 'quality/gold/cases.json'
EVALUATOR = ROOT / 'quality/scripts/evaluate.py'
MAX_PREDICTION_BYTES = 2 * 1024 * 1024

def read_predictions(workspace: Path) -> dict:
    """Проверяет происхождение предсказаний, чтобы синтетические примеры не выдавались за реальный клиентский аудит."""
    root = Path(workspace)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('workspace must be a normal directory')
    root = root.resolve(strict = True)
    folder = root / '.integration-test'
    candidate = folder / 'predictions.json'
    if folder.is_symlink() or candidate.is_symlink() or not candidate.is_file():
        raise ValueError('predictions.json missing or symlinked')
    if candidate.stat().st_size > MAX_PREDICTION_BYTES:
        raise ValueError('predictions.json exceeds size limit')
    prediction = json.loads(candidate.read_text('utf-8'))
    if not isinstance(prediction, dict) or not isinstance(prediction.get('case_id'), str):
        raise ValueError('predictions.json requires a case_id string')
    if not isinstance(prediction.get('findings'), list) or not isinstance(prediction.get('recommendations'), list):
        raise ValueError('predictions.json requires findings[] and recommendations[]')
    a = assess(root)
    if a['issues'] or not a['source_unchanged']:
        raise ValueError(f'fixture altered or evidence invalid: {a["issues"]}')
    if prediction['case_id'] != a['fixture']:
        raise ValueError('predicted case_id does not match workspace fixture')
    if a['fixture'] not in SAFE_FIXTURES:
        raise ValueError('unknown fixture')
    # Даже совпавший хеш журнала не доказывает, что состоялся настоящий сеанс AI-клиента.
    logs = verify(root)
    return {'case_id': a['fixture'], 'prediction': prediction,
            'client': a['platform'], 'log_status': logs['status'],
            'source_unchanged': True}

def report(workspaces: list[Path], * , score: bool = False) -> dict:
    """Соотносит результаты клиента с эталонами и считает метрики только при наличии валидированных данных."""
    observed = []
    invalid = []
    by_case = {}
    for path in workspaces:
        try:
            item = read_predictions(path)
            if item['case_id'] in by_case:
                raise ValueError(f'duplicate fixture: {item["case_id"]}')
            by_case[item['case_id']] = item['prediction']
            observed.append({'case_id': item['case_id'], 'client': item['client'],
                             'log_status': item['log_status'],
                             'session_authenticity': 'NOT_VERIFIED'})
        except (ValueError, OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            invalid.append({'input_index': len(observed) + len(invalid) + 1,
                            'reason': f'{type(exc).__name__}: {exc}'})
    missing = sorted(SAFE_FIXTURES - set(by_case))
    status = ('INVALID_INPUT' if invalid else
              'NOT_TESTED' if not by_case else
              'INCOMPLETE' if missing else 'COMPLETE_SUBMISSION_UNVERIFIED')
    result = {
        'status': status, 'submitted_cases': sorted(by_case), 'missing_cases': missing,
        'observations': observed, 'invalid_inputs': invalid,
        'actual_client_execution_confirmed': False, 'client_pass_certified': False,
        'quality_metrics': None,
        'limitations': [
            'Predictions and logs are operator-provided data; provenance is not authenticated.',
            'No AI model or client is executed by this program.',
            'Benchmark scores describe only the 12 synthetic fixtures; they do not certify security or platform compatibility.',
        ],
    }
    if score and not invalid and not missing:
        spec = importlib.util.spec_from_file_location('audit_quality_evaluator', EVALUATOR)
        if spec is None or spec.loader is None:
            raise RuntimeError('Cannot load local evaluator')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        gold = json.loads(GOLD.read_text('utf-8'))
        measurements = module.evaluate(gold, {'cases': list(by_case.values())}, ROOT)
        result['quality_metrics'] = measurements
        result['status'] = 'SCORED_UNVERIFIED_CLIENT_OUTPUT'
    return result

def main(argv = None) -> int:
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--workspace', action = 'append', type = Path, default = [], required = True)
    parser.add_argument('--score', action = 'store_true', help = 'only after all 12 responses have been collected')
    parser.add_argument('--output', type = Path, help = 'optional JSON report; never overwrites existing files')
    args = parser.parse_args(argv)
    try:
        result = report(args.workspace, score = args.score)
        data = json.dumps(result, ensure_ascii = False, indent = 2) + '\n'
        if args.output:
            if args.output.is_symlink() or args.output.exists():
                raise ValueError('output exists or is symlinked; choose a fresh path')
            args.output.parent.mkdir(parents = True, exist_ok = True)
            args.output.write_text(data, 'utf-8')
        print(data, end = '')
        return 2 if result['invalid_inputs'] else 0
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False), file = sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
