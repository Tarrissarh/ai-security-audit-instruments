#!/usr/bin/env python3
"""Deterministic, local-only checkpoint manager for audit-workflow.

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
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import uuid

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    raise SystemExit("Missing jsonschema. Install audit-workflow/scripts/requirements.txt manually; no automatic install.") from exc

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / 'schemas'
STAGES = ('PREFLIGHT', 'AUDIT', 'IMPROVE', 'MODERNIZE', 'DOCS', 'VALIDATE')
MANDATORY = {'PREFLIGHT', 'AUDIT', 'DOCS', 'VALIDATE'}
RETRYABLE = {'FAILED', 'BLOCKED', 'PARTIAL'}
MAX_ATTEMPTS = 2
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_SOURCE_FILES = 10_000
MAX_SOURCE_BYTES = 256 * 1024 * 1024
EXCLUDED_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache'}

class WorkflowError(ValueError):
    """Unsafe input, invalid checkpoint, or invalid state transition."""

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec = 'seconds')

def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def safe_path(path: Path) -> Path:
    """Reject symlinks in present components before resolving paths."""
    p = path.absolute()
    for part in (p, * p.parents):
        if part.is_symlink():
            raise WorkflowError(f'symlink in managed path: {part}')
    return p

def ensure_under(root: Path, item: Path) -> None:
    """Не позволяет сохранять состояние вне каталога аудита даже при попытке обхода через относительные компоненты."""
    if not item.resolve(strict = False).is_relative_to(root.resolve(strict = False)):
        raise WorkflowError(f'path outside report directory: {item}')

def schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f'{name}.schema.json').read_text('utf-8'))

def validate_schema(data: dict, name: str) -> None:
    """Проверяет JSON по контракту этапа и сообщает точное поле ошибки вместо неясной ошибки десериализации."""
    validator = Draft202012Validator(schema(name), format_checker = FormatChecker())
    errors = list(validator.iter_errors(data))
    if errors:
        first = sorted(errors, key = lambda e: (len(e.absolute_path), str(e.absolute_path)))[0]
        location = '.'.join(map(str, first.absolute_path)) or '<root>'
        raise WorkflowError(f'invalid {name} JSON at {location}: {first.message}')

def source_fingerprint(target: Path, report_dir: Path) -> str:
    """Hash source content and relative paths; exclude generated output and known caches.

    Refuses symlinks (rather than following them) and excessively large trees.
    No source bytes are stored or sent to any service.
    """
    target = safe_path(target)
    report_dir = safe_path(report_dir)
    if not target.exists():
        raise WorkflowError(f'target is missing: {target}')
    if target.is_dir() and target.resolve() == report_dir.resolve(strict = False):
        raise WorkflowError('report directory cannot equal audited target')
    h = hashlib.sha256()
    paths = [target] if target.is_file() else []
    if target.is_dir():
        def on_error(exc: OSError):
            raise WorkflowError(f'cannot traverse audited target: {exc}')
        for directory, subdirs, files in os.walk(target, followlinks = False, onerror = on_error):
            parent = Path(directory)
            clean = []
            for name in sorted(subdirs):
                entry = parent / name
                if name in EXCLUDED_DIRS or entry == report_dir or entry.is_relative_to(report_dir):
                    continue
                if entry.is_symlink():
                    raise WorkflowError(f'symlink in audited source: {entry}')
                clean.append(name)
            subdirs[:] = clean
            for name in sorted(files):
                file = parent / name
                if file.is_relative_to(report_dir):
                    continue
                paths.append(file)
    if len(paths) > MAX_SOURCE_FILES:
        raise WorkflowError('too many source files to fingerprint; use a narrower target')
    size = 0
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file():
            raise WorkflowError(f'source entry is a symlink or non-file: {path}')
        rel = path.relative_to(target) if target.is_dir() else Path(target.name)
        h.update(rel.as_posix().encode('utf-8') + b'\0')
        try:
            with path.open('rb') as f:
                while True:
                    buf = f.read(1024 * 1024)
                    if not buf:
                        break
                    size += len(buf)
                    if size > MAX_SOURCE_BYTES:
                        raise WorkflowError('source exceeds hashing limit (256 MiB); choose narrower target')
                    h.update(buf)
        except OSError as exc:
            raise WorkflowError(f'cannot hash source {path}: {exc}') from exc
        h.update(b'\0')
    return h.hexdigest()

def atomic_json(path: Path, value: dict) -> None:
    """Публикует JSON через временный файл и атомарное переименование, не оставляя повреждённого итогового состояния."""
    safe_path(path.parent)
    data = (json.dumps(value, ensure_ascii = False, indent = 2, sort_keys = True) + '\n').encode('utf-8')
    fd, tmp = tempfile.mkstemp(prefix = '.checkpoint-', suffix = '.tmp', dir = path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def load_manifest(report: Path) -> dict:
    """Загружает состояние аудита и проверяет структурную целостность перед разрешением следующих переходов."""
    path = safe_path(report / 'state' / 'manifest.json')
    if not path.is_file():
        raise WorkflowError('manifest.json not found; run init first')
    try:
        obj = json.loads(path.read_text('utf-8'))
    except (ValueError, OSError) as exc:
        raise WorkflowError(f'invalid manifest.json: {exc}') from exc
    validate_schema(obj, 'manifest')
    return obj

@contextmanager

def exclusive_lock(report: Path):
    """Обеспечивает единственного писателя состояния, предотвращая конкурирующие переходы одного аудита."""
    state_dir = safe_path(report / 'state')
    lock = state_dir / '.workflow.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise WorkflowError('workflow locked; another process may be writing. Resolve lock manually after verifying no process is active') from exc
    try:
        with os.fdopen(fd, 'w', encoding = 'ascii') as f:
            f.write(str(os.getpid()))
            f.flush()
            os.fsync(f.fileno())
        yield
    finally:
        lock.unlink(missing_ok = True)

def verify_source(manifest: dict) -> None:
    """Блокирует возобновление при изменении исходных файлов после начала аудита."""
    source_now = source_fingerprint(Path(manifest['target']['path']), Path(manifest['report_dir']))
    if source_now != manifest['target']['sha256']:
        raise WorkflowError('STALE_INPUT: audited source changed. Start a new run; never resume stale results')

def init(target: Path, target_type: str, report: Path) -> dict:
    """Создаёт новый запуск аудита с контрольной суммой цели и обязательными этапами без выполнения исследуемого инструмента."""
    target, report = safe_path(target), safe_path(report)
    if target_type not in ('auto', 'skill', 'agent', 'command', 'mcp', 'lsp', 'hooks'):
        raise WorkflowError('invalid target type')
    if report.exists() and not report.is_dir():
        raise WorkflowError('report-dir must be a directory')
    if report.exists() and (report / 'state' / 'manifest.json').exists():
        raise WorkflowError('existing run found; use resume or choose another report-dir')
    if report.is_relative_to(target) and target.is_file():
        raise WorkflowError('cannot nest report output beneath an audited file')
    hash_value = source_fingerprint(target, report)
    state_dir = report / 'state'
    state_dir.mkdir(parents = True, exist_ok = True, mode = 0o700)
    safe_path(state_dir)
    with exclusive_lock(report):
        if (state_dir / 'manifest.json').exists():
            raise WorkflowError('run created concurrently')
        timestamp = now()
        obj = {
            'schema_version': '1.0', 'run_id': uuid.uuid4().hex,
            'created_at': timestamp, 'updated_at': timestamp,
            'target': {'path': str(target), 'type': target_type, 'sha256': hash_value},
            'report_dir': str(report), 'state': 'RUNNING',
            'stages': {stage: {'status': 'PENDING', 'attempts': 0, 'artifact': None, 'sha256': None} for stage in STAGES},
            'docs_checksums': {},
        }
        validate_schema(obj, 'manifest')
        atomic_json(state_dir / 'manifest.json', obj)
    return obj

def read_artifact(report: Path, value: str, expected_sha: str) -> dict:
    """Читает результат этапа только после проверки пути и совпадения SHA-256 с манифестом."""
    path = safe_path(report / 'state' / value)
    ensure_under(report / 'state', path)
    if not path.is_file():
        raise WorkflowError(f'missing stage artifact: {path}')
    raw = path.read_bytes()
    if digest(raw) != expected_sha:
        raise WorkflowError(f'stage artifact checksum mismatch: {path}')
    data = json.loads(raw.decode('utf-8'))
    validate_schema(data, 'stage-result')
    return data

def stage_outputs(report: Path, file_names: list[str], require_readme: bool = False) -> None:
    """Проверяет наличие ожидаемых выходных документов перед фиксацией этапа DOCS."""
    if require_readme and 'README.md' not in file_names:
        raise WorkflowError('DOCS COMPLETE requires README.md in output_files')
    if require_readme and 'docs/workflow-status.md' not in file_names:
        raise WorkflowError('DOCS COMPLETE requires docs/workflow-status.md in output_files')
    # Сначала проверяем все пути: даже простая проверка существования может пройти по недоверенной ссылке.
    for name in file_names:
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name:
            raise WorkflowError(f'unsafe output path: {name}')
        if not (name == 'README.md' or (len(rel.parts) >= 2 and rel.parts[0] in ('docs', 'translations') and rel.suffix.lower() == '.md')):
            raise WorkflowError(f'not a report Markdown path: {name}')
    for name in file_names:
        file = safe_path(report / name)
        ensure_under(report, file)
        if not file.is_file() or not file.read_bytes().strip():
            raise WorkflowError(f'output file missing or empty: {name}')

def verify_report(report: Path, docs_files: list[str], expected: dict[str, str] | None = None) -> None:
    """Проверяет, что отчёты существуют и не были изменены после фиксации их контрольных сумм."""
    stage_outputs(report, docs_files, require_readme = True)
    if expected is not None:
        if set(expected) != set(docs_files):
            raise WorkflowError('document checksum index does not match declared outputs')
        for name in docs_files:
            if digest((report / name).read_bytes()) != expected[name]:
                raise WorkflowError(f'document changed since DOCS checkpoint: {name}')
    try:
        # Используем собственный валидатор, потому что установленные скиллы могут находиться в разных корнях.
        sys.path.insert(0, str(ROOT / 'scripts'))
        from markdown_links import check_markdown_links
    except ImportError as exc:
        raise WorkflowError('missing markdown-it-py; report validation unavailable') from exc
    errors, warnings = check_markdown_links(report, [report / file for file in docs_files])
    if errors or warnings:
        raise WorkflowError('report link validation failed: ' + '; '.join(errors + warnings))

def edges_for(manifest: dict, report: Path, pending: dict) -> list[tuple[str, str]]:
    """Строит зависимости этапов и переданные вызовы для проверки разрешённого порядка выполнения."""
    edges: list[tuple[str, str]] = []
    for stage in STAGES:
        prior = manifest['stages'][stage]
        if prior['artifact'] and stage != pending['stage']:
            record = read_artifact(report, prior['artifact'], prior['sha256'])
            edges.extend((x['caller'], x['callee']) for x in record['invocations'])
    edges.extend((x['caller'], x['callee']) for x in pending['invocations'])
    return edges

def verify_invocations(manifest: dict, report: Path, pending: dict) -> None:
    """Находит циклы делегирования скиллов и запрещает скрытые рекурсивные переходы."""
    calls = pending['invocations']
    if pending['method'] == 'SKILL_CALL' and not calls:
        raise WorkflowError('SKILL_CALL requires documented actual invocations')
    if pending['method'] != 'SKILL_CALL' and calls:
        raise WorkflowError('invocations must be empty unless method is SKILL_CALL')
    edges = edges_for(manifest, report, pending)
    called = [callee for _, callee in edges]
    if any(callee == 'ai-tool-generator' for callee in called):
        raise WorkflowError('ai-tool-generator cannot be called by audit-workflow')
    if len(called) != len(set(called)):
        raise WorkflowError('duplicate programmatic skill call in one audit run')
    graph: dict[str, set[str]] = {}
    for caller, callee in edges:
        graph.setdefault(caller, set()).add(callee)
        if callee == 'audit-workflow':
            raise WorkflowError('recursive call into audit-workflow is forbidden')
    seen, visiting = set(), set()
    def walk(node: str):
        if node in visiting:
            raise WorkflowError('cyclic skill invocation graph detected')
        if node in seen:
            return
        visiting.add(node)
        for next_node in graph.get(node, ()):
            walk(next_node)
        visiting.remove(node)
        seen.add(node)
    for node in graph:
        walk(node)

def prior_ready(manifest: dict, stage: str) -> None:
    """Запрещает запуск этапа, пока необходимые предыдущие этапы не зафиксированы."""
    for previous in STAGES[: STAGES.index(stage)]:
        status = manifest['stages'][previous]['status']
        if status not in ('COMPLETE', 'PARTIAL', 'SKIPPED'):
            raise WorkflowError(f'{stage} cannot run before {previous} is resolved (currently {status})')
    if stage == 'AUDIT' and manifest['stages']['PREFLIGHT']['status'] != 'COMPLETE':
        raise WorkflowError('AUDIT requires successful PREFLIGHT')
    if stage == 'DOCS' and manifest['stages']['AUDIT']['status'] not in ('COMPLETE', 'PARTIAL'):
        raise WorkflowError('DOCS requires actual audit results')

def check_payload(manifest: dict, report: Path, obj: dict) -> None:
    """Сверяет входной JSON-результат с текущим запуском, его контрактом и разрешёнными переходами."""
    validate_schema(obj, 'stage-result')
    if obj['run_id'] != manifest['run_id']:
        raise WorkflowError('stage result run_id does not match manifest')
    if obj['status'] == 'SKIPPED' and obj['stage'] in MANDATORY:
        raise WorkflowError(f'mandatory stage {obj["stage"]} cannot be SKIPPED')
    if obj['status'] == 'SKIPPED' and obj['method'] != 'NOT_RUN':
        raise WorkflowError('SKIPPED stage must use NOT_RUN')
    if obj['status'] == 'COMPLETE' and obj['method'] == 'NOT_RUN':
        raise WorkflowError('a COMPLETE stage cannot claim NOT_RUN')
    if obj['stage'] == 'AUDIT' and obj['status'] == 'COMPLETE' and not obj['data']['checked_files']:
        raise WorkflowError('AUDIT COMPLETE requires checked_files')
    if obj['stage'] == 'DOCS' and obj['status'] == 'COMPLETE':
        stage_outputs(report, obj['output_files'], require_readme = True)
    if obj['stage'] == 'VALIDATE' and obj['status'] == 'COMPLETE':
        docs = manifest['stages']['DOCS']
        if docs['status'] != 'COMPLETE':
            raise WorkflowError('VALIDATE COMPLETE requires DOCS COMPLETE')
        verify_report(report, read_artifact(report, docs['artifact'], docs['sha256'])['output_files'], manifest['docs_checksums'])
        if not obj['data']['checks']:
            raise WorkflowError('VALIDATE COMPLETE requires explicit checks')
        if any(check['status'] != 'PASSED' for check in obj['data']['checks']):
            raise WorkflowError('VALIDATE COMPLETE cannot include failed or untested checks')
    verify_invocations(manifest, report, obj)

def record(report: Path, payload: Path) -> dict:
    """Фиксирует подтверждённый результат этапа, сначала записывая артефакт, а затем атомарно обновляя манифест."""
    report, payload = safe_path(report), safe_path(payload)
    if not payload.is_file():
        raise WorkflowError('payload must be an existing JSON file')
    if payload.stat().st_size > MAX_PAYLOAD_BYTES:
        raise WorkflowError('stage payload too large (limit 2 MiB)')
    try:
        obj = json.loads(payload.read_text('utf-8'))
    except (ValueError, OSError) as exc:
        raise WorkflowError(f'invalid payload JSON: {exc}') from exc
    validate_schema(obj, 'stage-result')
    with exclusive_lock(report):
        manifest = load_manifest(report)
        verify_source(manifest)
        stage = obj['stage']
        existing = manifest['stages'][stage]
        if existing['artifact']:
            old = read_artifact(report, existing['artifact'], existing['sha256'])
            if obj == old:
                return {'status': 'UNCHANGED', 'stage': stage, 'attempts': existing['attempts']}
        if existing['status'] not in ('PENDING', * RETRYABLE):
            raise WorkflowError(f'{stage} already resolved as {existing["status"]}; no repeated stage execution')
        if existing['attempts'] >= MAX_ATTEMPTS:
            raise WorkflowError(f'{stage} exceeded retry limit ({MAX_ATTEMPTS} total attempts)')
        prior_ready(manifest, stage)
        check_payload(manifest, report, obj)
        attempt = existing['attempts'] + 1
        relative = f'artifacts/{stage.lower()}-{attempt}.json'
        artifact_path = report / 'state' / relative
        artifact_path.parent.mkdir(parents = True, exist_ok = True)
        # Сначала записываем артефакт, потом манифест: незавершённая запись оставит неактивный файл, а не ложный статус.
        atomic_json(artifact_path, obj)
        existing['sha256'] = digest(artifact_path.read_bytes())
        if stage == 'DOCS' and obj['status'] == 'COMPLETE':
            manifest['docs_checksums'] = {name: digest((report / name).read_bytes()) for name in obj['output_files']}
        existing['status'] = obj['status']
        existing['attempts'] = attempt
        existing['artifact'] = relative
        manifest['state'] = 'RUNNING'
        manifest['updated_at'] = now()
        validate_schema(manifest, 'manifest')
        atomic_json(report / 'state' / 'manifest.json', manifest)
    return {'status': 'RECORDED', 'stage': stage, 'result': obj['status'], 'attempts': attempt}

def next_stage(manifest: dict) -> str | None:
    """Определяет первый незавершённый обязательный этап без повторного выполнения успешных проверок."""
    if manifest['state'] == 'COMPLETE':
        return None
    for stage in STAGES:
        s = manifest['stages'][stage]
        if s['status'] == 'PENDING':
            return stage
        if s['status'] in RETRYABLE and s['attempts'] < MAX_ATTEMPTS:
            return stage
        if s['status'] in ('BLOCKED', 'FAILED') and s['attempts'] >= MAX_ATTEMPTS:
            return None
    return None

def resume(report: Path) -> dict:
    """Проверяет исходники и контрольные суммы сохранённых артефактов перед продолжением прерванного аудита."""
    manifest = load_manifest(report)
    verify_source(manifest)
    if manifest['state'] == 'COMPLETE':
        docs = manifest['stages']['DOCS']
        doc_record = read_artifact(report, docs['artifact'], docs['sha256'])
        verify_report(report, doc_record['output_files'], manifest['docs_checksums'])
    return {'status': manifest['state'], 'run_id': manifest['run_id'],
            'next_stage': next_stage(manifest),
            'stages': {s: manifest['stages'][s]['status'] for s in STAGES}}

def finalize(report: Path) -> dict:
    """Выставляет итоговый статус только после проверки обязательных этапов и неизменности созданных документов."""
    with exclusive_lock(report):
        manifest = load_manifest(report)
        verify_source(manifest)
        stages = {s: manifest['stages'][s]['status'] for s in STAGES}
        if any(stages[s] == 'FAILED' for s in MANDATORY):
            status = 'FAILED'
        elif any(stages[s] == 'BLOCKED' for s in MANDATORY):
            status = 'BLOCKED'
        elif any(stages[s] != 'COMPLETE' for s in MANDATORY):
            status = 'PARTIAL'
        elif any(stages[s] in ('FAILED', 'BLOCKED', 'PENDING', 'PARTIAL') for s in ('IMPROVE', 'MODERNIZE')):
            status = 'PARTIAL'
        else:
            docs = read_artifact(report, manifest['stages']['DOCS']['artifact'], manifest['stages']['DOCS']['sha256'])
            verify_report(report, docs['output_files'], manifest['docs_checksums'])
            status = 'COMPLETE'
        manifest['state'] = status
        manifest['updated_at'] = now()
        atomic_json(report / 'state' / 'manifest.json', manifest)
    return {'status': status, 'run_id': manifest['run_id'], 'stages': stages}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description = __doc__)
    sub = parser.add_subparsers(dest = 'command', required = True)
    init_cmd = sub.add_parser('init', help = 'Create a new audit state')
    init_cmd.add_argument('--target', required = True, type = Path)
    init_cmd.add_argument('--type', required = True, choices = ['auto', 'skill', 'agent', 'command', 'mcp', 'lsp', 'hooks'])
    init_cmd.add_argument('--report-dir', required = True, type = Path)
    for name in ('record', 'resume', 'finalize'):
        p = sub.add_parser(name)
        p.add_argument('--report-dir', type = Path, required = True)
        if name == 'record':
            p.add_argument('--payload', required = True, type = Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            res = init(args.target, args.type, args.report_dir)
        elif args.command == 'record':
            res = record(args.report_dir, args.payload)
        elif args.command == 'resume':
            res = resume(args.report_dir)
        else:
            res = finalize(args.report_dir)
    except WorkflowError as exc:
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False, indent = 2))
        return 1
    print(json.dumps(res, ensure_ascii = False, indent = 2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
