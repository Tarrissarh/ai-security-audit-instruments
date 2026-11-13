#!/usr/bin/env python3
"""v6.2: explicit read-only AI-client test executor.

Requires a *pre-existing* CLI and a disposable fixture prepared by real_client.py.
Never downloads packages, executes audited fixture code, or certifies Skill discovery.
The CLI may itself contact an AI service and incur charges: --execute and --consent
are both required. Use an external OS sandbox if one must prevent access outside
this workspace (vendor read-only modes are not an OS-wide confinement guarantee).
"""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations
# Импортирует модуль или имена, используемые в этом файле.
import argparse
# Импортирует модуль или имена, используемые в этом файле.
from datetime import datetime, timezone
# Импортирует модуль или имена, используемые в этом файле.
import hashlib
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
import os
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import re
# Импортирует модуль или имена, используемые в этом файле.
import shutil
# Импортирует модуль или имена, используемые в этом файле.
import subprocess
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
import uuid

# Импортирует модуль или имена, используемые в этом файле.
from real_client import (CLIENT_BINS, SAFE_FIXTURES, _load_json, assess, inventory)

# Сохраняет или обновляет вычисленное значение для последующих операций.
MAX_STDIO = 512 * 1024
# Сохраняет или обновляет вычисленное значение для последующих операций.
DEFAULT_TIMEOUT = 180
# Сохраняет или обновляет вычисленное значение для последующих операций.
BINARY_NAMES = {
    # Устанавливает поле opencode в словаре или описании.
    'opencode': ('opencode',),
    # Устанавливает поле deepseek-harness в словаре или описании.
    'deepseek-harness': ('dsh',),
    # Устанавливает поле claude-code в словаре или описании.
    'claude-code': ('claude',),
    # Устанавливает поле codex в словаре или описании.
    'codex': ('codex',),
    # Устанавливает поле cursor в словаре или описании.
    'cursor': ('agent', 'cursor-agent'), # not the Cursor GUI executable
}
# Сохраняет или обновляет вычисленное значение для последующих операций.
API_KEY_NAMES = ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY', 'OPENROUTER_API_KEY')

# Сохраняет или обновляет вычисленное значение для последующих операций.
PROMPT = (
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'Use the installed audit-workflow Skill to perform a READ-ONLY inspection of '
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'the synthetic test fixture in ./subject. Locate the audit-workflow Skill '
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'and read its references/preflight.md. Return a concise JSON object with '
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'fields skill_name, references_read, observations, limitations. '
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'Never modify files, execute code, access external paths or secrets, call '
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'network tools, generate new tools, or read any gold/ benchmark answers. '
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'Do NOT claim a skill was loaded unless the client log supports that claim.'
)


# Объявляет функцию workspace_state и её параметры.
def workspace_state(workspace: Path) -> tuple[Path, dict]:
    # Проверяет условие перед выполнением следующего блока.
    if workspace.is_symlink() or not workspace.is_dir():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('workspace must be existing real directory (no symlinks)')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = workspace.resolve(strict = True)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    state = root / '.integration-test'
    # Проверяет условие перед выполнением следующего блока.
    if state.is_symlink() or (state / 'baseline.json').is_symlink():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('symlinked state is forbidden')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    manifest = _load_json(state / 'baseline.json')
    # Проверяет условие перед выполнением следующего блока.
    if manifest.get('platform') not in BINARY_NAMES or manifest.get('fixture') not in SAFE_FIXTURES:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('not a prepared v6.1 integration workspace')
    # Проверяет условие перед выполнением следующего блока.
    if inventory(root / 'subject') != manifest['original_files']:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('fixture was changed: refuse to launch client against stale baseline')
    # Возвращает вычисленный результат вызывающему коду.
    return root, manifest


# Объявляет функцию command_for и её параметры.
def command_for(platform: str, prompt: str = PROMPT) -> list[str]:
    # Описывает назначение блока в многострочной строке документации.
    """CLI flags are pinned to documented read-only modes; recheck --help at runtime."""
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    cmd = {
        # Устанавливает поле opencode в словаре или описании.
        'opencode': ['opencode', 'run', '--standalone', '--agent', 'plan', '--format', 'json'],
        # Verified CLI syntax: no documented read-only flag for the headless profile.
        # `run()` must refuse to execute this entry until an isolated policy is verified.
        # Устанавливает поле deepseek-harness в словаре или описании.
        'deepseek-harness': ['dsh', '--profile', 'headless'],
        # Устанавливает поле claude-code в словаре или описании.
        'claude-code': ['claude', '-p', '--permission-mode', 'plan', '--output-format', 'json'],
        # Устанавливает поле codex в словаре или описании.
        'codex': ['codex', 'exec', '--sandbox', 'read-only', '--json', '--skip-git-repo-check'],
        # Устанавливает поле cursor в словаре или описании.
        'cursor': ['agent', '-p', '--mode=ask', '--output-format', 'json'],
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    }[platform]
    # Возвращает вычисленный результат вызывающему коду.
    return [ * cmd, prompt]


# A documented command is not equivalent to a verified read-only execution policy.
# DeepSeek Harness headless is deliberately disabled by this runner. A user may
# test it manually in an external sandbox, but this script does not execute it.
# Сохраняет или обновляет вычисленное значение для последующих операций.
READ_ONLY_UNVERIFIED = frozenset({'deepseek-harness'})


# Объявляет функцию _read_only_opencode_config и её параметры.
def _read_only_opencode_config(root: Path) -> dict:
    # V2 OpenCode schema. Existing project configuration is NEVER overwritten.
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    cfg = root / 'opencode.json'
    # Проверяет условие перед выполнением следующего блока.
    if cfg.is_symlink():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('symlinked opencode.json: cannot guarantee read-only policy')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    policy = {
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        '$schema': 'https://opencode.ai/config.json',
        # Устанавливает поле permissions в словаре или описании.
        'permissions': [
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': '*', 'resource': '*', 'effect': 'deny'},
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'read', 'resource': '*', 'effect': 'allow'},
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'glob', 'resource': '*', 'effect': 'allow'},
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'grep', 'resource': '*', 'effect': 'allow'},
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'skill', 'resource': '*', 'effect': 'allow'},
        ],
        # Устанавливает поле policies в словаре или описании.
        'policies': [
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'tool.use', 'resource': 'shell:*', 'effect': 'deny'},
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'tool.use', 'resource': 'edit:*', 'effect': 'deny'},
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'tool.use', 'resource': 'external_directory:*', 'effect': 'deny'},
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'tool.use', 'resource': 'webfetch:*', 'effect': 'deny'},
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'tool.use', 'resource': 'websearch:*', 'effect': 'deny'},
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            {'action': 'tool.use', 'resource': 'execute:*', 'effect': 'deny'},
        ],
    }
    # Проверяет условие перед выполнением следующего блока.
    if cfg.exists():
        # Начинает блок с контролируемой обработкой исключений.
        try:
            # Проверяет условие перед выполнением следующего блока.
            if json.loads(cfg.read_text('utf-8')) != policy:
                # Прерывает операцию с диагностическим исключением.
                raise ValueError('existing opencode.json does not match pinned read-only policy')
        # Перехватывает указанное исключение для безопасной обработки.
        except (OSError, json.JSONDecodeError) as exc:
            # Прерывает операцию с диагностическим исключением.
            raise ValueError('existing opencode.json cannot be verified') from exc
    # Возвращает вычисленный результат вызывающему коду.
    return policy


# Объявляет функцию _binary и её параметры.
def _binary(platform: str) -> str | None:
    # Перебирает элементы набора для последовательной обработки.
    for name in BINARY_NAMES[platform]:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        found = shutil.which(name)
        # Проверяет условие перед выполнением следующего блока.
        if found:
            # Возвращает вычисленный результат вызывающему коду.
            return found
    # Возвращает вычисленный результат вызывающему коду.
    return None


# Объявляет функцию plan и её параметры.
def plan(workspace: Path) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root, manifest = workspace_state(workspace)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    platform = manifest['platform']
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    cmd = command_for(platform)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    exe = _binary(platform)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    status = ('BLOCKED_CLI_NOT_FOUND' if not exe else
              # Формирует часть выражения или передаёт аргумент в текущую операцию.
              'BLOCKED_READ_ONLY_UNVERIFIED' if platform in READ_ONLY_UNVERIFIED else
              # Формирует часть выражения или передаёт аргумент в текущую операцию.
              'READY_FOR_EXPLICIT_EXECUTION')
    # Возвращает вычисленный результат вызывающему коду.
    return {
        # Устанавливает поле workspace в словаре или описании.
        'workspace': str(root), 'platform': platform,
        # Устанавливает поле cli_present в словаре или описании.
        'cli_present': bool(exe), 'cli_path': exe,
        # Устанавливает поле command_preview в словаре или описании.
        'command_preview': [Path(exe).name if exe else cmd[0], * cmd[1: - 1], '<READ_ONLY_PROMPT>'],
        # Устанавливает поле source_unchanged в словаре или описании.
        'source_unchanged': True,
        # Устанавливает поле status в словаре или описании.
        'status': status,
        # Устанавливает поле client_skill_discovery в словаре или описании.
        'client_skill_discovery': 'NOT_TESTED', 'client_skill_activation': 'NOT_TESTED',
        # Устанавливает поле read_only_limitations в словаре или описании.
        'read_only_limitations': 'Vendor flags are not a host-wide sandbox. Use a disposable machine/container for stronger isolation.',
        # Устанавливает поле billing_note в словаре или описании.
        'billing_note': 'Live model calls can incur charges. No client runs without --execute --consent.',
    }


# Объявляет функцию _isolated_env и её параметры.
def _isolated_env(root: Path) -> dict[str, str]:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    env = {}
    # Перебирает элементы набора для последовательной обработки.
    for key in ('PATH', 'PATHEXT', 'COMSPEC', 'SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'LANG', 'LC_ALL', 'TERM'):
        # Проверяет условие перед выполнением следующего блока.
        if key in os.environ:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            env[key] = os.environ[key]
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    state = root / '.integration-test'
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    home = state / 'client-home'
    # Перебирает элементы набора для последовательной обработки.
    for p in (home, home / 'config', home / 'cache', home / 'data', home / 'tmp'):
        # Настраивает аргументы, параметры или состояние объекта.
        p.mkdir(mode = 0o700, exist_ok = True)
        # Проверяет условие перед выполнением следующего блока.
        if p.is_symlink():
            # Прерывает операцию с диагностическим исключением.
            raise ValueError('symlinked isolated home path')
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    env.update({
        # Устанавливает поле HOME в словаре или описании.
        'HOME': str(home), 'USERPROFILE': str(home),
        # Устанавливает поле APPDATA в словаре или описании.
        'APPDATA': str(home / 'config'), 'LOCALAPPDATA': str(home / 'data'),
        # Устанавливает поле XDG_CONFIG_HOME в словаре или описании.
        'XDG_CONFIG_HOME': str(home / 'config'),
        # Устанавливает поле XDG_CACHE_HOME в словаре или описании.
        'XDG_CACHE_HOME': str(home / 'cache'),
        # Устанавливает поле XDG_DATA_HOME в словаре или описании.
        'XDG_DATA_HOME': str(home / 'data'),
        # Устанавливает поле TMPDIR в словаре или описании.
        'TMPDIR': str(home / 'tmp'), 'TMP': str(home / 'tmp'), 'TEMP': str(home / 'tmp'),
        # Устанавливает поле CI в словаре или описании.
        'CI': '1', 'NO_COLOR': '1',
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    })
    # Перебирает элементы набора для последовательной обработки.
    for key in API_KEY_NAMES:
        # Проверяет условие перед выполнением следующего блока.
        if os.environ.get(key):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            env[key] = os.environ[key]
    # Возвращает вычисленный результат вызывающему коду.
    return env


# Объявляет функцию _redact и её параметры.
def _redact(raw: bytes, env: dict[str, str]) -> str:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    txt = raw.decode('utf-8', errors = 'replace')
    # Перебирает элементы набора для последовательной обработки.
    for key in API_KEY_NAMES:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        token = env.get(key)
        # Проверяет условие перед выполнением следующего блока.
        if token and len(token) > 5:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            txt = txt.replace(token, f'[REDACTED_{key}]')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    txt = re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._\-]{12,}', r'\1[REDACTED]', txt)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    txt = re.sub(r'\bsk-[A-Za-z0-9_\-]{12,}', '[REDACTED_KEY]', txt)
    # Возвращает вычисленный результат вызывающему коду.
    return txt[: MAX_STDIO]


# Объявляет функцию _write_private и её параметры.
def _write_private(path: Path, content: str):
    # Проверяет условие перед выполнением следующего блока.
    if path.is_symlink() or path.exists():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('refuse overwriting existing log')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    # Открывает управляемый контекст и гарантирует его корректное завершение.
    with os.fdopen(fd, 'w', encoding = 'utf-8') as f:
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        f.write(content)


# Объявляет функцию run и её параметры.
def run(workspace: Path, * , execute = False, consent = False, timeout = DEFAULT_TIMEOUT) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root, manifest = workspace_state(workspace)
    # Проверяет условие перед выполнением следующего блока.
    if not execute:
        # Возвращает вычисленный результат вызывающему коду.
        return plan(root)
    # Проверяет условие перед выполнением следующего блока.
    if not consent:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('real client execution requires BOTH --execute and --consent')
    # Проверяет условие перед выполнением следующего блока.
    if timeout < 10 or timeout > 1800:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('timeout must be between 10 and 1800 seconds')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    platform = manifest['platform']
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    exe = _binary(platform)
    # Проверяет условие перед выполнением следующего блока.
    if not exe:
        # Возвращает вычисленный результат вызывающему коду.
        return {'status': 'BLOCKED_CLI_NOT_FOUND', 'platform': platform, 'client_executed': False}
    # Проверяет условие перед выполнением следующего блока.
    if platform in READ_ONLY_UNVERIFIED:
        # Возвращает вычисленный результат вызывающему коду.
        return {'status': 'BLOCKED_READ_ONLY_UNVERIFIED', 'platform': platform,
                # Устанавливает поле client_executed в словаре или описании.
                'client_executed': False,
                # Устанавливает поле reason в словаре или описании.
                'reason': 'Headless CLI exists but no verified vendor read-only policy was found.'}
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args = command_for(platform)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args[0] = exe
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    env = _isolated_env(root)
    # Проверяет условие перед выполнением следующего блока.
    if platform == 'opencode':
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        config = _read_only_opencode_config(root)
        # Проверяет условие перед выполнением следующего блока.
        if not (root / 'opencode.json').exists():
            # Вызывает функцию для выполнения операции.
            _write_private(root / 'opencode.json', json.dumps(config, indent = 2) + '\n')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    started = datetime.now(timezone.utc).isoformat()
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    error = None
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        completed = subprocess.run(args, cwd = root, env = env, capture_output = True, timeout = timeout, check = False)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        process_status = 'EXIT_ZERO' if exit_code == 0 else 'NONZERO_EXIT'
    # Перехватывает указанное исключение для безопасной обработки.
    except subprocess.TimeoutExpired as exc:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        stdout, stderr, exit_code = exc.stdout or b'', exc.stderr or b'', None
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        process_status = 'TIMEOUT'
    # Перехватывает указанное исключение для безопасной обработки.
    except OSError as exc:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        stdout, stderr, exit_code, error = b'', b'', None, str(exc)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        process_status = 'OS_ERROR'
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    finished = datetime.now(timezone.utc).isoformat()
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    out_dir = root / '.integration-test' / 'client-runs'
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    out_dir.mkdir(mode = 0o700, exist_ok = True)
    # Проверяет условие перед выполнением следующего блока.
    if out_dir.is_symlink():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('symlinked client-runs directory')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    run_id = uuid.uuid4().hex
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    standard_out, standard_err = _redact(stdout, env), _redact(stderr, env)
    # Вызывает функцию для выполнения операции.
    _write_private(out_dir / f'{run_id}.stdout.txt', standard_out)
    # Вызывает функцию для выполнения операции.
    _write_private(out_dir / f'{run_id}.stderr.txt', standard_err)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    original_unchanged = inventory(root / 'subject') == manifest['original_files']
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    record = {
        # Устанавливает поле schema_version в словаре или описании.
        'schema_version': '1.0', 'run_id': run_id, 'platform': platform,
        # Устанавливает поле started_at в словаре или описании.
        'started_at': started, 'finished_at': finished,
        # Устанавливает поле command в словаре или описании.
        'command': [Path(exe).name, * args[1: - 1], '<READ_ONLY_PROMPT>'],
        # Устанавливает поле process_status в словаре или описании.
        'process_status': process_status, 'exit_code': exit_code,
        # Устанавливает поле execution_attempted в словаре или описании.
        'execution_attempted': True, 'source_unchanged': original_unchanged,
        # Устанавливает поле stdout_file в словаре или описании.
        'stdout_file': f'.integration-test/client-runs/{run_id}.stdout.txt',
        # Устанавливает поле stderr_file в словаре или описании.
        'stderr_file': f'.integration-test/client-runs/{run_id}.stderr.txt',
        # Устанавливает поле stdout_sha256 в словаре или описании.
        'stdout_sha256': hashlib.sha256(standard_out.encode()).hexdigest(),
        # Устанавливает поле stderr_sha256 в словаре или описании.
        'stderr_sha256': hashlib.sha256(standard_err.encode()).hexdigest(),
        # Устанавливает поле truncated в словаре или описании.
        'truncated': len(standard_out) >= MAX_STDIO or len(standard_err) >= MAX_STDIO,
        # Устанавливает поле stdout_raw_bytes в словаре или описании.
        'stdout_raw_bytes': len(stdout), 'stderr_raw_bytes': len(stderr),
        # Устанавливает поле stdout_redacted в словаре или описании.
        'stdout_redacted': standard_out != stdout.decode('utf-8', errors = 'replace')[: MAX_STDIO],
        # Устанавливает поле stderr_redacted в словаре или описании.
        'stderr_redacted': standard_err != stderr.decode('utf-8', errors = 'replace')[: MAX_STDIO],
        # Устанавливает поле error в словаре или описании.
        'error': error,
        # Устанавливает поле client_skill_discovery в словаре или описании.
        'client_skill_discovery': 'REVIEW_REQUIRED' if process_status == 'EXIT_ZERO' else 'NOT_TESTED',
        # Устанавливает поле client_skill_activation в словаре или описании.
        'client_skill_activation': 'REVIEW_REQUIRED' if process_status == 'EXIT_ZERO' else 'NOT_TESTED',
        # Устанавливает поле client_pass_certified в словаре или описании.
        'client_pass_certified': False,
        # Устанавливает поле limitations в словаре или описании.
        'limitations': 'CLI exit 0 and logs do NOT prove skill loading or correct audit. A human must inspect session evidence.',
    }
    # Вызывает функцию для выполнения операции.
    _write_private(out_dir / f'{run_id}.json', json.dumps(record, ensure_ascii = False, indent = 2) + '\n')
    # Возвращает вычисленный результат вызывающему коду.
    return record


# Объявляет функцию verify и её параметры.
def verify(workspace: Path) -> dict:
    # Описывает назначение блока в многострочной строке документации.
    """Check local log provenance only. Never declare client or Skill success."""
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root, manifest = workspace_state(workspace)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    directory = root / '.integration-test' / 'client-runs'
    # Проверяет условие перед выполнением следующего блока.
    if directory.is_symlink():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('client-runs directory is symlinked')
    # Проверяет условие перед выполнением следующего блока.
    if not directory.exists():
        # Возвращает вычисленный результат вызывающему коду.
        return {'status': 'NOT_TESTED', 'runs_checked': 0, 'issues': [], 'client_pass_certified': False}
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    records = sorted(directory.glob('*.json'))
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    issues = []
    # Перебирает элементы набора для последовательной обработки.
    for record_path in records:
        # Проверяет условие перед выполнением следующего блока.
        if record_path.is_symlink():
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'SYMLINKED_RECORD: {record_path.name}')
            # Переходит к следующей итерации цикла.
            continue
        # Начинает блок с контролируемой обработкой исключений.
        try:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            r = _load_json(record_path)
            # Проверяет условие перед выполнением следующего блока.
            if not isinstance(r, dict):
                # Прерывает операцию с диагностическим исключением.
                raise ValueError('run record must be a JSON object')
        # Перехватывает указанное исключение для безопасной обработки.
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'INVALID_RECORD: {record_path.name}: {exc}')
            # Переходит к следующей итерации цикла.
            continue
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        run_id = r.get('run_id')
        # Проверяет условие перед выполнением следующего блока.
        if not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{32}', run_id) or record_path.name != run_id + '.json':
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'INVALID_RUN_ID: {record_path.name}')
        # Проверяет условие перед выполнением следующего блока.
        if (r.get('schema_version') != '1.0' or r.get('platform') != manifest['platform']
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                or r.get('client_pass_certified') is not False
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                or r.get('execution_attempted') is not True):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'UNTRUSTED_RECORD_FIELDS: {record_path.name}')
        # Проверяет условие перед выполнением следующего блока.
        if r.get('process_status') not in ('EXIT_ZERO', 'NONZERO_EXIT', 'TIMEOUT', 'OS_ERROR'):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'INVALID_PROCESS_STATUS: {record_path.name}')
        # Проверяет условие перед выполнением следующего блока.
        if r.get('source_unchanged') is not True:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'SOURCE_CHANGED_IN_RUN: {record_path.name}')
        # Перебирает элементы набора для последовательной обработки.
        for field in ('started_at', 'finished_at'):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            when = r.get(field)
            # Начинает блок с контролируемой обработкой исключений.
            try:
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                parsed = datetime.fromisoformat(when)
                # Проверяет условие перед выполнением следующего блока.
                if parsed.tzinfo is None:
                    # Прерывает операцию с диагностическим исключением.
                    raise ValueError('timezone missing')
            # Перехватывает указанное исключение для безопасной обработки.
            except (TypeError, ValueError):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                issues.append(f'INVALID_TIMESTAMP: {record_path.name}/{field}')
        # Перебирает элементы набора для последовательной обработки.
        for field in ('stdout', 'stderr'):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            rel = r.get(field + '_file')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            expected = f'.integration-test/client-runs/{run_id}.{field}.txt' if isinstance(run_id, str) else ''
            # Проверяет условие перед выполнением следующего блока.
            if not isinstance(rel, str) or rel != expected:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                issues.append(f'INVALID_PATH: {record_path.name}/{field}')
                # Переходит к следующей итерации цикла.
                continue
            # Начинает блок с контролируемой обработкой исключений.
            try:
                # Импортирует модуль или имена, используемые в этом файле.
                from real_client import _evidence_file
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                f = _evidence_file(root, rel)
                # Проверяет условие перед выполнением следующего блока.
                if not f.is_file():
                    # Формирует часть выражения или передаёт аргумент в текущую операцию.
                    issues.append(f'MISSING_LOG: {record_path.name}/{field}')
                # Проверяет альтернативное условие.
                elif hashlib.sha256(f.read_bytes()).hexdigest() != r.get(field + '_sha256'):
                    # Формирует часть выражения или передаёт аргумент в текущую операцию.
                    issues.append(f'LOG_CHANGED: {record_path.name}/{field}')
            # Перехватывает указанное исключение для безопасной обработки.
            except (ValueError, OSError) as exc:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                issues.append(f'UNSAFE_LOG_PATH: {record_path.name}/{field}: {exc}')
    # Возвращает вычисленный результат вызывающему коду.
    return {
        # Устанавливает поле status в словаре или описании.
        'status': ('FAILED_LOG_INTEGRITY' if issues else
                   # Формирует часть выражения или передаёт аргумент в текущую операцию.
                   'LOCAL_LOGS_VERIFIED_CLIENT_REVIEW_REQUIRED' if records else 'NOT_TESTED'),
        # Устанавливает поле runs_checked в словаре или описании.
        'runs_checked': len(records), 'source_unchanged': True, 'issues': issues,
        # Устанавливает поле client_pass_certified в словаре или описании.
        'client_pass_certified': False,
        # Устанавливает поле note в словаре или описании.
        'note': 'Only local log bytes/hashes were checked, not whether client loaded skills.',
    }


# Объявляет функцию _load_json и её параметры.
def _load_json(path: Path) -> dict:
    # Возвращает вычисленный результат вызывающему коду.
    return json.loads(path.read_text('utf-8'))


# Объявляет функцию main и её параметры.
def main(argv = None) -> int:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    ap = argparse.ArgumentParser(description = __doc__)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    sp = ap.add_subparsers(dest = 'action', required = True)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    p = sp.add_parser('plan', help = 'no client execution')
    # Настраивает аргументы, параметры или состояние объекта.
    p.add_argument('--workspace', type = Path, required = True)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    r = sp.add_parser('run', help = 'requires two explicit approval switches')
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    r.add_argument('--workspace', type = Path, required = True)
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    r.add_argument('--execute', action = 'store_true', help = 'run installed client')
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    r.add_argument('--consent', action = 'store_true', help = 'acknowledge model/network use and possible API charges')
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    r.add_argument('--timeout', type = int, default = DEFAULT_TIMEOUT)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    v = sp.add_parser('verify', help = 'check saved logs without certifying client behavior')
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    v.add_argument('--workspace', type = Path, required = True)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    a = ap.parse_args(argv)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        value = (plan(a.workspace) if a.action == 'plan' else
                 # Вызывает функцию для выполнения операции.
                 verify(a.workspace) if a.action == 'verify' else
                 # Вызывает функцию для выполнения операции.
                 run(a.workspace, execute = a.execute, consent = a.consent, timeout = a.timeout))
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps(value, ensure_ascii = False, indent = 2))
        # Возвращает вычисленный результат вызывающему коду.
        return 0 if not str(value.get('status', '')).startswith('BLOCKED_') else 3
    # Перехватывает указанное исключение для безопасной обработки.
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False), file = sys.stderr)
        # Возвращает вычисленный результат вызывающему коду.
        return 2

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit(main())
