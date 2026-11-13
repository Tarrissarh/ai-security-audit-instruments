#!/usr/bin/env python3
"""Deterministic, local-only checkpoint manager for audit-workflow v5.2.

Manages TRUSTED audit metadata; it does NOT call LLMs, skills, tools, tests,
network endpoints, or any executable code from the audited target.

Usage:
  python workflow_state.py init --target /project/skills/foo --type skill --report-dir /project/skills/foo/audit
  python workflow_state.py record --report-dir /project/skills/foo/audit --payload /tmp/preflight.json
  python workflow_state.py resume --report-dir /project/skills/foo/audit
  python workflow_state.py finalize --report-dir /project/skills/foo/audit

Only writes under explicitly provided REPORT_DIR/state; report publication is
handled separately by audit-docs/scripts/safe_writer.py. Requires jsonschema;
validation of report Markdown additionally requires markdown-it-py.
"""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations

# Импортирует модуль или имена, используемые в этом файле.
import argparse
# Импортирует модуль или имена, используемые в этом файле.
from contextlib import contextmanager
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
import stat
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
import uuid

# Начинает блок с контролируемой обработкой исключений.
try:
    # Импортирует модуль или имена, используемые в этом файле.
    from jsonschema import Draft202012Validator, FormatChecker
# Перехватывает указанное исключение для безопасной обработки.
except ImportError as exc:
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit("Missing jsonschema. Install audit-workflow/scripts/requirements.txt manually; no automatic install.") from exc

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Сохраняет или обновляет вычисленное значение для последующих операций.
SCHEMA_DIR = ROOT / 'schemas'
# Сохраняет или обновляет вычисленное значение для последующих операций.
STAGES = ('PREFLIGHT', 'AUDIT', 'IMPROVE', 'MODERNIZE', 'DOCS', 'VALIDATE')
# Сохраняет или обновляет вычисленное значение для последующих операций.
MANDATORY = {'PREFLIGHT', 'AUDIT', 'DOCS', 'VALIDATE'}
# Сохраняет или обновляет вычисленное значение для последующих операций.
RETRYABLE = {'FAILED', 'BLOCKED', 'PARTIAL'}
# Сохраняет или обновляет вычисленное значение для последующих операций.
MAX_ATTEMPTS = 2
# Сохраняет или обновляет вычисленное значение для последующих операций.
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
# Сохраняет или обновляет вычисленное значение для последующих операций.
MAX_SOURCE_FILES = 10_000
# Сохраняет или обновляет вычисленное значение для последующих операций.
MAX_SOURCE_BYTES = 256 * 1024 * 1024
# Сохраняет или обновляет вычисленное значение для последующих операций.
EXCLUDED_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache'}


# Определяет класс и его интерфейс.
class WorkflowError(ValueError):
    # Описывает назначение блока в многострочной строке документации.
    """Unsafe input, invalid checkpoint, or invalid state transition."""


# Объявляет функцию now и её параметры.
def now() -> str:
    # Возвращает вычисленный результат вызывающему коду.
    return datetime.now(timezone.utc).isoformat(timespec = 'seconds')


# Объявляет функцию digest и её параметры.
def digest(raw: bytes) -> str:
    # Возвращает вычисленный результат вызывающему коду.
    return hashlib.sha256(raw).hexdigest()


# Объявляет функцию safe_path и её параметры.
def safe_path(path: Path) -> Path:
    # Описывает назначение блока в многострочной строке документации.
    """Reject symlinks in present components before resolving paths."""
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    p = path.absolute()
    # Перебирает элементы набора для последовательной обработки.
    for part in (p, * p.parents):
        # Проверяет условие перед выполнением следующего блока.
        if part.is_symlink():
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'symlink in managed path: {part}')
    # Возвращает вычисленный результат вызывающему коду.
    return p


# Объявляет функцию ensure_under и её параметры.
def ensure_under(root: Path, item: Path) -> None:
    # Проверяет условие перед выполнением следующего блока.
    if not item.resolve(strict = False).is_relative_to(root.resolve(strict = False)):
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError(f'path outside report directory: {item}')


# Объявляет функцию schema и её параметры.
def schema(name: str) -> dict:
    # Возвращает вычисленный результат вызывающему коду.
    return json.loads((SCHEMA_DIR / f'{name}.schema.json').read_text('utf-8'))


# Объявляет функцию validate_schema и её параметры.
def validate_schema(data: dict, name: str) -> None:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    validator = Draft202012Validator(schema(name), format_checker = FormatChecker())
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    errors = list(validator.iter_errors(data))
    # Проверяет условие перед выполнением следующего блока.
    if errors:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        first = sorted(errors, key = lambda e: (len(e.absolute_path), str(e.absolute_path)))[0]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        location = '.'.join(map(str, first.absolute_path)) or '<root>'
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError(f'invalid {name} JSON at {location}: {first.message}')


# Объявляет функцию source_fingerprint и её параметры.
def source_fingerprint(target: Path, report_dir: Path) -> str:
    """Hash source content and relative paths; exclude generated output and known caches.

    Refuses symlinks (rather than following them) and excessively large trees.
    No source bytes are stored or sent to any service.
    """
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    target = safe_path(target)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    report_dir = safe_path(report_dir)
    # Проверяет условие перед выполнением следующего блока.
    if not target.exists():
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError(f'target is missing: {target}')
    # Проверяет условие перед выполнением следующего блока.
    if target.is_dir() and target.resolve() == report_dir.resolve(strict = False):
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('report directory cannot equal audited target')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    h = hashlib.sha256()
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    paths = [target] if target.is_file() else []
    # Проверяет условие перед выполнением следующего блока.
    if target.is_dir():
        # Объявляет функцию on_error и её параметры.
        def on_error(exc: OSError):
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'cannot traverse audited target: {exc}')
        # Перебирает элементы набора для последовательной обработки.
        for directory, subdirs, files in os.walk(target, followlinks = False, onerror = on_error):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            parent = Path(directory)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            clean = []
            # Перебирает элементы набора для последовательной обработки.
            for name in sorted(subdirs):
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                entry = parent / name
                # Проверяет условие перед выполнением следующего блока.
                if name in EXCLUDED_DIRS or entry == report_dir or entry.is_relative_to(report_dir):
                    # Переходит к следующей итерации цикла.
                    continue
                # Проверяет условие перед выполнением следующего блока.
                if entry.is_symlink():
                    # Прерывает операцию с диагностическим исключением.
                    raise WorkflowError(f'symlink in audited source: {entry}')
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                clean.append(name)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            subdirs[:] = clean
            # Перебирает элементы набора для последовательной обработки.
            for name in sorted(files):
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                file = parent / name
                # Проверяет условие перед выполнением следующего блока.
                if file.is_relative_to(report_dir):
                    # Переходит к следующей итерации цикла.
                    continue
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                paths.append(file)
    # Проверяет условие перед выполнением следующего блока.
    if len(paths) > MAX_SOURCE_FILES:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('too many source files to fingerprint; use a narrower target')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    size = 0
    # Перебирает элементы набора для последовательной обработки.
    for path in sorted(paths):
        # Проверяет условие перед выполнением следующего блока.
        if path.is_symlink() or not path.is_file():
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'source entry is a symlink or non-file: {path}')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        rel = path.relative_to(target) if target.is_dir() else Path(target.name)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        h.update(rel.as_posix().encode('utf-8') + b'\0')
        # Начинает блок с контролируемой обработкой исключений.
        try:
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with path.open('rb') as f:
                # Продолжает выполнение цикла, пока условие истинно.
                while True:
                    # Сохраняет или обновляет вычисленное значение для последующих операций.
                    buf = f.read(1024 * 1024)
                    # Проверяет условие перед выполнением следующего блока.
                    if not buf:
                        # Прерывает текущий цикл.
                        break
                    # Формирует часть выражения или передаёт аргумент в текущую операцию.
                    size += len(buf)
                    # Проверяет условие перед выполнением следующего блока.
                    if size > MAX_SOURCE_BYTES:
                        # Прерывает операцию с диагностическим исключением.
                        raise WorkflowError('source exceeds hashing limit (256 MiB); choose narrower target')
                    # Формирует часть выражения или передаёт аргумент в текущую операцию.
                    h.update(buf)
        # Перехватывает указанное исключение для безопасной обработки.
        except OSError as exc:
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'cannot hash source {path}: {exc}') from exc
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        h.update(b'\0')
    # Возвращает вычисленный результат вызывающему коду.
    return h.hexdigest()


# Объявляет функцию atomic_json и её параметры.
def atomic_json(path: Path, value: dict) -> None:
    # Вызывает функцию для выполнения операции.
    safe_path(path.parent)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    data = (json.dumps(value, ensure_ascii = False, indent = 2, sort_keys = True) + '\n').encode('utf-8')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    fd, tmp = tempfile.mkstemp(prefix = '.checkpoint-', suffix = '.tmp', dir = path.parent)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with os.fdopen(fd, 'wb') as f:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.write(data)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.flush()
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            os.fsync(f.fileno())
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        os.replace(tmp, path)
    # Выполняет завершающие действия независимо от результата.
    finally:
        # Проверяет условие перед выполнением следующего блока.
        if os.path.exists(tmp):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            os.unlink(tmp)


# Объявляет функцию load_manifest и её параметры.
def load_manifest(report: Path) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    path = safe_path(report / 'state' / 'manifest.json')
    # Проверяет условие перед выполнением следующего блока.
    if not path.is_file():
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('manifest.json not found; run init first')
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        obj = json.loads(path.read_text('utf-8'))
    # Перехватывает указанное исключение для безопасной обработки.
    except (ValueError, OSError) as exc:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError(f'invalid manifest.json: {exc}') from exc
    # Вызывает функцию для выполнения операции.
    validate_schema(obj, 'manifest')
    # Возвращает вычисленный результат вызывающему коду.
    return obj


# Применяет указанный декоратор к следующему объявлению.
@contextmanager
# Объявляет функцию exclusive_lock и её параметры.
def exclusive_lock(report: Path):
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    state_dir = safe_path(report / 'state')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    lock = state_dir / '.workflow.lock'
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    # Перехватывает указанное исключение для безопасной обработки.
    except FileExistsError as exc:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('workflow locked; another process may be writing. Resolve lock manually after verifying no process is active') from exc
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with os.fdopen(fd, 'w', encoding = 'ascii') as f:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.write(str(os.getpid()))
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            f.flush()
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            os.fsync(f.fileno())
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        yield
    # Выполняет завершающие действия независимо от результата.
    finally:
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        lock.unlink(missing_ok = True)


# Объявляет функцию verify_source и её параметры.
def verify_source(manifest: dict) -> None:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    source_now = source_fingerprint(Path(manifest['target']['path']), Path(manifest['report_dir']))
    # Проверяет условие перед выполнением следующего блока.
    if source_now != manifest['target']['sha256']:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('STALE_INPUT: audited source changed. Start a new run; never resume stale results')


# Объявляет функцию init и её параметры.
def init(target: Path, target_type: str, report: Path) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    target, report = safe_path(target), safe_path(report)
    # Проверяет условие перед выполнением следующего блока.
    if target_type not in ('auto', 'skill', 'agent', 'command', 'mcp', 'lsp', 'hooks'):
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('invalid target type')
    # Проверяет условие перед выполнением следующего блока.
    if report.exists() and not report.is_dir():
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('report-dir must be a directory')
    # Проверяет условие перед выполнением следующего блока.
    if report.exists() and (report / 'state' / 'manifest.json').exists():
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('existing run found; use resume or choose another report-dir')
    # Проверяет условие перед выполнением следующего блока.
    if report.is_relative_to(target) and target.is_file():
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('cannot nest report output beneath an audited file')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    hash_value = source_fingerprint(target, report)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    state_dir = report / 'state'
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    state_dir.mkdir(parents = True, exist_ok = True, mode = 0o700)
    # Вызывает функцию для выполнения операции.
    safe_path(state_dir)
    # Открывает управляемый контекст и гарантирует его корректное завершение.
    with exclusive_lock(report):
        # Проверяет условие перед выполнением следующего блока.
        if (state_dir / 'manifest.json').exists():
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError('run created concurrently')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        timestamp = now()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        obj = {
            # Устанавливает поле schema_version в словаре или описании.
            'schema_version': '1.0', 'run_id': uuid.uuid4().hex,
            # Устанавливает поле created_at в словаре или описании.
            'created_at': timestamp, 'updated_at': timestamp,
            # Устанавливает поле target в словаре или описании.
            'target': {'path': str(target), 'type': target_type, 'sha256': hash_value},
            # Устанавливает поле report_dir в словаре или описании.
            'report_dir': str(report), 'state': 'RUNNING',
            # Устанавливает поле stages в словаре или описании.
            'stages': {stage: {'status': 'PENDING', 'attempts': 0, 'artifact': None, 'sha256': None} for stage in STAGES},
            # Устанавливает поле docs_checksums в словаре или описании.
            'docs_checksums': {},
        }
        # Вызывает функцию для выполнения операции.
        validate_schema(obj, 'manifest')
        # Вызывает функцию для выполнения операции.
        atomic_json(state_dir / 'manifest.json', obj)
    # Возвращает вычисленный результат вызывающему коду.
    return obj


# Объявляет функцию read_artifact и её параметры.
def read_artifact(report: Path, value: str, expected_sha: str) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    path = safe_path(report / 'state' / value)
    # Вызывает функцию для выполнения операции.
    ensure_under(report / 'state', path)
    # Проверяет условие перед выполнением следующего блока.
    if not path.is_file():
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError(f'missing stage artifact: {path}')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    raw = path.read_bytes()
    # Проверяет условие перед выполнением следующего блока.
    if digest(raw) != expected_sha:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError(f'stage artifact checksum mismatch: {path}')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    data = json.loads(raw.decode('utf-8'))
    # Вызывает функцию для выполнения операции.
    validate_schema(data, 'stage-result')
    # Возвращает вычисленный результат вызывающему коду.
    return data


# Объявляет функцию stage_outputs и её параметры.
def stage_outputs(report: Path, file_names: list[str], require_readme: bool = False) -> None:
    # Проверяет условие перед выполнением следующего блока.
    if require_readme and 'README.md' not in file_names:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('DOCS COMPLETE requires README.md in output_files')
    # Проверяет условие перед выполнением следующего блока.
    if require_readme and 'docs/workflow-status.md' not in file_names:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('DOCS COMPLETE requires docs/workflow-status.md in output_files')
    # Validate every path first, before checking file presence or touching the FS.
    # Перебирает элементы набора для последовательной обработки.
    for name in file_names:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        rel = Path(name)
        # Проверяет условие перед выполнением следующего блока.
        if rel.is_absolute() or '..' in rel.parts or '\\' in name:
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'unsafe output path: {name}')
        # Проверяет условие перед выполнением следующего блока.
        if not (name == 'README.md' or (len(rel.parts) >= 2 and rel.parts[0] in ('docs', 'translations') and rel.suffix.lower() == '.md')):
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'not a report Markdown path: {name}')
    # Перебирает элементы набора для последовательной обработки.
    for name in file_names:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        file = safe_path(report / name)
        # Вызывает функцию для выполнения операции.
        ensure_under(report, file)
        # Проверяет условие перед выполнением следующего блока.
        if not file.is_file() or not file.read_bytes().strip():
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'output file missing or empty: {name}')


# Объявляет функцию verify_report и её параметры.
def verify_report(report: Path, docs_files: list[str], expected: dict[str, str] | None = None) -> None:
    # Вызывает функцию для выполнения операции.
    stage_outputs(report, docs_files, require_readme = True)
    # Проверяет условие перед выполнением следующего блока.
    if expected is not None:
        # Проверяет условие перед выполнением следующего блока.
        if set(expected) != set(docs_files):
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError('document checksum index does not match declared outputs')
        # Перебирает элементы набора для последовательной обработки.
        for name in docs_files:
            # Проверяет условие перед выполнением следующего блока.
            if digest((report / name).read_bytes()) != expected[name]:
                # Прерывает операцию с диагностическим исключением.
                raise WorkflowError(f'document changed since DOCS checkpoint: {name}')
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Use bundled validator; skill installations need not be sibling directories.
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        sys.path.insert(0, str(ROOT / 'scripts'))
        # Импортирует модуль или имена, используемые в этом файле.
        from markdown_links import check_markdown_links
    # Перехватывает указанное исключение для безопасной обработки.
    except ImportError as exc:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('missing markdown-it-py; report validation unavailable') from exc
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    errors, warnings = check_markdown_links(report, [report / file for file in docs_files])
    # Проверяет условие перед выполнением следующего блока.
    if errors or warnings:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('report link validation failed: ' + '; '.join(errors + warnings))


# Объявляет функцию edges_for и её параметры.
def edges_for(manifest: dict, report: Path, pending: dict) -> list[tuple[str, str]]:
    # Устанавливает поле edges в словаре или описании.
    edges: list[tuple[str, str]] = []
    # Перебирает элементы набора для последовательной обработки.
    for stage in STAGES:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        prior = manifest['stages'][stage]
        # Проверяет условие перед выполнением следующего блока.
        if prior['artifact'] and stage != pending['stage']:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            record = read_artifact(report, prior['artifact'], prior['sha256'])
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            edges.extend((x['caller'], x['callee']) for x in record['invocations'])
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    edges.extend((x['caller'], x['callee']) for x in pending['invocations'])
    # Возвращает вычисленный результат вызывающему коду.
    return edges


# Объявляет функцию verify_invocations и её параметры.
def verify_invocations(manifest: dict, report: Path, pending: dict) -> None:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    calls = pending['invocations']
    # Проверяет условие перед выполнением следующего блока.
    if pending['method'] == 'SKILL_CALL' and not calls:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('SKILL_CALL requires documented actual invocations')
    # Проверяет условие перед выполнением следующего блока.
    if pending['method'] != 'SKILL_CALL' and calls:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('invocations must be empty unless method is SKILL_CALL')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    edges = edges_for(manifest, report, pending)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    called = [callee for _, callee in edges]
    # Проверяет условие перед выполнением следующего блока.
    if any(callee == 'ai-tool-generator' for callee in called):
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('ai-tool-generator cannot be called by audit-workflow')
    # Проверяет условие перед выполнением следующего блока.
    if len(called) != len(set(called)):
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('duplicate programmatic skill call in one audit run')
    # Устанавливает поле graph в словаре или описании.
    graph: dict[str, set[str]] = {}
    # Перебирает элементы набора для последовательной обработки.
    for caller, callee in edges:
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        graph.setdefault(caller, set()).add(callee)
        # Проверяет условие перед выполнением следующего блока.
        if callee == 'audit-workflow':
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError('recursive call into audit-workflow is forbidden')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    seen, visiting = set(), set()
    # Объявляет функцию walk и её параметры.
    def walk(node: str):
        # Проверяет условие перед выполнением следующего блока.
        if node in visiting:
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError('cyclic skill invocation graph detected')
        # Проверяет условие перед выполнением следующего блока.
        if node in seen:
            # Завершает функцию без возвращаемого значения.
            return
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        visiting.add(node)
        # Перебирает элементы набора для последовательной обработки.
        for next_node in graph.get(node, ()):
            # Вызывает функцию для выполнения операции.
            walk(next_node)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        visiting.remove(node)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        seen.add(node)
    # Перебирает элементы набора для последовательной обработки.
    for node in graph:
        # Вызывает функцию для выполнения операции.
        walk(node)


# Объявляет функцию prior_ready и её параметры.
def prior_ready(manifest: dict, stage: str) -> None:
    # Перебирает элементы набора для последовательной обработки.
    for previous in STAGES[: STAGES.index(stage)]:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        status = manifest['stages'][previous]['status']
        # Проверяет условие перед выполнением следующего блока.
        if status not in ('COMPLETE', 'PARTIAL', 'SKIPPED'):
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'{stage} cannot run before {previous} is resolved (currently {status})')
    # Проверяет условие перед выполнением следующего блока.
    if stage == 'AUDIT' and manifest['stages']['PREFLIGHT']['status'] != 'COMPLETE':
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('AUDIT requires successful PREFLIGHT')
    # Проверяет условие перед выполнением следующего блока.
    if stage == 'DOCS' and manifest['stages']['AUDIT']['status'] not in ('COMPLETE', 'PARTIAL'):
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('DOCS requires actual audit results')


# Объявляет функцию check_payload и её параметры.
def check_payload(manifest: dict, report: Path, obj: dict) -> None:
    # Вызывает функцию для выполнения операции.
    validate_schema(obj, 'stage-result')
    # Проверяет условие перед выполнением следующего блока.
    if obj['run_id'] != manifest['run_id']:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('stage result run_id does not match manifest')
    # Проверяет условие перед выполнением следующего блока.
    if obj['status'] == 'SKIPPED' and obj['stage'] in MANDATORY:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError(f'mandatory stage {obj["stage"]} cannot be SKIPPED')
    # Проверяет условие перед выполнением следующего блока.
    if obj['status'] == 'SKIPPED' and obj['method'] != 'NOT_RUN':
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('SKIPPED stage must use NOT_RUN')
    # Проверяет условие перед выполнением следующего блока.
    if obj['status'] == 'COMPLETE' and obj['method'] == 'NOT_RUN':
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('a COMPLETE stage cannot claim NOT_RUN')
    # Проверяет условие перед выполнением следующего блока.
    if obj['stage'] == 'AUDIT' and obj['status'] == 'COMPLETE' and not obj['data']['checked_files']:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('AUDIT COMPLETE requires checked_files')
    # Проверяет условие перед выполнением следующего блока.
    if obj['stage'] == 'DOCS' and obj['status'] == 'COMPLETE':
        # Вызывает функцию для выполнения операции.
        stage_outputs(report, obj['output_files'], require_readme = True)
    # Проверяет условие перед выполнением следующего блока.
    if obj['stage'] == 'VALIDATE' and obj['status'] == 'COMPLETE':
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        docs = manifest['stages']['DOCS']
        # Проверяет условие перед выполнением следующего блока.
        if docs['status'] != 'COMPLETE':
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError('VALIDATE COMPLETE requires DOCS COMPLETE')
        # Вызывает функцию для выполнения операции.
        verify_report(report, read_artifact(report, docs['artifact'], docs['sha256'])['output_files'], manifest['docs_checksums'])
        # Проверяет условие перед выполнением следующего блока.
        if not obj['data']['checks']:
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError('VALIDATE COMPLETE requires explicit checks')
        # Проверяет условие перед выполнением следующего блока.
        if any(check['status'] != 'PASSED' for check in obj['data']['checks']):
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError('VALIDATE COMPLETE cannot include failed or untested checks')
    # Вызывает функцию для выполнения операции.
    verify_invocations(manifest, report, obj)


# Объявляет функцию record и её параметры.
def record(report: Path, payload: Path) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    report, payload = safe_path(report), safe_path(payload)
    # Проверяет условие перед выполнением следующего блока.
    if not payload.is_file():
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('payload must be an existing JSON file')
    # Проверяет условие перед выполнением следующего блока.
    if payload.stat().st_size > MAX_PAYLOAD_BYTES:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError('stage payload too large (limit 2 MiB)')
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        obj = json.loads(payload.read_text('utf-8'))
    # Перехватывает указанное исключение для безопасной обработки.
    except (ValueError, OSError) as exc:
        # Прерывает операцию с диагностическим исключением.
        raise WorkflowError(f'invalid payload JSON: {exc}') from exc
    # Вызывает функцию для выполнения операции.
    validate_schema(obj, 'stage-result')
    # Открывает управляемый контекст и гарантирует его корректное завершение.
    with exclusive_lock(report):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        manifest = load_manifest(report)
        # Вызывает функцию для выполнения операции.
        verify_source(manifest)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        stage = obj['stage']
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        existing = manifest['stages'][stage]
        # Проверяет условие перед выполнением следующего блока.
        if existing['artifact']:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            old = read_artifact(report, existing['artifact'], existing['sha256'])
            # Проверяет условие перед выполнением следующего блока.
            if obj == old:
                # Возвращает вычисленный результат вызывающему коду.
                return {'status': 'UNCHANGED', 'stage': stage, 'attempts': existing['attempts']}
        # Проверяет условие перед выполнением следующего блока.
        if existing['status'] not in ('PENDING', * RETRYABLE):
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'{stage} already resolved as {existing["status"]}; no repeated stage execution')
        # Проверяет условие перед выполнением следующего блока.
        if existing['attempts'] >= MAX_ATTEMPTS:
            # Прерывает операцию с диагностическим исключением.
            raise WorkflowError(f'{stage} exceeded retry limit ({MAX_ATTEMPTS} total attempts)')
        # Вызывает функцию для выполнения операции.
        prior_ready(manifest, stage)
        # Вызывает функцию для выполнения операции.
        check_payload(manifest, report, obj)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        attempt = existing['attempts'] + 1
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        relative = f'artifacts/{stage.lower()}-{attempt}.json'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        artifact_path = report / 'state' / relative
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        artifact_path.parent.mkdir(parents = True, exist_ok = True)
        # Write artifact first; manifest is the commit record. Orphans are inert.
        # Вызывает функцию для выполнения операции.
        atomic_json(artifact_path, obj)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        existing['sha256'] = digest(artifact_path.read_bytes())
        # Проверяет условие перед выполнением следующего блока.
        if stage == 'DOCS' and obj['status'] == 'COMPLETE':
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            manifest['docs_checksums'] = {name: digest((report / name).read_bytes()) for name in obj['output_files']}
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        existing['status'] = obj['status']
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        existing['attempts'] = attempt
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        existing['artifact'] = relative
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        manifest['state'] = 'RUNNING'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        manifest['updated_at'] = now()
        # Вызывает функцию для выполнения операции.
        validate_schema(manifest, 'manifest')
        # Вызывает функцию для выполнения операции.
        atomic_json(report / 'state' / 'manifest.json', manifest)
    # Возвращает вычисленный результат вызывающему коду.
    return {'status': 'RECORDED', 'stage': stage, 'result': obj['status'], 'attempts': attempt}


# Объявляет функцию next_stage и её параметры.
def next_stage(manifest: dict) -> str | None:
    # Проверяет условие перед выполнением следующего блока.
    if manifest['state'] == 'COMPLETE':
        # Возвращает вычисленный результат вызывающему коду.
        return None
    # Перебирает элементы набора для последовательной обработки.
    for stage in STAGES:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        s = manifest['stages'][stage]
        # Проверяет условие перед выполнением следующего блока.
        if s['status'] == 'PENDING':
            # Возвращает вычисленный результат вызывающему коду.
            return stage
        # Проверяет условие перед выполнением следующего блока.
        if s['status'] in RETRYABLE and s['attempts'] < MAX_ATTEMPTS:
            # Возвращает вычисленный результат вызывающему коду.
            return stage
        # Проверяет условие перед выполнением следующего блока.
        if s['status'] in ('BLOCKED', 'FAILED') and s['attempts'] >= MAX_ATTEMPTS:
            # Возвращает вычисленный результат вызывающему коду.
            return None
    # Возвращает вычисленный результат вызывающему коду.
    return None


# Объявляет функцию resume и её параметры.
def resume(report: Path) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    manifest = load_manifest(report)
    # Вызывает функцию для выполнения операции.
    verify_source(manifest)
    # Проверяет условие перед выполнением следующего блока.
    if manifest['state'] == 'COMPLETE':
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        docs = manifest['stages']['DOCS']
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        doc_record = read_artifact(report, docs['artifact'], docs['sha256'])
        # Вызывает функцию для выполнения операции.
        verify_report(report, doc_record['output_files'], manifest['docs_checksums'])
    # Возвращает вычисленный результат вызывающему коду.
    return {'status': manifest['state'], 'run_id': manifest['run_id'],
            # Устанавливает поле next_stage в словаре или описании.
            'next_stage': next_stage(manifest),
            # Устанавливает поле stages в словаре или описании.
            'stages': {s: manifest['stages'][s]['status'] for s in STAGES}}


# Объявляет функцию finalize и её параметры.
def finalize(report: Path) -> dict:
    # Открывает управляемый контекст и гарантирует его корректное завершение.
    with exclusive_lock(report):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        manifest = load_manifest(report)
        # Вызывает функцию для выполнения операции.
        verify_source(manifest)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        stages = {s: manifest['stages'][s]['status'] for s in STAGES}
        # Проверяет условие перед выполнением следующего блока.
        if any(stages[s] == 'FAILED' for s in MANDATORY):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            status = 'FAILED'
        # Проверяет альтернативное условие.
        elif any(stages[s] == 'BLOCKED' for s in MANDATORY):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            status = 'BLOCKED'
        # Проверяет альтернативное условие.
        elif any(stages[s] != 'COMPLETE' for s in MANDATORY):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            status = 'PARTIAL'
        # Проверяет альтернативное условие.
        elif any(stages[s] in ('FAILED', 'BLOCKED', 'PENDING', 'PARTIAL') for s in ('IMPROVE', 'MODERNIZE')):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            status = 'PARTIAL'
        # Выполняет ветку, когда предыдущие условия не сработали.
        else:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            docs = read_artifact(report, manifest['stages']['DOCS']['artifact'], manifest['stages']['DOCS']['sha256'])
            # Вызывает функцию для выполнения операции.
            verify_report(report, docs['output_files'], manifest['docs_checksums'])
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            status = 'COMPLETE'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        manifest['state'] = status
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        manifest['updated_at'] = now()
        # Вызывает функцию для выполнения операции.
        atomic_json(report / 'state' / 'manifest.json', manifest)
    # Возвращает вычисленный результат вызывающему коду.
    return {'status': status, 'run_id': manifest['run_id'], 'stages': stages}


# Объявляет функцию main и её параметры.
def main(argv: list[str] | None = None) -> int:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    parser = argparse.ArgumentParser(description = __doc__)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    sub = parser.add_subparsers(dest = 'command', required = True)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    init_cmd = sub.add_parser('init', help = 'Create a new audit state')
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    init_cmd.add_argument('--target', required = True, type = Path)
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    init_cmd.add_argument('--type', required = True, choices = ['auto', 'skill', 'agent', 'command', 'mcp', 'lsp', 'hooks'])
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    init_cmd.add_argument('--report-dir', required = True, type = Path)
    # Перебирает элементы набора для последовательной обработки.
    for name in ('record', 'resume', 'finalize'):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = sub.add_parser(name)
        # Настраивает аргументы, параметры или состояние объекта.
        p.add_argument('--report-dir', type = Path, required = True)
        # Проверяет условие перед выполнением следующего блока.
        if name == 'record':
            # Настраивает аргументы, параметры или состояние объекта.
            p.add_argument('--payload', required = True, type = Path)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args = parser.parse_args(argv)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Проверяет условие перед выполнением следующего блока.
        if args.command == 'init':
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            res = init(args.target, args.type, args.report_dir)
        # Проверяет альтернативное условие.
        elif args.command == 'record':
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            res = record(args.report_dir, args.payload)
        # Проверяет альтернативное условие.
        elif args.command == 'resume':
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            res = resume(args.report_dir)
        # Выполняет ветку, когда предыдущие условия не сработали.
        else:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            res = finalize(args.report_dir)
    # Перехватывает указанное исключение для безопасной обработки.
    except WorkflowError as exc:
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False, indent = 2))
        # Возвращает вычисленный результат вызывающему коду.
        return 1
    # Выводит диагностическую информацию о результате выполнения.
    print(json.dumps(res, ensure_ascii = False, indent = 2))
    # Возвращает вычисленный результат вызывающему коду.
    return 0


# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit(main())
