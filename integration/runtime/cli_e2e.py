#!/usr/bin/env python3
"""Explicit read-only AI-client test executor.

Requires a *pre-existing* CLI and a disposable fixture prepared by real_client.py.
Never downloads packages, executes audited fixture code, or certifies Skill discovery.
The CLI may itself contact an AI service and incur charges: --execute and --consent
are both required. Use an external OS sandbox if one must prevent access outside
this workspace (vendor read-only modes are not an OS-wide confinement guarantee).
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

from real_client import (CLIENT_BINS, SAFE_FIXTURES, _load_json, assess, inventory)

MAX_STDIO = 512 * 1024
DEFAULT_TIMEOUT = 180
BINARY_NAMES = {
    'opencode': ('opencode',),
    'deepseek-harness': ('dsh',),
    'claude-code': ('claude',),
    'codex': ('codex',),
    'cursor': ('agent', 'cursor-agent'), # not the Cursor GUI executable
}
API_KEY_NAMES = ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY', 'OPENROUTER_API_KEY')

PROMPT = (
    'Use the installed audit-workflow Skill to perform a READ-ONLY inspection of '
    'the synthetic test fixture in ./subject. Locate the audit-workflow Skill '
    'and read its references/preflight.md. Return a concise JSON object with '
    'fields skill_name, references_read, observations, limitations. '
    'Never modify files, execute code, access external paths or secrets, call '
    'network tools, generate new tools, or read any gold/ benchmark answers. '
    'Do NOT claim a skill was loaded unless the client log supports that claim.'
)

def workspace_state(workspace: Path) -> tuple[Path, dict]:
    """Загружает подготовленное тестовое окружение и отклоняет посторонние или повреждённые проекты."""
    if workspace.is_symlink() or not workspace.is_dir():
        raise ValueError('workspace must be existing real directory (no symlinks)')
    root = workspace.resolve(strict = True)
    state = root / '.integration-test'
    if state.is_symlink() or (state / 'baseline.json').is_symlink():
        raise ValueError('symlinked state is forbidden')
    manifest = _load_json(state / 'baseline.json')
    if manifest.get('platform') not in BINARY_NAMES or manifest.get('fixture') not in SAFE_FIXTURES:
        raise ValueError('not a prepared integration workspace')
    if inventory(root / 'subject') != manifest['original_files']:
        raise ValueError('fixture was changed: refuse to launch client against stale baseline')
    return root, manifest

def command_for(platform: str, prompt: str = PROMPT) -> list[str]:
    """CLI flags are pinned to documented read-only modes; recheck --help at runtime."""
    cmd = {
        'opencode': ['opencode', 'run', '--standalone', '--agent', 'plan', '--format', 'json'],
        # В headless-профиле нет подтверждённого режима только чтения: запуск без проверенной изоляции запрещён.
        'deepseek-harness': ['dsh', '--profile', 'headless'],
        'claude-code': ['claude', '-p', '--permission-mode', 'plan', '--output-format', 'json'],
        'codex': ['codex', 'exec', '--sandbox', 'read-only', '--json', '--skip-git-repo-check'],
        'cursor': ['agent', '-p', '--mode=ask', '--output-format', 'json'],
    }[platform]
    return [ * cmd, prompt]

# Наличие CLI-команды не гарантирует безопасный режим: DeepSeek Harness проверяется отдельно во внешней песочнице.
READ_ONLY_UNVERIFIED = frozenset({'deepseek-harness'})

def _read_only_opencode_config(root: Path) -> dict:
    # Формат конфигурации OpenCode должен применяться только к изолированному проекту, без перезаписи настроек пользователя.
    """Формирует ограничения прав для OpenCode в изолированном проекте, не изменяя пользовательскую конфигурацию."""
    cfg = root / 'opencode.json'
    if cfg.is_symlink():
        raise ValueError('symlinked opencode.json: cannot guarantee read-only policy')
    policy = {
        '$schema': 'https://opencode.ai/config.json',
        'permissions': [
            {'action': '*', 'resource': '*', 'effect': 'deny'},
            {'action': 'read', 'resource': '*', 'effect': 'allow'},
            {'action': 'glob', 'resource': '*', 'effect': 'allow'},
            {'action': 'grep', 'resource': '*', 'effect': 'allow'},
            {'action': 'skill', 'resource': '*', 'effect': 'allow'},
        ],
        'policies': [
            {'action': 'tool.use', 'resource': 'shell:*', 'effect': 'deny'},
            {'action': 'tool.use', 'resource': 'edit:*', 'effect': 'deny'},
            {'action': 'tool.use', 'resource': 'external_directory:*', 'effect': 'deny'},
            {'action': 'tool.use', 'resource': 'webfetch:*', 'effect': 'deny'},
            {'action': 'tool.use', 'resource': 'websearch:*', 'effect': 'deny'},
            {'action': 'tool.use', 'resource': 'execute:*', 'effect': 'deny'},
        ],
    }
    if cfg.exists():
        try:
            if json.loads(cfg.read_text('utf-8')) != policy:
                raise ValueError('existing opencode.json does not match pinned read-only policy')
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError('existing opencode.json cannot be verified') from exc
    return policy

def _binary(platform: str) -> str | None:
    for name in BINARY_NAMES[platform]:
        found = shutil.which(name)
        if found:
            return found
    return None

def plan(workspace: Path) -> dict:
    root, manifest = workspace_state(workspace)
    platform = manifest['platform']
    cmd = command_for(platform)
    exe = _binary(platform)
    status = ('BLOCKED_CLI_NOT_FOUND' if not exe else
              'BLOCKED_READ_ONLY_UNVERIFIED' if platform in READ_ONLY_UNVERIFIED else
              'READY_FOR_EXPLICIT_EXECUTION')
    return {
        'workspace': str(root), 'platform': platform,
        'cli_present': bool(exe), 'cli_path': exe,
        'command_preview': [Path(exe).name if exe else cmd[0], * cmd[1: - 1], '<READ_ONLY_PROMPT>'],
        'source_unchanged': True,
        'status': status,
        'client_skill_discovery': 'NOT_TESTED', 'client_skill_activation': 'NOT_TESTED',
        'read_only_limitations': 'Vendor flags are not a host-wide sandbox. Use a disposable machine/container for stronger isolation.',
        'billing_note': 'Live model calls can incur charges. No client runs without --execute --consent.',
    }

def _isolated_env(root: Path) -> dict[str, str]:
    """Создаёт минимальное окружение дочернего процесса без производственных секретов и путей пользователя."""
    env = {}
    for key in ('PATH', 'PATHEXT', 'COMSPEC', 'SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'LANG', 'LC_ALL', 'TERM'):
        if key in os.environ:
            env[key] = os.environ[key]
    state = root / '.integration-test'
    home = state / 'client-home'
    for p in (home, home / 'config', home / 'cache', home / 'data', home / 'tmp'):
        p.mkdir(mode = 0o700, exist_ok = True)
        if p.is_symlink():
            raise ValueError('symlinked isolated home path')
    env.update({
        'HOME': str(home), 'USERPROFILE': str(home),
        'APPDATA': str(home / 'config'), 'LOCALAPPDATA': str(home / 'data'),
        'XDG_CONFIG_HOME': str(home / 'config'),
        'XDG_CACHE_HOME': str(home / 'cache'),
        'XDG_DATA_HOME': str(home / 'data'),
        'TMPDIR': str(home / 'tmp'), 'TMP': str(home / 'tmp'), 'TEMP': str(home / 'tmp'),
        'CI': '1', 'NO_COLOR': '1',
    })
    for key in API_KEY_NAMES:
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env

def _redact(raw: bytes, env: dict[str, str]) -> str:
    """Маскирует известные секреты в диагностике перед записью журналов, не считая маскировку полной анонимизацией."""
    txt = raw.decode('utf-8', errors = 'replace')
    for key in API_KEY_NAMES:
        token = env.get(key)
        if token and len(token) > 5:
            txt = txt.replace(token, f'[REDACTED_{key}]')
    txt = re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._\-]{12,}', r'\1[REDACTED]', txt)
    txt = re.sub(r'\bsk-[A-Za-z0-9_\-]{12,}', '[REDACTED_KEY]', txt)
    return txt[: MAX_STDIO]

def _write_private(path: Path, content: str):
    if path.is_symlink() or path.exists():
        raise ValueError('refuse overwriting existing log')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding = 'utf-8') as f:
        f.write(content)

def run(workspace: Path, * , execute = False, consent = False, timeout = DEFAULT_TIMEOUT) -> dict:
    """Запускает AI-клиент только после двух явных подтверждений; до и после сравнивает хеши исходников и сохраняет свидетельства."""
    root, manifest = workspace_state(workspace)
    if not execute:
        return plan(root)
    if not consent:
        raise ValueError('real client execution requires BOTH --execute and --consent')
    if timeout < 10 or timeout > 1800:
        raise ValueError('timeout must be between 10 and 1800 seconds')
    platform = manifest['platform']
    exe = _binary(platform)
    if not exe:
        return {'status': 'BLOCKED_CLI_NOT_FOUND', 'platform': platform, 'client_executed': False}
    if platform in READ_ONLY_UNVERIFIED:
        return {'status': 'BLOCKED_READ_ONLY_UNVERIFIED', 'platform': platform,
                'client_executed': False,
                'reason': 'Headless CLI exists but no verified vendor read-only policy was found.'}
    args = command_for(platform)
    args[0] = exe
    env = _isolated_env(root)
    if platform == 'opencode':
        config = _read_only_opencode_config(root)
        if not (root / 'opencode.json').exists():
            _write_private(root / 'opencode.json', json.dumps(config, indent = 2) + '\n')
    started = datetime.now(timezone.utc).isoformat()
    error = None
    try:
        completed = subprocess.run(args, cwd = root, env = env, capture_output = True, timeout = timeout, check = False)
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
        process_status = 'EXIT_ZERO' if exit_code == 0 else 'NONZERO_EXIT'
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, exit_code = exc.stdout or b'', exc.stderr or b'', None
        process_status = 'TIMEOUT'
    except OSError as exc:
        stdout, stderr, exit_code, error = b'', b'', None, str(exc)
        process_status = 'OS_ERROR'
    finished = datetime.now(timezone.utc).isoformat()
    out_dir = root / '.integration-test' / 'client-runs'
    out_dir.mkdir(mode = 0o700, exist_ok = True)
    if out_dir.is_symlink():
        raise ValueError('symlinked client-runs directory')
    run_id = uuid.uuid4().hex
    standard_out, standard_err = _redact(stdout, env), _redact(stderr, env)
    _write_private(out_dir / f'{run_id}.stdout.txt', standard_out)
    _write_private(out_dir / f'{run_id}.stderr.txt', standard_err)
    original_unchanged = inventory(root / 'subject') == manifest['original_files']
    record = {
        'schema_version': '1.0', 'run_id': run_id, 'platform': platform,
        'started_at': started, 'finished_at': finished,
        'command': [Path(exe).name, * args[1: - 1], '<READ_ONLY_PROMPT>'],
        'process_status': process_status, 'exit_code': exit_code,
        'execution_attempted': True, 'source_unchanged': original_unchanged,
        'stdout_file': f'.integration-test/client-runs/{run_id}.stdout.txt',
        'stderr_file': f'.integration-test/client-runs/{run_id}.stderr.txt',
        'stdout_sha256': hashlib.sha256(standard_out.encode()).hexdigest(),
        'stderr_sha256': hashlib.sha256(standard_err.encode()).hexdigest(),
        'truncated': len(standard_out) >= MAX_STDIO or len(standard_err) >= MAX_STDIO,
        'stdout_raw_bytes': len(stdout), 'stderr_raw_bytes': len(stderr),
        'stdout_redacted': standard_out != stdout.decode('utf-8', errors = 'replace')[: MAX_STDIO],
        'stderr_redacted': standard_err != stderr.decode('utf-8', errors = 'replace')[: MAX_STDIO],
        'error': error,
        'client_skill_discovery': 'REVIEW_REQUIRED' if process_status == 'EXIT_ZERO' else 'NOT_TESTED',
        'client_skill_activation': 'REVIEW_REQUIRED' if process_status == 'EXIT_ZERO' else 'NOT_TESTED',
        'client_pass_certified': False,
        'limitations': 'CLI exit 0 and logs do NOT prove skill loading or correct audit. A human must inspect session evidence.',
    }
    _write_private(out_dir / f'{run_id}.json', json.dumps(record, ensure_ascii = False, indent = 2) + '\n')
    return record

def verify(workspace: Path) -> dict:
    """Check local log provenance only. Never declare client or Skill success."""
    root, manifest = workspace_state(workspace)
    directory = root / '.integration-test' / 'client-runs'
    if directory.is_symlink():
        raise ValueError('client-runs directory is symlinked')
    if not directory.exists():
        return {'status': 'NOT_TESTED', 'runs_checked': 0, 'issues': [], 'client_pass_certified': False}
    records = sorted(directory.glob('*.json'))
    issues = []
    for record_path in records:
        if record_path.is_symlink():
            issues.append(f'SYMLINKED_RECORD: {record_path.name}')
            continue
        try:
            r = _load_json(record_path)
            if not isinstance(r, dict):
                raise ValueError('run record must be a JSON object')
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            issues.append(f'INVALID_RECORD: {record_path.name}: {exc}')
            continue
        run_id = r.get('run_id')
        if not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{32}', run_id) or record_path.name != run_id + '.json':
            issues.append(f'INVALID_RUN_ID: {record_path.name}')
        if (r.get('schema_version') != '1.0' or r.get('platform') != manifest['platform']
                or r.get('client_pass_certified') is not False
                or r.get('execution_attempted') is not True):
            issues.append(f'UNTRUSTED_RECORD_FIELDS: {record_path.name}')
        if r.get('process_status') not in ('EXIT_ZERO', 'NONZERO_EXIT', 'TIMEOUT', 'OS_ERROR'):
            issues.append(f'INVALID_PROCESS_STATUS: {record_path.name}')
        if r.get('source_unchanged') is not True:
            issues.append(f'SOURCE_CHANGED_IN_RUN: {record_path.name}')
        for field in ('started_at', 'finished_at'):
            when = r.get(field)
            try:
                parsed = datetime.fromisoformat(when)
                if parsed.tzinfo is None:
                    raise ValueError('timezone missing')
            except (TypeError, ValueError):
                issues.append(f'INVALID_TIMESTAMP: {record_path.name}/{field}')
        for field in ('stdout', 'stderr'):
            rel = r.get(field + '_file')
            expected = f'.integration-test/client-runs/{run_id}.{field}.txt' if isinstance(run_id, str) else ''
            if not isinstance(rel, str) or rel != expected:
                issues.append(f'INVALID_PATH: {record_path.name}/{field}')
                continue
            try:
                from real_client import _evidence_file
                f = _evidence_file(root, rel)
                if not f.is_file():
                    issues.append(f'MISSING_LOG: {record_path.name}/{field}')
                elif hashlib.sha256(f.read_bytes()).hexdigest() != r.get(field + '_sha256'):
                    issues.append(f'LOG_CHANGED: {record_path.name}/{field}')
            except (ValueError, OSError) as exc:
                issues.append(f'UNSAFE_LOG_PATH: {record_path.name}/{field}: {exc}')
    return {
        'status': ('FAILED_LOG_INTEGRITY' if issues else
                   'LOCAL_LOGS_VERIFIED_CLIENT_REVIEW_REQUIRED' if records else 'NOT_TESTED'),
        'runs_checked': len(records), 'source_unchanged': True, 'issues': issues,
        'client_pass_certified': False,
        'note': 'Only local log bytes/hashes were checked, not whether client loaded skills.',
    }

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text('utf-8'))

def main(argv = None) -> int:
    ap = argparse.ArgumentParser(description = __doc__)
    sp = ap.add_subparsers(dest = 'action', required = True)
    p = sp.add_parser('plan', help = 'no client execution')
    p.add_argument('--workspace', type = Path, required = True)
    r = sp.add_parser('run', help = 'requires two explicit approval switches')
    r.add_argument('--workspace', type = Path, required = True)
    r.add_argument('--execute', action = 'store_true', help = 'run installed client')
    r.add_argument('--consent', action = 'store_true', help = 'acknowledge model/network use and possible API charges')
    r.add_argument('--timeout', type = int, default = DEFAULT_TIMEOUT)
    v = sp.add_parser('verify', help = 'check saved logs without certifying client behavior')
    v.add_argument('--workspace', type = Path, required = True)
    a = ap.parse_args(argv)
    try:
        value = (plan(a.workspace) if a.action == 'plan' else
                 verify(a.workspace) if a.action == 'verify' else
                 run(a.workspace, execute = a.execute, consent = a.consent, timeout = a.timeout))
        print(json.dumps(value, ensure_ascii = False, indent = 2))
        return 0 if not str(value.get('status', '')).startswith('BLOCKED_') else 3
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False), file = sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
