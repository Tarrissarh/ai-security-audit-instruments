#!/usr/bin/env python3
"""Publish reviewed Markdown reports with verified backups and in-process rollback.

This tool NEVER executes inspected code, downloads packages, deletes legacy RU.md
or TRANSLATE.md, or modifies anything outside an explicitly provided output dir.

CLI:
  python scripts/safe_writer.py --staging ./prepared-report --output ./target/audit
  python scripts/safe_writer.py --staging ./prepared-report --output ./target/audit --overwrite

The staging directory must contain README.md plus optional docs/**/*.md,
translations/**/*.md, findings.json and report.sarif. This script requires
markdown-it-py for link validation.
Use a trusted, exclusively-owned output directory: race-resistant operations
against a concurrently hostile filesystem are beyond this tool's threat model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

from portable_names import find_collisions, assert_no_existing_aliases, is_link_or_reparse_point

try:
    from markdown_links import check_markdown_links
except ModuleNotFoundError as exc:
    raise SystemExit(f'Missing documentation-writer dependency: {exc.name}. '
                     'See audit-docs/scripts/requirements.txt; no automatic install.') from exc

class PublishError(RuntimeError):
    pass

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _assert_no_symlinks(path: Path):
    """Reject symlinks in every existing parent and target component."""
    path = path.absolute()
    for part in (path, * path.parents):
        if is_link_or_reparse_point(part):
            raise PublishError(f'symlink is forbidden in publish path: {part}')

def _within(root: Path, child: Path) -> bool:
    """Проверяет, что разрешённый путь остаётся в целевой директории даже при вложенных каталогах."""
    return child.resolve(strict = False).is_relative_to(root.resolve(strict = False))

def _is_report_file(rel: Path) -> bool:
    """Допустимые выходные файлы: README.md, docs/**, translations/**, findings.json, report.sarif."""
    if rel in (Path('README.md'), Path('findings.json'), Path('report.sarif')):
        return True
    return len(rel.parts) >= 2 and rel.parts[0] in ('docs', 'translations') and rel.suffix.lower() == '.md'

def _collect(staging: Path) -> dict[Path, bytes]:
    """Собирает документы из staging как исходные байты, сохраняя UTF-8/BOM и CRLF без неявной нормализации."""
    if not staging.is_dir():
        raise PublishError(f'staging directory does not exist: {staging}')
    _assert_no_symlinks(staging)
    result = {}
    def fail_walk(err: OSError):
        raise PublishError(f'failed to read staging directory: {err}')
    for directory, subdirs, files in os.walk(staging, followlinks = False, onerror = fail_walk):
        folder = Path(directory)
        for subdir in subdirs:
            _assert_no_symlinks(folder / subdir)
        for filename in files:
            path = folder / filename
            _assert_no_symlinks(path)
            rel = path.relative_to(staging)
            if not _is_report_file(rel):
                raise PublishError(f'unexpected staging file (only report files allowed): {rel}')
            if not path.is_file():
                raise PublishError(f'not a regular staging file: {rel}')
            data = path.read_bytes()
            try:
                text = data.decode('utf-8-sig')
            except UnicodeDecodeError as exc:
                raise PublishError(f'non-UTF-8 file: {rel}') from exc
            if not text.strip():
                raise PublishError(f'empty file: {rel}')
            result[rel] = data
    if Path('README.md') not in result:
        raise PublishError('staging must contain README.md')
    all_entries = (entry.relative_to(staging) for entry in staging.rglob('*'))
    portable_errors = find_collisions(all_entries)
    if portable_errors:
        raise PublishError('non-portable report paths: ' + '; '.join(portable_errors))
    link_errors, link_warnings = check_markdown_links(staging)
    if link_errors:
        raise PublishError('staging contains broken local links: ' + '; '.join(link_errors))
    if link_warnings:
        raise PublishError('staging contains unverifiable site-root links: ' + '; '.join(link_warnings))
    return result

def _atomic_replace(destination: Path, data: bytes, old_mode: int | None):
    """Write to sibling temp, fsync and atomically replace within one filesystem."""
    fd, name = tempfile.mkstemp(prefix = '.audit-write-', suffix = '.tmp', dir = destination.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if old_mode is not None:
            os.chmod(name, stat.S_IMODE(old_mode))
        os.replace(name, destination)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def publish(staging: Path, output: Path, * , overwrite: bool = False) -> dict:
    """Проводит предвалидацию всех документов, защищает существующие файлы, создаёт резервные копии и откатывает частичные изменения при ошибке."""
    staging = staging.absolute()
    output = output.absolute()
    _assert_no_symlinks(staging)
    _assert_no_symlinks(output)
    if _within(staging, output) or _within(output, staging):
        raise PublishError('staging and output directories must be disjoint')
    content = _collect(staging)  # validate all before writing anything
    try:
        assert_no_existing_aliases(output, content.keys())
    except ValueError as error:
        raise PublishError(str(error)) from error
    if output.exists() and not output.is_dir():
        raise PublishError('output must be a directory')

    existing: dict[Path, tuple[bytes, int]] = {}
    for rel in content:
        dest = output / rel
        _assert_no_symlinks(dest)
        if not _within(output, dest):
            raise PublishError(f'path escapes output: {rel}')
        if dest.exists():
            if not dest.is_file():
                raise PublishError(f'refusing to replace non-file: {dest}')
            if not overwrite:
                raise PublishError(f'file exists; use --overwrite after reviewing: {dest}')
            mode = dest.stat().st_mode
            if not (stat.S_IMODE(mode) & stat.S_IWUSR):
                raise PublishError(f'read-only destination requires manual permission change: {dest}')
            existing[rel] = (dest.read_bytes(), mode)

    output.mkdir(parents = True, exist_ok = True)
    _assert_no_symlinks(output)
    backup_dir = None
    if existing:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup_dir = output / '.audit-backups' / f'{stamp}-{uuid4().hex[: 12]}'
        _assert_no_symlinks(backup_dir)
        for rel, (old_data, old_mode) in existing.items():
            target = backup_dir / rel
            _assert_no_symlinks(target)
            target.parent.mkdir(parents = True, exist_ok = True)
            # Создаём резервные копии исключительно новыми файлами, без перезаписи предыдущих копий.
            with target.open('xb') as f:
                f.write(old_data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(target, stat.S_IMODE(old_mode))
            if sha256(target.read_bytes()) != sha256(old_data):
                raise PublishError(f'backup verification failed: {target}')

    committed = []
    try:
        for rel, data in content.items():
            dest = output / rel
            _assert_no_symlinks(dest)
            dest.parent.mkdir(parents = True, exist_ok = True)
            _assert_no_symlinks(dest)
            _atomic_replace(dest, data, existing[rel][1] if rel in existing else None)
            committed.append(rel)
            if sha256(dest.read_bytes()) != sha256(data):
                raise PublishError(f'write verification failed: {dest}')
    except BaseException as exc:
        # При сбое откатываем доступные изменения и явно сообщаем, если восстановление получилось неполным.
        restore_errors = []
        for rel in reversed(committed):
            dest = output / rel
            try:
                _assert_no_symlinks(dest)
                if rel in existing:
                    _atomic_replace(dest, existing[rel][0], existing[rel][1])
                    if sha256(dest.read_bytes()) != sha256(existing[rel][0]):
                        raise PublishError(f'restored bytes mismatch: {dest}')
                elif dest.exists():
                    dest.unlink()
            except Exception as rollback_exc:
                restore_errors.append(str(rollback_exc))
        if restore_errors:
            raise PublishError('publish failed and rollback incomplete: ' + 
                               '; '.join(restore_errors)) from exc
        raise PublishError(f'publish failed; committed files rolled back: {exc}') from exc

    return {
        'status': 'COMPLETE',
        'output': str(output),
        'files_written': [rel.as_posix() for rel in content],
        'files_replaced': [rel.as_posix() for rel in existing],
        'backups': str(backup_dir) if backup_dir else None,
        'legacy_deleted': False,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--staging', type = Path, required = True,
                        help = 'Directory containing reviewed README.md/docs/translations')
    parser.add_argument('--output', type = Path, required = True,
                        help = 'Explicit report-only destination (normally <target>/audit)')
    parser.add_argument('--overwrite', action = 'store_true',
                        help = 'Explicitly permit replacing existing report docs after verified backup')
    args = parser.parse_args()
    try:
        result = publish(args.staging, args.output, overwrite = args.overwrite)
    except PublishError as exc:
        print(json.dumps({'status': 'FAILED', 'error': str(exc)}, ensure_ascii = False, indent = 2))
        return 1
    print(json.dumps(result, ensure_ascii = False, indent = 2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
