#!/usr/bin/env python3
"""Safe external-client test preparation and evidence validation, v6.1.

No AI client is ever launched by this utility. Its status cannot certify actual
Skill loading: client observations require a real session and human review.
Never executes code inside a fixture; never downloads or installs packages.
"""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations

# Импортирует модуль или имена, используемые в этом файле.
import argparse
# Импортирует модуль или имена, используемые в этом файле.
import hashlib
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
from datetime import datetime, timezone
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import shutil
# Импортирует модуль или имена, используемые в этом файле.
import sys

# Сохраняет или обновляет вычисленное значение для последующих операций.
BUNDLE = Path(__file__).resolve().parents[2]
# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(BUNDLE / 'scripts'))
# Импортирует модуль или имена, используемые в этом файле.
from platform_compat import IDS, PLATFORMS, inspect, stage  # noqa: E402

# Сохраняет или обновляет вычисленное значение для последующих операций.
CLIENT_BINS = {
    # Устанавливает поле opencode в словаре или описании.
    'opencode': ('opencode',),
    # Устанавливает поле deepseek-harness в словаре или описании.
    'deepseek-harness': ('dsh',),
    # Устанавливает поле claude-code в словаре или описании.
    'claude-code': ('claude',),
    # Устанавливает поле codex в словаре или описании.
    'codex': ('codex',),
    # Устанавливает поле cursor в словаре или описании.
    'cursor': ('agent', 'cursor-agent'),
}
# Сохраняет или обновляет вычисленное значение для последующих операций.
CHECKS = (
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'discovery', 'activation', 'reference_loading', 'orchestration',
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'reports', 'no_unauthorized_change', 'generator_consent', 'quality',
)
# Сохраняет или обновляет вычисленное значение для последующих операций.
STATUS = {'NOT_TESTED', 'BLOCKED', 'FAIL', 'PASS'}
# Сохраняет или обновляет вычисленное значение для последующих операций.
SAFE_FIXTURES = {
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'skill-clean', 'skill-issues', 'agent-clean', 'agent-issues',
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'command-clean', 'command-issues', 'mcp-clean', 'mcp-issues',
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'lsp-clean', 'lsp-issues', 'hooks-clean', 'hooks-issues',
}


# Объявляет функцию file_hash и её параметры.
def file_hash(path: Path) -> str:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    h = hashlib.sha256()
    # Открывает управляемый контекст и гарантирует его корректное завершение.
    with path.open('rb') as src:
        # Перебирает элементы набора для последовательной обработки.
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            h.update(chunk)
    # Возвращает вычисленный результат вызывающему коду.
    return h.hexdigest()


# Объявляет функцию inventory и её параметры.
def inventory(root: Path) -> dict[str, str]:
    # Описывает назначение блока в многострочной строке документации.
    """Only regular, local files; symlinked fixture content is rejected."""
    # Проверяет условие перед выполнением следующего блока.
    if root.is_symlink() or not root.is_dir():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('subject must be a normal directory')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    data = {}
    # Перебирает элементы набора для последовательной обработки.
    for p in sorted(root.rglob('*')):
        # Check symlinks BEFORE excluding generated reports. A link in audit/
        # must not escape the workspace merely because the report is ignored.
        # Проверяет условие перед выполнением следующего блока.
        if p.is_symlink():
            # Прерывает операцию с диагностическим исключением.
            raise ValueError(f'symlink forbidden in fixture: {p}')
        # Some hosts put generated audit documentation inside the subject.
        # Проверяет условие перед выполнением следующего блока.
        if p.relative_to(root).parts[0] == 'audit':
            # Переходит к следующей итерации цикла.
            continue
        # Проверяет условие перед выполнением следующего блока.
        if p.is_file():
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            data[p.relative_to(root).as_posix()] = file_hash(p)
    # Возвращает вычисленный результат вызывающему коду.
    return data


# Объявляет функцию probe и её параметры.
def probe() -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    result = {}
    # Перебирает элементы набора для последовательной обработки.
    for platform, names in CLIENT_BINS.items():
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        matches = [{'binary': name, 'path': shutil.which(name)} for name in names]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        found = [m for m in matches if m['path']]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result[platform] = {
            # Устанавливает поле binary_candidates в словаре или описании.
            'binary_candidates': matches,
            # Устанавливает поле cli_present в словаре или описании.
            'cli_present': bool(found),
            # Устанавливает поле client_version в словаре или описании.
            'client_version': 'NOT_VERIFIED',
            # Устанавливает поле actual_skill_discovery в словаре или описании.
            'actual_skill_discovery': 'NOT_TESTED',
            # Устанавливает поле actual_skill_execution в словаре или описании.
            'actual_skill_execution': 'NOT_TESTED',
            # Устанавливает поле note в словаре или описании.
            'note': 'Presence on PATH is not proof of active client or correct identity.',
        }
    # Возвращает вычисленный результат вызывающему коду.
    return {'checked_at': datetime.now(timezone.utc).isoformat(), 'clients': result,
            # Устанавливает поле client_commands_executed в словаре или описании.
            'client_commands_executed': 0}


# Объявляет функцию _empty_workspace и её параметры.
def _empty_workspace(path: Path) -> Path:
    # No resolution of a caller-supplied symlink into another location.
    # Проверяет условие перед выполнением следующего блока.
    if path.is_symlink() or not path.exists() or not path.is_dir():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('workspace must be an existing regular directory')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = path.resolve()
    # Проверяет условие перед выполнением следующего блока.
    if any(root.iterdir()):
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('workspace must be empty; use a new disposable directory')
    # Возвращает вычисленный результат вызывающему коду.
    return root


# Объявляет функцию prepare и её параметры.
def prepare(platform: str, workspace: Path, fixture: str) -> dict:
    # Проверяет условие перед выполнением следующего блока.
    if platform not in PLATFORMS or fixture not in SAFE_FIXTURES:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('invalid platform or fixture')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = _empty_workspace(workspace)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    source = BUNDLE / 'quality' / 'fixtures' / fixture
    # Вызывает функцию для выполнения операции.
    inventory(source)  # Reject fixture symlinks and unreadable sources.
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    (root / '.git').mkdir()
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    dest = root / 'subject'
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    shutil.copytree(source, dest)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    state = root / '.integration-test'
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    state.mkdir(mode = 0o700)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    manifest = {
        # Устанавливает поле schema_version в словаре или описании.
        'schema_version': '1.0', 'platform': platform, 'fixture': fixture,
        # Устанавливает поле created_at в словаре или описании.
        'created_at': datetime.now(timezone.utc).isoformat(),
        # Устанавливает поле original_files в словаре или описании.
        'original_files': inventory(dest),
        # Устанавливает поле ai_client_executed_by_prepare в словаре или описании.
        'ai_client_executed_by_prepare': False,
    }
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    (state / 'baseline.json').write_text(json.dumps(manifest, indent = 2, ensure_ascii = False) + '\n', encoding = 'utf-8')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    evidence = {
        # Устанавливает поле platform в словаре или описании.
        'platform': platform, 'client_version': None,
        # Устанавливает поле checked_at в словаре или описании.
        'checked_at': None, 'fixture': fixture,
        # Устанавливает поле checks в словаре или описании.
        'checks': {k: {'status': 'NOT_TESTED', 'evidence_files': [], 'notes': ''} for k in CHECKS},
        # Устанавливает поле constraints в словаре или описании.
        'constraints': ['Use only synthetic fixture; do not execute audited code',
                        # Формирует часть выражения или передаёт аргумент в текущую операцию.
                        'Inspect client session logs independently before claiming PASS',
                        # Формирует часть выражения или передаёт аргумент в текущую операцию.
                        'No automatic ai-tool-generator invocation'],
    }
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    (state / 'evidence.json').write_text(json.dumps(evidence, indent = 2, ensure_ascii = False) + '\n', encoding = 'utf-8')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    staged = stage(platform, root, apply = True)
    # Проверяет условие перед выполнением следующего блока.
    if staged['status'] != 'LOCAL_INSTALL_PASS':
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('local skill installation failed: ' + str(staged.get('errors')))
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    snapshot = inspect(platform, root)
    # Возвращает вычисленный результат вызывающему коду.
    return {'status': 'READY_FOR_MANUAL_CLIENT_TEST', 'platform': platform,
            # Устанавливает поле fixture в словаре или описании.
            'fixture': fixture, 'workspace': str(root),
            # Устанавливает поле installed_skill_count в словаре или описании.
            'installed_skill_count': len(snapshot['found']),
            # Устанавливает поле local_discovery в словаре или описании.
            'local_discovery': snapshot['local_discovery_static'],
            # Устанавливает поле real_client_discovery в словаре или описании.
            'real_client_discovery': 'NOT_TESTED',
            # Устанавливает поле real_client_activation в словаре или описании.
            'real_client_activation': 'NOT_TESTED',
            # Устанавливает поле client_executed в словаре или описании.
            'client_executed': False,
            # Устанавливает поле evidence_template в словаре или описании.
            'evidence_template': str(state / 'evidence.json')}


# Объявляет функцию _load_json и её параметры.
def _load_json(path: Path):
    # Возвращает вычисленный результат вызывающему коду.
    return json.loads(path.read_text(encoding = 'utf-8'))


# Объявляет функцию _evidence_file и её параметры.
def _evidence_file(root: Path, relative: str) -> Path:
    # Проверяет условие перед выполнением следующего блока.
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('evidence path must be a nonempty relative path')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    parts = Path(relative).parts
    # Проверяет условие перед выполнением следующего блока.
    if '..' in parts or '.' in parts:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('evidence path escapes workspace')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    current = root
    # Перебирает элементы набора для последовательной обработки.
    for part in parts:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        current = current / part
        # Проверяет условие перед выполнением следующего блока.
        if current.is_symlink():
            # Прерывает операцию с диагностическим исключением.
            raise ValueError('evidence symlink forbidden')
    # Проверяет условие перед выполнением следующего блока.
    if not current.is_relative_to(root):
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('invalid evidence path')
    # Возвращает вычисленный результат вызывающему коду.
    return current


# Объявляет функцию assess и её параметры.
def assess(workspace: Path) -> dict:
    # Проверяет условие перед выполнением следующего блока.
    if workspace.is_symlink() or not workspace.is_dir():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('workspace must be a normal directory')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = workspace.resolve(strict = True)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    state = root / '.integration-test'
    # Проверяет условие перед выполнением следующего блока.
    if state.is_symlink() or (state / 'baseline.json').is_symlink() or (state / 'evidence.json').is_symlink():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('state must not be a symbolic link')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    manifest = _load_json(state / 'baseline.json')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    record = _load_json(state / 'evidence.json')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    platform = manifest['platform']
    # Проверяет условие перед выполнением следующего блока.
    if record.get('platform') != platform or record.get('fixture') != manifest['fixture']:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('platform/fixture mismatch between baseline and evidence')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    before = manifest['original_files']
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    after = inventory(root / 'subject')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    original_unchanged = before == after
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    problems = []
    # Проверяет условие перед выполнением следующего блока.
    if not original_unchanged:
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        problems.append('AUDITED_SOURCE_CHANGED: fixture differs from baseline')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    client_checks = {}
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    checked = record.get('checks', {})
    # Проверяет условие перед выполнением следующего блока.
    if set(checked) != set(CHECKS):
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('evidence checks do not match expected set')
    # Перебирает элементы набора для последовательной обработки.
    for check in CHECKS:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        item = checked[check]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        status = item.get('status')
        # Проверяет условие перед выполнением следующего блока.
        if status not in STATUS:
            # Прерывает операцию с диагностическим исключением.
            raise ValueError(f'unknown status for {check}: {status}')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        docs = item.get('evidence_files', [])
        # Проверяет условие перед выполнением следующего блока.
        if not isinstance(docs, list):
            # Прерывает операцию с диагностическим исключением.
            raise ValueError('evidence_files must be a list')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        valid_files = []
        # Перебирает элементы набора для последовательной обработки.
        for rel in docs:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = _evidence_file(root, rel)
            # Проверяет условие перед выполнением следующего блока.
            if not p.is_file() or not p.stat().st_size:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                problems.append(f'MISSING_EVIDENCE: {check}: {rel}')
            # Выполняет ветку, когда предыдущие условия не сработали.
            else:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                valid_files.append({'file': rel, 'sha256': file_hash(p)})
        # Проверяет условие перед выполнением следующего блока.
        if status == 'PASS' and (not docs or len(valid_files) != len(docs)):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            problems.append(f'UNSUPPORTED_PASS: {check} has no verified evidence files')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        client_checks[check] = {
            # Устанавливает поле operator_assertion в словаре или описании.
            'operator_assertion': status,
            # Устанавливает поле evidence в словаре или описании.
            'evidence': valid_files,
            # Устанавливает поле independent_client_verification в словаре или описании.
            'independent_client_verification': 'REVIEW_REQUIRED' if status == 'PASS' else 'NOT_TESTED',
        }
    # Проверяет условие перед выполнением следующего блока.
    if checked['reports']['status'] == 'PASS':
        # Report root may be audit/ or subject/audit/ depending on client configuration.
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        report_roots = (root / 'audit', root / 'subject' / 'audit')
        # Проверяет условие перед выполнением следующего блока.
        if not any((not r.is_symlink()) and (not (r / 'README.md').is_symlink()) and
                   # Формирует часть выражения или передаёт аргумент в текущую операцию.
                   (r / 'README.md').is_file() for r in report_roots):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            problems.append('UNSUPPORTED_PASS: reports are asserted but no audit/README.md is present')
    # Проверяет условие перед выполнением следующего блока.
    if checked['no_unauthorized_change']['status'] == 'PASS' and not original_unchanged:
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        problems.append('UNSUPPORTED_PASS: original files changed')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    observed = any(item['status'] != 'NOT_TESTED' for item in checked.values())
    # Возвращает вычисленный результат вызывающему коду.
    return {
        # Устанавливает поле platform в словаре или описании.
        'platform': platform, 'fixture': manifest['fixture'],
        # Устанавливает поле source_unchanged в словаре или описании.
        'source_unchanged': original_unchanged,
        # Устанавливает поле checks в словаре или описании.
        'checks': client_checks,
        # Устанавливает поле issues в словаре или описании.
        'issues': problems,
        # Устанавливает поле status в словаре или описании.
        'status': ('FAILED_VALIDATION' if problems else
                   # Формирует часть выражения или передаёт аргумент в текущую операцию.
                   'EVIDENCE_REVIEW_REQUIRED' if observed else 'NOT_TESTED'),
        # Устанавливает поле client_pass_certified в словаре или описании.
        'client_pass_certified': False,
        # Устанавливает поле note в словаре или описании.
        'note': 'Evidence presence does not prove the client used a Skill; inspect original session logs and client UI.',
    }


# Объявляет функцию main и её параметры.
def main(argv = None):
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    ap = argparse.ArgumentParser(description = __doc__)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    sub = ap.add_subparsers(dest = 'command', required = True)
    # Настраивает аргументы, параметры или состояние объекта.
    sub.add_parser('probe', help = 'Read-only PATH discovery; never executes clients')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    prep = sub.add_parser('prepare', help = 'Create isolated fixture and install Skills; no clients invoked')
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    prep.add_argument('--platform', required = True, choices = sorted(PLATFORMS))
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    prep.add_argument('--workspace', required = True, type = Path)
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    prep.add_argument('--fixture', default = 'skill-clean', choices = sorted(SAFE_FIXTURES))
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    ev = sub.add_parser('assess', help = 'Evaluate operator evidence and snapshot; no client invoked')
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    ev.add_argument('--workspace', required = True, type = Path)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args = ap.parse_args(argv)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        data = (probe() if args.command == 'probe' else
              # Вызывает функцию для выполнения операции.
              prepare(args.platform, args.workspace, args.fixture) if args.command == 'prepare' else
              # Вызывает функцию для выполнения операции.
              assess(args.workspace))
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps(data, ensure_ascii = False, indent = 2))
        # Возвращает вычисленный результат вызывающему коду.
        return 2 if data.get('status') == 'FAILED_VALIDATION' else 0
    # Перехватывает указанное исключение для безопасной обработки.
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False), file = sys.stderr)
        # Возвращает вычисленный результат вызывающему коду.
        return 1


# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit(main())
