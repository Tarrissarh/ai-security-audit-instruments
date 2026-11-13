#!/usr/bin/env python3
"""Safe external-client test preparation and evidence validation.

No AI client is ever launched by this utility. Its status cannot certify actual
Skill loading: client observations require a real session and human review.
Never executes code inside a fixture; never downloads or installs packages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

BUNDLE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUNDLE / 'scripts'))
from platform_compat import IDS, PLATFORMS, inspect, stage  # noqa: E402

CLIENT_BINS = {
    'opencode': ('opencode',),
    'deepseek-harness': ('dsh',),
    'claude-code': ('claude',),
    'codex': ('codex',),
    'cursor': ('agent', 'cursor-agent'),
}
CHECKS = (
    'discovery', 'activation', 'reference_loading', 'orchestration',
    'reports', 'no_unauthorized_change', 'generator_consent', 'quality',
)
STATUS = {'NOT_TESTED', 'BLOCKED', 'FAIL', 'PASS'}
SAFE_FIXTURES = {
    'skill-clean', 'skill-issues', 'agent-clean', 'agent-issues',
    'command-clean', 'command-issues', 'mcp-clean', 'mcp-issues',
    'lsp-clean', 'lsp-issues', 'hooks-clean', 'hooks-issues',
}

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def inventory(root: Path) -> dict[str, str]:
    """Only regular, local files; symlinked fixture content is rejected."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError('subject must be a normal directory')
    data = {}
    for p in sorted(root.rglob('*')):
        # Проверяем ссылки до исключения отчётов: audit/ не должен позволять выход за границы проекта.
        if p.is_symlink():
            raise ValueError(f'symlink forbidden in fixture: {p}')
        # Некоторые клиенты сохраняют результаты аудита непосредственно внутри исследуемого инструмента.
        if p.relative_to(root).parts[0] == 'audit':
            continue
        if p.is_file():
            data[p.relative_to(root).as_posix()] = file_hash(p)
    return data

def probe() -> dict:
    """Определяет наличие внешних CLI, не интерпретируя это как доказательство загрузки Skills."""
    result = {}
    for platform, names in CLIENT_BINS.items():
        matches = [{'binary': name, 'path': shutil.which(name)} for name in names]
        found = [m for m in matches if m['path']]
        result[platform] = {
            'binary_candidates': matches,
            'cli_present': bool(found),
            'client_version': 'NOT_VERIFIED',
            'actual_skill_discovery': 'NOT_TESTED',
            'actual_skill_execution': 'NOT_TESTED',
            'note': 'Presence on PATH is not proof of active client or correct identity.',
        }
    return {'checked_at': datetime.now(timezone.utc).isoformat(), 'clients': result,
            'client_commands_executed': 0}

def _empty_workspace(path: Path) -> Path:
    # Не разрешаем предоставленную пользователем ссылку в путь за пределами тестового проекта.
    if path.is_symlink() or not path.exists() or not path.is_dir():
        raise ValueError('workspace must be an existing regular directory')
    root = path.resolve()
    if any(root.iterdir()):
        raise ValueError('workspace must be empty; use a new disposable directory')
    return root

def prepare(platform: str, workspace: Path, fixture: str) -> dict:
    """Создаёт изолированный проект с безопасной фикстурой и копиями Skills без обращения к моделям."""
    if platform not in PLATFORMS or fixture not in SAFE_FIXTURES:
        raise ValueError('invalid platform or fixture')
    root = _empty_workspace(workspace)
    source = BUNDLE / 'quality' / 'fixtures' / fixture
    inventory(source)  # Reject fixture symlinks and unreadable sources.
    (root / '.git').mkdir()
    dest = root / 'subject'
    shutil.copytree(source, dest)
    state = root / '.integration-test'
    state.mkdir(mode = 0o700)
    manifest = {
        'schema_version': '1.0', 'platform': platform, 'fixture': fixture,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'original_files': inventory(dest),
        'ai_client_executed_by_prepare': False,
    }
    (state / 'baseline.json').write_text(json.dumps(manifest, indent = 2, ensure_ascii = False) + '\n', encoding = 'utf-8')
    evidence = {
        'platform': platform, 'client_version': None,
        'checked_at': None, 'fixture': fixture,
        'checks': {k: {'status': 'NOT_TESTED', 'evidence_files': [], 'notes': ''} for k in CHECKS},
        'constraints': ['Use only synthetic fixture; do not execute audited code',
                        'Inspect client session logs independently before claiming PASS',
                        'No automatic ai-tool-generator invocation'],
    }
    (state / 'evidence.json').write_text(json.dumps(evidence, indent = 2, ensure_ascii = False) + '\n', encoding = 'utf-8')
    staged = stage(platform, root, apply = True)
    if staged['status'] != 'LOCAL_INSTALL_PASS':
        raise ValueError('local skill installation failed: ' + str(staged.get('errors')))
    snapshot = inspect(platform, root)
    return {'status': 'READY_FOR_MANUAL_CLIENT_TEST', 'platform': platform,
            'fixture': fixture, 'workspace': str(root),
            'installed_skill_count': len(snapshot['found']),
            'local_discovery': snapshot['local_discovery_static'],
            'real_client_discovery': 'NOT_TESTED',
            'real_client_activation': 'NOT_TESTED',
            'client_executed': False,
            'evidence_template': str(state / 'evidence.json')}

def _load_json(path: Path):
    return json.loads(path.read_text(encoding = 'utf-8'))

def _evidence_file(root: Path, relative: str) -> Path:
    """Проверяет границы и тип файла свидетельства, запрещая чтение внешних путей через ссылки."""
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('evidence path must be a nonempty relative path')
    parts = Path(relative).parts
    if '..' in parts or '.' in parts:
        raise ValueError('evidence path escapes workspace')
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('evidence symlink forbidden')
    if not current.is_relative_to(root):
        raise ValueError('invalid evidence path')
    return current

def assess(workspace: Path) -> dict:
    """Сопоставляет записи запуска с фактическими файлами и контрольными суммами; не выдаёт локальный журнал за подтверждённый E2E."""
    if workspace.is_symlink() or not workspace.is_dir():
        raise ValueError('workspace must be a normal directory')
    root = workspace.resolve(strict = True)
    state = root / '.integration-test'
    if state.is_symlink() or (state / 'baseline.json').is_symlink() or (state / 'evidence.json').is_symlink():
        raise ValueError('state must not be a symbolic link')
    manifest = _load_json(state / 'baseline.json')
    record = _load_json(state / 'evidence.json')
    platform = manifest['platform']
    if record.get('platform') != platform or record.get('fixture') != manifest['fixture']:
        raise ValueError('platform/fixture mismatch between baseline and evidence')
    before = manifest['original_files']
    after = inventory(root / 'subject')
    original_unchanged = before == after
    problems = []
    if not original_unchanged:
        problems.append('AUDITED_SOURCE_CHANGED: fixture differs from baseline')
    client_checks = {}
    checked = record.get('checks', {})
    if set(checked) != set(CHECKS):
        raise ValueError('evidence checks do not match expected set')
    for check in CHECKS:
        item = checked[check]
        status = item.get('status')
        if status not in STATUS:
            raise ValueError(f'unknown status for {check}: {status}')
        docs = item.get('evidence_files', [])
        if not isinstance(docs, list):
            raise ValueError('evidence_files must be a list')
        valid_files = []
        for rel in docs:
            p = _evidence_file(root, rel)
            if not p.is_file() or not p.stat().st_size:
                problems.append(f'MISSING_EVIDENCE: {check}: {rel}')
            else:
                valid_files.append({'file': rel, 'sha256': file_hash(p)})
        if status == 'PASS' and (not docs or len(valid_files) != len(docs)):
            problems.append(f'UNSUPPORTED_PASS: {check} has no verified evidence files')
        client_checks[check] = {
            'operator_assertion': status,
            'evidence': valid_files,
            'independent_client_verification': 'REVIEW_REQUIRED' if status == 'PASS' else 'NOT_TESTED',
        }
    if checked['reports']['status'] == 'PASS':
        # Допускаем два расположения отчёта, но проверяем их на безопасность одинаково.
        report_roots = (root / 'audit', root / 'subject' / 'audit')
        if not any((not r.is_symlink()) and (not (r / 'README.md').is_symlink()) and
                   (r / 'README.md').is_file() for r in report_roots):
            problems.append('UNSUPPORTED_PASS: reports are asserted but no audit/README.md is present')
    if checked['no_unauthorized_change']['status'] == 'PASS' and not original_unchanged:
        problems.append('UNSUPPORTED_PASS: original files changed')
    observed = any(item['status'] != 'NOT_TESTED' for item in checked.values())
    return {
        'platform': platform, 'fixture': manifest['fixture'],
        'source_unchanged': original_unchanged,
        'checks': client_checks,
        'issues': problems,
        'status': ('FAILED_VALIDATION' if problems else
                   'EVIDENCE_REVIEW_REQUIRED' if observed else 'NOT_TESTED'),
        'client_pass_certified': False,
        'note': 'Evidence presence does not prove the client used a Skill; inspect original session logs and client UI.',
    }

def main(argv = None):
    ap = argparse.ArgumentParser(description = __doc__)
    sub = ap.add_subparsers(dest = 'command', required = True)
    sub.add_parser('probe', help = 'Read-only PATH discovery; never executes clients')
    prep = sub.add_parser('prepare', help = 'Create isolated fixture and install Skills; no clients invoked')
    prep.add_argument('--platform', required = True, choices = sorted(PLATFORMS))
    prep.add_argument('--workspace', required = True, type = Path)
    prep.add_argument('--fixture', default = 'skill-clean', choices = sorted(SAFE_FIXTURES))
    ev = sub.add_parser('assess', help = 'Evaluate operator evidence and snapshot; no client invoked')
    ev.add_argument('--workspace', required = True, type = Path)
    args = ap.parse_args(argv)
    try:
        data = (probe() if args.command == 'probe' else
              prepare(args.platform, args.workspace, args.fixture) if args.command == 'prepare' else
              assess(args.workspace))
        print(json.dumps(data, ensure_ascii = False, indent = 2))
        return 2 if data.get('status') == 'FAILED_VALIDATION' else 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False), file = sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
