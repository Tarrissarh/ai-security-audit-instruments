#!/usr/bin/env python3
"""Offline benchmark evaluator: compares externally produced audit results to fixture gold.

NEVER imports, executes, installs, or runs the target fixture. Standard library only.
Quality of LLM audits is NOT measured unless actual, independently produced predictions
are supplied through --predictions. Gold results must not be exposed to the audited model.
"""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations
# Импортирует модуль или имена, используемые в этом файле.
import argparse
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[2]
# Сохраняет или обновляет вычисленное значение для последующих операций.
DEFAULT_GOLD = ROOT / 'quality' / 'gold' / 'cases.json'
# Сохраняет или обновляет вычисленное значение для последующих операций.
REQUIRED_REC_FIELDS = ('change', 'rationale', 'validation', 'compatibility', 'rollback')
# Сохраняет или обновляет вычисленное значение для последующих операций.
ALLOWED_SEVERITIES = {'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'}

# Определяет класс и его интерфейс.
class EvaluationError(ValueError):
    # Оставляет тело блока пустым намеренно.
    pass


# Объявляет функцию load_json и её параметры.
def load_json(path: Path):
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Возвращает вычисленный результат вызывающему коду.
        return json.loads(path.read_text(encoding = 'utf-8'))
    # Перехватывает указанное исключение для безопасной обработки.
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        # Прерывает операцию с диагностическим исключением.
        raise EvaluationError(f'Cannot read JSON {path}: {exc}') from exc


# Объявляет функцию safe_target и её параметры.
def safe_target(root: Path, relpath: str) -> Path:
    # Описывает назначение блока в многострочной строке документации.
    """Read-only target locator; guard traversal and symbolic links."""
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    rel = Path(relpath)
    # Проверяет условие перед выполнением следующего блока.
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        # Прерывает операцию с диагностическим исключением.
        raise EvaluationError('Unsafe fixture path')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    target = root / rel
    # Проверяет условие перед выполнением следующего блока.
    if not target.resolve().is_relative_to(root.resolve()):
        # Прерывает операцию с диагностическим исключением.
        raise EvaluationError('Fixture resolves outside suite')
    # Avoid traversing symlinked fixture content.
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    item = root
    # Перебирает элементы набора для последовательной обработки.
    for part in rel.parts:
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        item /= part
        # Проверяет условие перед выполнением следующего блока.
        if item.is_symlink():
            # Прерывает операцию с диагностическим исключением.
            raise EvaluationError('Fixture symlink is not allowed')
    # Возвращает вычисленный результат вызывающему коду.
    return target


# Объявляет функцию validate_gold и её параметры.
def validate_gold(gold: dict, root: Path) -> None:
    # Проверяет условие перед выполнением следующего блока.
    if not isinstance(gold, dict) or not isinstance(gold.get('cases'), list):
        # Прерывает операцию с диагностическим исключением.
        raise EvaluationError('Gold must contain cases[]')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    case_ids = set()
    # Перебирает элементы набора для последовательной обработки.
    for case in gold['cases']:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cid = case.get('case_id')
        # Проверяет условие перед выполнением следующего блока.
        if not isinstance(cid, str) or not cid or cid in case_ids:
            # Прерывает операцию с диагностическим исключением.
            raise EvaluationError('Invalid/duplicate gold case id')
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        case_ids.add(cid)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        target = safe_target(root, case['target'])
        # Проверяет условие перед выполнением следующего блока.
        if not target.is_dir():
            # Прерывает операцию с диагностическим исключением.
            raise EvaluationError(f'Fixture missing: {cid}')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        ids = set()
        # Перебирает элементы набора для последовательной обработки.
        for f in case.get('expected_findings', []):
            # Проверяет условие перед выполнением следующего блока.
            if f['benchmark_id'] in ids:
                # Прерывает операцию с диагностическим исключением.
                raise EvaluationError(f'Duplicate gold finding: {cid}')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            ids.add(f['benchmark_id'])
            # Проверяет условие перед выполнением следующего блока.
            if f['severity'] not in ALLOWED_SEVERITIES:
                # Прерывает операцию с диагностическим исключением.
                raise EvaluationError(f'Unknown severity in {cid}')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            src = safe_target(target, f['file'])
            # Проверяет условие перед выполнением следующего блока.
            if not src.is_file() or f['evidence_contains'] not in src.read_text(encoding = 'utf-8'):
                # Прерывает операцию с диагностическим исключением.
                raise EvaluationError(f'Gold evidence not found: {cid}/{f["file"]}')


# Объявляет функцию validated_evidence и её параметры.
def validated_evidence(pred: dict, gold: dict, target: Path) -> bool:
    # Проверяет условие перед выполнением следующего блока.
    if pred.get('file') != gold['file']:
        # Возвращает вычисленный результат вызывающему коду.
        return False
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    evidence = pred.get('evidence')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    line = pred.get('line')
    # Проверяет условие перед выполнением следующего блока.
    if not isinstance(evidence, str) or not evidence.strip() or type(line) is not int or line <= 0:
        # Возвращает вычисленный результат вызывающему коду.
        return False
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    lines = safe_target(target, gold['file']).read_text(encoding = 'utf-8').splitlines()
    # Проверяет условие перед выполнением следующего блока.
    if line > len(lines):
        # Возвращает вычисленный результат вызывающему коду.
        return False
    # Проверяет условие перед выполнением следующего блока.
    if evidence.strip() not in lines[line - 1]:
        # Возвращает вычисленный результат вызывающему коду.
        return False
    # Возвращает вычисленный результат вызывающему коду.
    return gold['evidence_contains'] in evidence


# Объявляет функцию ratio и её параметры.
def ratio(a: int, b: int, * , empty: float = 1.0) -> float:
    # Возвращает вычисленный результат вызывающему коду.
    return a / b if b else empty


# Объявляет функцию f1 и её параметры.
def f1(p: float, r: float) -> float:
    # Возвращает вычисленный результат вызывающему коду.
    return 2 * p * r / (p + r) if p + r else 0.0


# Объявляет функцию evaluate и её параметры.
def evaluate(gold: dict, predictions: dict, root: Path) -> dict:
    # Вызывает функцию для выполнения операции.
    validate_gold(gold, root)
    # Проверяет условие перед выполнением следующего блока.
    if not isinstance(predictions, dict) or not isinstance(predictions.get('cases'), list):
        # Прерывает операцию с диагностическим исключением.
        raise EvaluationError('Predictions must contain cases[]')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    pmap = {}
    # Перебирает элементы набора для последовательной обработки.
    for case in predictions['cases']:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cid = case.get('case_id')
        # Проверяет условие перед выполнением следующего блока.
        if not isinstance(cid, str) or cid in pmap:
            # Прерывает операцию с диагностическим исключением.
            raise EvaluationError('Duplicate/invalid prediction case_id')
        # Проверяет условие перед выполнением следующего блока.
        if not isinstance(case.get('findings'), list) or not isinstance(case.get('recommendations', []), list):
            # Прерывает операцию с диагностическим исключением.
            raise EvaluationError('findings[] / recommendations[] expected')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        pmap[cid] = case
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    gold_ids = {c['case_id'] for c in gold['cases']}
    # Проверяет условие перед выполнением следующего блока.
    if set(pmap) != gold_ids:
        # Прерывает операцию с диагностическим исключением.
        raise EvaluationError(f'Predictions must include every case exactly once. Missing={sorted(gold_ids - set(pmap))} extra={sorted(set(pmap) - gold_ids)}')

    # Сохраняет или обновляет вычисленное значение для последующих операций.
    counts = {'tp': 0, 'fp': 0, 'fn': 0, 'severity_correct': 0, 'severity_wrong': 0,
            # Устанавливает поле recommendations_valid в словаре или описании.
            'recommendations_valid': 0, 'recommendations_missing': 0, 'recommendations_unsupported': 0}
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    per_case = []
    # Перебирает элементы набора для последовательной обработки.
    for c in gold['cases']:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cid = c['case_id']
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        gmap = {f['benchmark_id']: f for f in c['expected_findings']}
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = pmap[cid]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        target = safe_target(root, c['target'])
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        matched = set()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fp = 0
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        sp = 0
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        sw = 0
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        matched_by_prediction = {}
        # Перебирает элементы набора для последовательной обработки.
        for i, pred in enumerate(p['findings']):
            # Проверяет условие перед выполнением следующего блока.
            if not isinstance(pred, dict):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                fp += 1
                # Переходит к следующей итерации цикла.
                continue
            # The auditee receives NO gold IDs. Label matching is inferred from
            # a declared category and verified evidence, with optional human
            # post-hoc benchmark_id label for ambiguous cases.
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            explicit_id = pred.get('benchmark_id')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            candidates = [gmap[explicit_id]] if isinstance(explicit_id, str) and explicit_id in gmap else [
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                f for f in gmap.values() if f['category'] == pred.get('category')]
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            candidates = [f for f in candidates if f['benchmark_id'] not in matched and
                        # Вызывает функцию для выполнения операции.
                        validated_evidence(pred, f, target)]
            # Проверяет условие перед выполнением следующего блока.
            if len(candidates) != 1:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                fp += 1
                # Переходит к следующей итерации цикла.
                continue
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            item = candidates[0]
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            fid = item['benchmark_id']
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            matched.add(fid)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            pred_key = pred.get('id') if isinstance(pred.get('id'), str) else f'finding-{i + 1}'
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            matched_by_prediction[pred_key] = fid
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            matched_by_prediction[fid] = fid
            # Проверяет условие перед выполнением следующего блока.
            if pred.get('severity') == item['severity']:
                # Учитывает корректную классификацию критичности.
                sp += 1
            # Выполняет ветку, когда предыдущие условия не сработали.
            else:
                # Учитывает ошибочную классификацию критичности.
                sw += 1
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        tp = len(matched)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fn = len(gmap) - tp
        # Each expected actionable recommendation requires its own explicit evidence-backed proposal.
        # Structural recommendation score: an evidence-backed, single-finding
        # proposal with a test plan and rollback. Technical merit still needs
        # human evaluation; text fields are not semantically judged.
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        recognized = set()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        invalid = 0
        # Перебирает элементы набора для последовательной обработки.
        for r in p.get('recommendations', []):
            # Проверяет условие перед выполнением следующего блока.
            if not isinstance(r, dict):
                # Учитывает некорректную рекомендацию.
                invalid += 1
                # Пропускает элемент, не соответствующий структуре рекомендации.
                continue
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            refs = r.get('finding_ids')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            linked = [matched_by_prediction.get(x) for x in refs] if isinstance(refs, list) else []
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            expected = gmap.get(linked[0]) if len(linked) == 1 else None
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            well_formed = (expected is not None and expected['benchmark_id'] in matched and
              # Формирует часть выражения или передаёт аргумент в текущую операцию.
              expected['benchmark_id'] not in recognized and
              # Вызывает функцию для выполнения операции.
              all(isinstance(r.get(k), str) and r[k].strip() for k in REQUIRED_REC_FIELDS)
              # Формирует часть выражения или передаёт аргумент в текущую операцию.
              and r.get('priority') == expected['priority'])
            # Проверяет условие перед выполнением следующего блока.
            if not well_formed:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                invalid += 1
                # Переходит к следующей итерации цикла.
                continue
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            recognized.add(expected['benchmark_id'])
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        rec_missing = len([f for f in c['expected_findings']
                         # Проверяет условие перед выполнением следующего блока.
                         if f.get('recommendation_id') and f['benchmark_id'] not in recognized])
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        counts['tp'] += tp
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        counts['fp'] += fp
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        counts['fn'] += fn
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        counts['severity_correct'] += sp
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        counts['severity_wrong'] += sw
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        counts['recommendations_valid'] += len(recognized)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        counts['recommendations_missing'] += rec_missing
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        counts['recommendations_unsupported'] += invalid
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cp = ratio(tp, tp + fp)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cr = ratio(tp, tp + fn)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        per_case.append({'case_id': cid, 'tool_type': c['tool_type'],
            # Устанавливает поле tp в словаре или описании.
            'tp': tp, 'fp': fp, 'fn': fn, 'precision': round(cp, 4), 'recall': round(cr, 4),
            # Устанавливает поле f1 в словаре или описании.
            'f1': round(f1(cp, cr), 4), 'severity_correct': sp, 'severity_wrong': sw,
            # Устанавливает поле missing_finding_ids в словаре или описании.
            'missing_finding_ids': sorted(set(gmap) - matched), 'recommendations_valid': len(recognized),
            # Устанавливает поле recommendations_missing в словаре или описании.
            'recommendations_missing': rec_missing, 'recommendations_unsupported': invalid})
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    p = ratio(counts['tp'], counts['tp'] + counts['fp'])
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    r = ratio(counts['tp'], counts['tp'] + counts['fn'])
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    s = ratio(counts['severity_correct'], counts['tp'], empty = None)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    rp = ratio(counts['recommendations_valid'], counts['recommendations_valid'] + counts['recommendations_unsupported'], empty = None)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    rr = ratio(counts['recommendations_valid'], counts['recommendations_valid'] + counts['recommendations_missing'])
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    per_type = {}
    # Перебирает элементы набора для последовательной обработки.
    for entry in per_case:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        b = per_type.setdefault(entry['tool_type'], {'cases': 0, 'tp': 0, 'fp': 0, 'fn': 0, 'severity_correct': 0, 'severity_wrong': 0})
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        b['cases'] += 1
        # Перебирает элементы набора для последовательной обработки.
        for k in ('tp', 'fp', 'fn', 'severity_correct', 'severity_wrong'):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            b[k] += entry[k]
    # Перебирает элементы набора для последовательной обработки.
    for b in per_type.values():
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        bp = ratio(b['tp'], b['tp'] + b['fp'])
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        br = ratio(b['tp'], b['tp'] + b['fn'])
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        b['precision'] = round(bp, 4)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        b['recall'] = round(br, 4)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        b['f1'] = round(f1(bp, br), 4)
    # Возвращает вычисленный результат вызывающему коду.
    return {'benchmark_version': gold['benchmark_version'], 'suite': gold.get('suite'),
        # Устанавливает поле method в словаре или описании.
        'method': 'offline_category_and_grounded_evidence', 'counts': counts,
        # Устанавливает поле metrics в словаре или описании.
        'metrics': {'precision': round(p, 4), 'recall': round(r, 4), 'f1': round(f1(p, r), 4),
                   # Устанавливает поле severity_accuracy_on_detected в словаре или описании.
                   'severity_accuracy_on_detected': round(s, 4) if s is not None else None,
                   # Устанавливает поле recommendation_precision в словаре или описании.
                   'recommendation_precision': round(rp, 4) if rp is not None else None, 'recommendation_recall': round(rr, 4)},
        # Устанавливает поле per_type в словаре или описании.
        'per_type': per_type, 'per_case': per_case,
        # Устанавливает поле limitations в словаре или описании.
        'limitations': ['Category and grounded evidence permit automatic fixture matching; optional benchmark_id can be attached post-hoc by a human.',
                       # Формирует часть выражения или передаёт аргумент в текущую операцию.
                       'Exact evidence matching does not prove semantic correctness or coverage of unseen vulnerabilities.',
                       # Формирует часть выражения или передаёт аргумент в текущую операцию.
                       'Recommendation scoring is structural, not a semantic or real-world efficacy assessment.',
                       # Формирует часть выражения или передаёт аргумент в текущую операцию.
                       'This evaluator does not invoke an AI client, a tool, or any fixture code.']}


# Объявляет функцию main и её параметры.
def main(argv = None):
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    parser = argparse.ArgumentParser(description = __doc__)
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--predictions', type = Path, required = True)
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--gold', type = Path, default = DEFAULT_GOLD)
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--output', type = Path)
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--min-f1', type = float, default = None, help = 'optional gate, range 0..1')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args = parser.parse_args(argv)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Проверяет условие перед выполнением следующего блока.
        if args.min_f1 is not None and not 0 <= args.min_f1 <= 1:
            # Прерывает операцию с диагностическим исключением.
            raise EvaluationError('--min-f1 must be 0..1')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        gold = load_json(args.gold)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        pred = load_json(args.predictions)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = evaluate(gold, pred, ROOT)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        text = json.dumps(result, ensure_ascii = False, indent = 2) + '\n'
        # Проверяет условие перед выполнением следующего блока.
        if args.output:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            args.output.parent.mkdir(parents = True, exist_ok = True)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            args.output.write_text(text, encoding = 'utf-8')
        # Выводит диагностическую информацию о результате выполнения.
        print(text, end = '')
        # Возвращает вычисленный результат вызывающему коду.
        return 2 if args.min_f1 is not None and result['metrics']['f1'] < args.min_f1 else 0
    # Перехватывает указанное исключение для безопасной обработки.
    except (KeyError, TypeError, EvaluationError) as exc:
        # Выводит диагностическую информацию о результате выполнения.
        print(f'EVALUATION_ERROR: {exc}', file = sys.stderr)
        # Возвращает вычисленный результат вызывающему коду.
        return 1

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    sys.exit(main())
