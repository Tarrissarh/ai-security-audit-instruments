#!/usr/bin/env python3
"""Offline benchmark evaluator: compares externally produced audit results to fixture gold.

NEVER imports, executes, installs, or runs the target fixture. Standard library only.
Quality of LLM audits is NOT measured unless actual, independently produced predictions
are supplied through --predictions. Gold results must not be exposed to the audited model.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD = ROOT / 'quality' / 'gold' / 'cases.json'
REQUIRED_REC_FIELDS = ('change', 'rationale', 'validation', 'compatibility', 'rollback')
ALLOWED_SEVERITIES = {'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'}

class EvaluationError(ValueError):
    pass

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding = 'utf-8'))
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f'Cannot read JSON {path}: {exc}') from exc

def safe_target(root: Path, relpath: str) -> Path:
    """Read-only target locator; guard traversal and symbolic links."""
    rel = Path(relpath)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise EvaluationError('Unsafe fixture path')
    target = root / rel
    if not target.resolve().is_relative_to(root.resolve()):
        raise EvaluationError('Fixture resolves outside suite')
    # Запрещаем переход по ссылкам из тестовых примеров, чтобы оценщик не вышел за их пределы.
    item = root
    for part in rel.parts:
        item /= part
        if item.is_symlink():
            raise EvaluationError('Fixture symlink is not allowed')
    return target

def validate_gold(gold: dict, root: Path) -> None:
    """Проверяет эталонные находки, их уникальность и привязку к реальным файлам до вычисления метрик."""
    if not isinstance(gold, dict) or not isinstance(gold.get('cases'), list):
        raise EvaluationError('Gold must contain cases[]')
    case_ids = set()
    for case in gold['cases']:
        cid = case.get('case_id')
        if not isinstance(cid, str) or not cid or cid in case_ids:
            raise EvaluationError('Invalid/duplicate gold case id')
        case_ids.add(cid)
        target = safe_target(root, case['target'])
        if not target.is_dir():
            raise EvaluationError(f'Fixture missing: {cid}')
        ids = set()
        for f in case.get('expected_findings', []):
            if f['benchmark_id'] in ids:
                raise EvaluationError(f'Duplicate gold finding: {cid}')
            ids.add(f['benchmark_id'])
            if f['severity'] not in ALLOWED_SEVERITIES:
                raise EvaluationError(f'Unknown severity in {cid}')
            src = safe_target(target, f['file'])
            if not src.is_file() or f['evidence_contains'] not in src.read_text(encoding = 'utf-8'):
                raise EvaluationError(f'Gold evidence not found: {cid}/{f["file"]}')

def validated_evidence(pred: dict, gold: dict, target: Path) -> bool:
    """Учитывает находку только при наличии корректного доказательства из указанного исходного файла."""
    if pred.get('file') != gold['file']:
        return False
    evidence = pred.get('evidence')
    line = pred.get('line')
    if not isinstance(evidence, str) or not evidence.strip() or type(line) is not int or line <= 0:
        return False
    lines = safe_target(target, gold['file']).read_text(encoding = 'utf-8').splitlines()
    if line > len(lines):
        return False
    if evidence.strip() not in lines[line - 1]:
        return False
    return gold['evidence_contains'] in evidence

def ratio(a: int, b: int, * , empty: float = 1.0) -> float:
    return a / b if b else empty

def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0

def evaluate(gold: dict, predictions: dict, root: Path) -> dict:
    """Считает precision, recall, F1 и качество рекомендаций по эталонам, отдельно выделяя неподтверждённые находки."""
    validate_gold(gold, root)
    if not isinstance(predictions, dict) or not isinstance(predictions.get('cases'), list):
        raise EvaluationError('Predictions must contain cases[]')
    pmap = {}
    for case in predictions['cases']:
        cid = case.get('case_id')
        if not isinstance(cid, str) or cid in pmap:
            raise EvaluationError('Duplicate/invalid prediction case_id')
        if not isinstance(case.get('findings'), list) or not isinstance(case.get('recommendations', []), list):
            raise EvaluationError('findings[] / recommendations[] expected')
        pmap[cid] = case
    gold_ids = {c['case_id'] for c in gold['cases']}
    if set(pmap) != gold_ids:
        raise EvaluationError(f'Predictions must include every case exactly once. Missing={sorted(gold_ids - set(pmap))} extra={sorted(set(pmap) - gold_ids)}')

    counts = {'tp': 0, 'fp': 0, 'fn': 0, 'severity_correct': 0, 'severity_wrong': 0,
            'recommendations_valid': 0, 'recommendations_missing': 0, 'recommendations_unsupported': 0}
    per_case = []
    for c in gold['cases']:
        cid = c['case_id']
        gmap = {f['benchmark_id']: f for f in c['expected_findings']}
        p = pmap[cid]
        target = safe_target(root, c['target'])
        matched = set()
        fp = 0
        sp = 0
        sw = 0
        matched_by_prediction = {}
        for i, pred in enumerate(p['findings']):
            if not isinstance(pred, dict):
                fp += 1
                continue
            # Эталонные ID скрыты от аудитора: сопоставление идёт по категории и доказательству, неоднозначности требуют ручной сверки.
            explicit_id = pred.get('benchmark_id')
            candidates = [gmap[explicit_id]] if isinstance(explicit_id, str) and explicit_id in gmap else [
                f for f in gmap.values() if f['category'] == pred.get('category')]
            candidates = [f for f in candidates if f['benchmark_id'] not in matched and
                        validated_evidence(pred, f, target)]
            if len(candidates) != 1:
                fp += 1
                continue
            item = candidates[0]
            fid = item['benchmark_id']
            matched.add(fid)
            pred_key = pred.get('id') if isinstance(pred.get('id'), str) else f'finding-{i + 1}'
            matched_by_prediction[pred_key] = fid
            matched_by_prediction[fid] = fid
            if pred.get('severity') == item['severity']:
                sp += 1
            else:
                sw += 1
        tp = len(matched)
        fn = len(gmap) - tp
        # Рекомендация засчитывается только с доказательством, планом проверки и отката; пользу оценивает человек.
        recognized = set()
        invalid = 0
        for r in p.get('recommendations', []):
            if not isinstance(r, dict):
                invalid += 1
                continue
            refs = r.get('finding_ids')
            linked = [matched_by_prediction.get(x) for x in refs] if isinstance(refs, list) else []
            expected = gmap.get(linked[0]) if len(linked) == 1 else None
            well_formed = (expected is not None and expected['benchmark_id'] in matched and
              expected['benchmark_id'] not in recognized and
              all(isinstance(r.get(k), str) and r[k].strip() for k in REQUIRED_REC_FIELDS)
              and r.get('priority') == expected['priority'])
            if not well_formed:
                invalid += 1
                continue
            recognized.add(expected['benchmark_id'])
        rec_missing = len([f for f in c['expected_findings']
                         if f.get('recommendation_id') and f['benchmark_id'] not in recognized])
        counts['tp'] += tp
        counts['fp'] += fp
        counts['fn'] += fn
        counts['severity_correct'] += sp
        counts['severity_wrong'] += sw
        counts['recommendations_valid'] += len(recognized)
        counts['recommendations_missing'] += rec_missing
        counts['recommendations_unsupported'] += invalid
        cp = ratio(tp, tp + fp)
        cr = ratio(tp, tp + fn)
        per_case.append({'case_id': cid, 'tool_type': c['tool_type'],
            'tp': tp, 'fp': fp, 'fn': fn, 'precision': round(cp, 4), 'recall': round(cr, 4),
            'f1': round(f1(cp, cr), 4), 'severity_correct': sp, 'severity_wrong': sw,
            'missing_finding_ids': sorted(set(gmap) - matched), 'recommendations_valid': len(recognized),
            'recommendations_missing': rec_missing, 'recommendations_unsupported': invalid})
    p = ratio(counts['tp'], counts['tp'] + counts['fp'])
    r = ratio(counts['tp'], counts['tp'] + counts['fn'])
    s = ratio(counts['severity_correct'], counts['tp'], empty = None)
    rp = ratio(counts['recommendations_valid'], counts['recommendations_valid'] + counts['recommendations_unsupported'], empty = None)
    rr = ratio(counts['recommendations_valid'], counts['recommendations_valid'] + counts['recommendations_missing'])
    per_type = {}
    for entry in per_case:
        b = per_type.setdefault(entry['tool_type'], {'cases': 0, 'tp': 0, 'fp': 0, 'fn': 0, 'severity_correct': 0, 'severity_wrong': 0})
        b['cases'] += 1
        for k in ('tp', 'fp', 'fn', 'severity_correct', 'severity_wrong'):
            b[k] += entry[k]
    for b in per_type.values():
        bp = ratio(b['tp'], b['tp'] + b['fp'])
        br = ratio(b['tp'], b['tp'] + b['fn'])
        b['precision'] = round(bp, 4)
        b['recall'] = round(br, 4)
        b['f1'] = round(f1(bp, br), 4)
    return {'benchmark_version': gold['benchmark_version'], 'suite': gold.get('suite'),
        'method': 'offline_category_and_grounded_evidence', 'counts': counts,
        'metrics': {'precision': round(p, 4), 'recall': round(r, 4), 'f1': round(f1(p, r), 4),
                   'severity_accuracy_on_detected': round(s, 4) if s is not None else None,
                   'recommendation_precision': round(rp, 4) if rp is not None else None, 'recommendation_recall': round(rr, 4)},
        'per_type': per_type, 'per_case': per_case,
        'limitations': ['Category and grounded evidence permit automatic fixture matching; optional benchmark_id can be attached post-hoc by a human.',
                       'Exact evidence matching does not prove semantic correctness or coverage of unseen vulnerabilities.',
                       'Recommendation scoring is structural, not a semantic or real-world efficacy assessment.',
                       'This evaluator does not invoke an AI client, a tool, or any fixture code.']}

def main(argv = None):
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--predictions', type = Path, required = True)
    parser.add_argument('--gold', type = Path, default = DEFAULT_GOLD)
    parser.add_argument('--output', type = Path)
    parser.add_argument('--min-f1', type = float, default = None, help = 'optional gate, range 0..1')
    args = parser.parse_args(argv)
    try:
        if args.min_f1 is not None and not 0 <= args.min_f1 <= 1:
            raise EvaluationError('--min-f1 must be 0..1')
        gold = load_json(args.gold)
        pred = load_json(args.predictions)
        result = evaluate(gold, pred, ROOT)
        text = json.dumps(result, ensure_ascii = False, indent = 2) + '\n'
        if args.output:
            args.output.parent.mkdir(parents = True, exist_ok = True)
            args.output.write_text(text, encoding = 'utf-8')
        print(text, end = '')
        return 2 if args.min_f1 is not None and result['metrics']['f1'] < args.min_f1 else 0
    except (KeyError, TypeError, EvaluationError) as exc:
        print(f'EVALUATION_ERROR: {exc}', file = sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
