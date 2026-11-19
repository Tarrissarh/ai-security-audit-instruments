#!/usr/bin/env python3
"""Emit machine-readable audit findings: findings.json + report.sarif.

Reads a findings document (see audit-workflow/schemas/findings.schema.json) and
writes two artifacts next to the human report so CI/Code Scanning can consume them:

  python emit_findings.py --input <findings-document.json> --output-dir <target>/audit

This tool never executes inspected code or downloads anything; it only validates
and rewrites already-collected findings metadata (no secrets — mask before use).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SEVERITY_TO_LEVEL = {
    'CRITICAL': 'error',
    'HIGH': 'error',
    'MEDIUM': 'warning',
    'LOW': 'note',
    'INFO': 'note',
}
SEVERITIES = set(SEVERITY_TO_LEVEL)
CONFIDENCES = {'VERIFIED', 'DOCUMENTED', 'INFERRED', 'UNVERIFIED', 'NOT TESTED', 'NOT APPLICABLE'}
SCHEMA_VERSION = '1.0'

SARIF_SCHEMA_URL = 'https://json.schemastore.org/sarif-2.1.0.json'
TOOL_NAME = 'ai-security-audit-instruments'
TOOL_URI = 'https://github.com/Tarrissarh/ai-security-audit-instruments'


class FindingsError(ValueError):
    pass


def validate_document(doc: dict) -> None:
    """Проверяет форму документа находок без внешних зависимостей."""
    if not isinstance(doc, dict):
        raise FindingsError('findings document must be a JSON object')
    if doc.get('schema_version') != SCHEMA_VERSION:
        raise FindingsError(f"unsupported schema_version {doc.get('schema_version')!r}")
    target = doc.get('target')
    if not isinstance(target, dict) or not target.get('path') or not target.get('type'):
        raise FindingsError('target.path and target.type are required')
    if not doc.get('generated_at'):
        raise FindingsError('generated_at is required')
    if not doc.get('verdict'):
        raise FindingsError('verdict is required')
    findings = doc.get('findings')
    if not isinstance(findings, list):
        raise FindingsError('findings must be an array')
    for finding in findings:
        if not isinstance(finding, dict):
            raise FindingsError('each finding must be an object')
        for field in ('id', 'severity', 'confidence', 'file'):
            if not finding.get(field):
                raise FindingsError(f'finding is missing required field: {field}')
        if finding['severity'] not in SEVERITIES:
            raise FindingsError(f"invalid severity: {finding['severity']!r}")
        if finding['confidence'] not in CONFIDENCES:
            raise FindingsError(f"invalid confidence: {finding['confidence']!r}")
        line = finding.get('line')
        if line is not None and (not isinstance(line, int) or isinstance(line, bool) or line < 1):
            raise FindingsError(f'invalid line for {finding["id"]!r}: {line!r}')


def to_sarif(doc: dict) -> dict:
    """Преобразует документ находок в SARIF 2.1.0."""
    results = []
    for finding in doc['findings']:
        location = {'artifactLocation': {'uri': finding['file']}}
        if finding.get('line'):
            location['region'] = {'startLine': finding['line']}
        message = finding.get('title') or finding['id']
        if finding.get('evidence'):
            message = f"{message} — {finding['evidence']}"
        results.append({
            'ruleId': finding['id'],
            'level': SEVERITY_TO_LEVEL[finding['severity']],
            'message': {'text': message},
            'locations': [{'physicalLocation': location}],
        })
    return {
        'version': '2.1.0',
        '$schema': SARIF_SCHEMA_URL,
        'runs': [{
            'tool': {
                'driver': {
                    'name': TOOL_NAME,
                    'informationUri': TOOL_URI,
                },
            },
            'results': results,
        }],
    }


def emit(input_path: Path, output_dir: Path) -> dict:
    """Читает и проверяет документ, затем пишет findings.json и report.sarif."""
    raw = input_path.read_text(encoding='utf-8-sig')
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise FindingsError(f'invalid JSON: {exc}') from exc
    validate_document(doc)
    output_dir.mkdir(parents=True, exist_ok=True)
    findings_path = output_dir / 'findings.json'
    sarif_path = output_dir / 'report.sarif'
    findings_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sarif_path.write_text(json.dumps(to_sarif(doc), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {
        'status': 'COMPLETE',
        'findings': str(findings_path),
        'sarif': str(sarif_path),
        'count': len(doc['findings']),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True,
                        help='Findings document JSON (see findings.schema.json)')
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='Directory to write findings.json and report.sarif into')
    args = parser.parse_args()
    try:
        result = emit(args.input, args.output_dir)
    except (FindingsError, OSError) as exc:
        print(json.dumps({'status': 'FAILED', 'error': str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
