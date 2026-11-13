#!/usr/bin/env python3
"""Publish reviewed Markdown reports with verified backups and in-process rollback.

This tool NEVER executes inspected code, downloads packages, deletes legacy RU.md
or TRANSLATE.md, or modifies anything outside an explicitly provided output dir.

CLI:
  python scripts/safe_writer.py --staging ./prepared-report --output ./target/audit
  python scripts/safe_writer.py --staging ./prepared-report --output ./target/audit --overwrite

The staging directory must contain README.md plus optional docs/**/*.md and
translations/**/*.md. This script requires markdown-it-py for link validation.
Use a trusted, exclusively-owned output directory: race-resistant operations
against a concurrently hostile filesystem are beyond this tool's threat model.
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
import os
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import shutil
# Импортирует модуль или имена, используемые в этом файле.
import stat
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
from datetime import datetime, timezone
# Импортирует модуль или имена, используемые в этом файле.
from uuid import uuid4

# Проверяет переносимые имена и конфликты файловых систем Windows/Linux.
from portable_names import find_collisions, assert_no_existing_aliases, is_link_or_reparse_point

# Начинает блок с контролируемой обработкой исключений.
try:
    # Импортирует модуль или имена, используемые в этом файле.
    from markdown_links import check_markdown_links
# Перехватывает указанное исключение для безопасной обработки.
except ModuleNotFoundError as exc:
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit(f'Missing documentation-writer dependency: {exc.name}. '
                     # Формирует часть выражения или передаёт аргумент в текущую операцию.
                     'See audit-docs/scripts/requirements.txt; no automatic install.') from exc


# Определяет класс и его интерфейс.
class PublishError(RuntimeError):
    # Оставляет тело блока пустым намеренно.
    pass


# Объявляет функцию sha256 и её параметры.
def sha256(data: bytes) -> str:
    # Возвращает вычисленный результат вызывающему коду.
    return hashlib.sha256(data).hexdigest()


# Объявляет функцию _assert_no_symlinks и её параметры.
def _assert_no_symlinks(path: Path):
    # Описывает назначение блока в многострочной строке документации.
    """Reject symlinks in every existing parent and target component."""
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    path = path.absolute()
    # Перебирает элементы набора для последовательной обработки.
    for part in (path, * path.parents):
        # Проверяет условие перед выполнением следующего блока.
        if is_link_or_reparse_point(part):
            # Прерывает операцию с диагностическим исключением.
            raise PublishError(f'symlink is forbidden in publish path: {part}')


# Объявляет функцию _within и её параметры.
def _within(root: Path, child: Path) -> bool:
    # Возвращает вычисленный результат вызывающему коду.
    return child.resolve(strict = False).is_relative_to(root.resolve(strict = False))


# Объявляет функцию _collect и её параметры.
def _collect(staging: Path) -> dict[Path, bytes]:
    # Проверяет условие перед выполнением следующего блока.
    if not staging.is_dir():
        # Прерывает операцию с диагностическим исключением.
        raise PublishError(f'staging directory does not exist: {staging}')
    # Вызывает функцию для выполнения операции.
    _assert_no_symlinks(staging)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    result = {}
    # Объявляет функцию fail_walk и её параметры.
    def fail_walk(err: OSError):
        # Прерывает операцию с диагностическим исключением.
        raise PublishError(f'failed to read staging directory: {err}')
    # Перебирает элементы набора для последовательной обработки.
    for directory, subdirs, files in os.walk(staging, followlinks = False, onerror = fail_walk):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        folder = Path(directory)
        # Перебирает элементы набора для последовательной обработки.
        for subdir in subdirs:
            # Вызывает функцию для выполнения операции.
            _assert_no_symlinks(folder / subdir)
        # Перебирает элементы набора для последовательной обработки.
        for filename in files:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            path = folder / filename
            # Вызывает функцию для выполнения операции.
            _assert_no_symlinks(path)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            rel = path.relative_to(staging)
            # Проверяет условие перед выполнением следующего блока.
            if not (rel == Path('README.md') or
                    # Формирует часть выражения или передаёт аргумент в текущую операцию.
                    (len(rel.parts) >= 2 and rel.parts[0] in ('docs', 'translations') and rel.suffix.lower() == '.md')):
                # Прерывает операцию с диагностическим исключением.
                raise PublishError(f'unexpected staging file (only report Markdown allowed): {rel}')
            # Проверяет условие перед выполнением следующего блока.
            if not path.is_file():
                # Прерывает операцию с диагностическим исключением.
                raise PublishError(f'not a regular staging file: {rel}')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            data = path.read_bytes()
            # Начинает блок с контролируемой обработкой исключений.
            try:
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                text = data.decode('utf-8-sig')
            # Перехватывает указанное исключение для безопасной обработки.
            except UnicodeDecodeError as exc:
                # Прерывает операцию с диагностическим исключением.
                raise PublishError(f'non-UTF-8 Markdown: {rel}') from exc
            # Проверяет условие перед выполнением следующего блока.
            if not text.strip():
                # Прерывает операцию с диагностическим исключением.
                raise PublishError(f'empty Markdown: {rel}')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result[rel] = data
    # Проверяет условие перед выполнением следующего блока.
    if Path('README.md') not in result:
        # Прерывает операцию с диагностическим исключением.
        raise PublishError('staging must contain README.md')
    # Проверяет Windows-совместимость имён файлов и директорий отчёта.
    all_entries = (entry.relative_to(staging) for entry in staging.rglob('*'))
    # Накапливает конфликты Unicode, регистра и зарезервированных имён.
    portable_errors = find_collisions(all_entries)
    # Прерывает операцию до записи, если путь нельзя перенести на Windows.
    if portable_errors:
        # Сообщает точные имена, требующие переименования.
        raise PublishError('non-portable report paths: ' + '; '.join(portable_errors))
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    link_errors, link_warnings = check_markdown_links(staging)
    # Проверяет условие перед выполнением следующего блока.
    if link_errors:
        # Прерывает операцию с диагностическим исключением.
        raise PublishError('staging contains broken local links: ' + '; '.join(link_errors))
    # Проверяет условие перед выполнением следующего блока.
    if link_warnings:
        # Прерывает операцию с диагностическим исключением.
        raise PublishError('staging contains unverifiable site-root links: ' + '; '.join(link_warnings))
    # Возвращает вычисленный результат вызывающему коду.
    return result


# Объявляет функцию _atomic_replace и её параметры.
def _atomic_replace(destination: Path, data: bytes, old_mode: int | None):
    # Описывает назначение блока в многострочной строке документации.
    """Write to sibling temp, fsync and atomically replace within one filesystem."""
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    fd, name = tempfile.mkstemp(prefix = '.audit-write-', suffix = '.tmp', dir = destination.parent)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with os.fdopen(fd, 'wb') as stream:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            stream.write(data)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            stream.flush()
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            os.fsync(stream.fileno())
        # Проверяет условие перед выполнением следующего блока.
        if old_mode is not None:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            os.chmod(name, stat.S_IMODE(old_mode))
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        os.replace(name, destination)
    # Выполняет завершающие действия независимо от результата.
    finally:
        # Проверяет условие перед выполнением следующего блока.
        if os.path.exists(name):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            os.unlink(name)


# Объявляет функцию publish и её параметры.
def publish(staging: Path, output: Path, * , overwrite: bool = False) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    staging = staging.absolute()
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    output = output.absolute()
    # Вызывает функцию для выполнения операции.
    _assert_no_symlinks(staging)
    # Вызывает функцию для выполнения операции.
    _assert_no_symlinks(output)
    # Проверяет условие перед выполнением следующего блока.
    if _within(staging, output) or _within(output, staging):
        # Прерывает операцию с диагностическим исключением.
        raise PublishError('staging and output directories must be disjoint')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    content = _collect(staging)  # validate all before writing anything
    # Проверяет конфликтующие имена в существующем выходном каталоге.
    try:
        # Не допускает совпадения имён Windows при разных именах на Linux.
        assert_no_existing_aliases(output, content.keys())
    # Преобразует ошибку переносимости в контролируемый отказ публикации.
    except ValueError as error:
        # Предотвращает частичную запись при обнаруженном конфликте.
        raise PublishError(str(error)) from error
    # Проверяет условие перед выполнением следующего блока.
    if output.exists() and not output.is_dir():
        # Прерывает операцию с диагностическим исключением.
        raise PublishError('output must be a directory')

    # Устанавливает поле existing в словаре или описании.
    existing: dict[Path, tuple[bytes, int]] = {}
    # Перебирает элементы набора для последовательной обработки.
    for rel in content:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        dest = output / rel
        # Вызывает функцию для выполнения операции.
        _assert_no_symlinks(dest)
        # Проверяет условие перед выполнением следующего блока.
        if not _within(output, dest):
            # Прерывает операцию с диагностическим исключением.
            raise PublishError(f'path escapes output: {rel}')
        # Проверяет условие перед выполнением следующего блока.
        if dest.exists():
            # Проверяет условие перед выполнением следующего блока.
            if not dest.is_file():
                # Прерывает операцию с диагностическим исключением.
                raise PublishError(f'refusing to replace non-file: {dest}')
            # Проверяет условие перед выполнением следующего блока.
            if not overwrite:
                # Прерывает операцию с диагностическим исключением.
                raise PublishError(f'file exists; use --overwrite after reviewing: {dest}')
            # Получает права существующего файла перед попыткой перезаписи.
            mode = dest.stat().st_mode
            # Предотвращает попытку замены Windows read-only файла.
            if not (stat.S_IMODE(mode) & stat.S_IWUSR):
                # Просит пользователя явно снять защиту от записи вне этого скрипта.
                raise PublishError(f'read-only destination requires manual permission change: {dest}')
            # Сохраняет байты и режим для резервной копии и отката.
            existing[rel] = (dest.read_bytes(), mode)

    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    output.mkdir(parents = True, exist_ok = True)
    # Вызывает функцию для выполнения операции.
    _assert_no_symlinks(output)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    backup_dir = None
    # Проверяет условие перед выполнением следующего блока.
    if existing:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        backup_dir = output / '.audit-backups' / f'{stamp}-{uuid4().hex[: 12]}'
        # Вызывает функцию для выполнения операции.
        _assert_no_symlinks(backup_dir)
        # Перебирает элементы набора для последовательной обработки.
        for rel, (old_data, old_mode) in existing.items():
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            target = backup_dir / rel
            # Вызывает функцию для выполнения операции.
            _assert_no_symlinks(target)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            target.parent.mkdir(parents = True, exist_ok = True)
            # Exclusive creation; a preexisting backup is never replaced.
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with target.open('xb') as f:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                f.write(old_data)
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                f.flush()
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                os.fsync(f.fileno())
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            os.chmod(target, stat.S_IMODE(old_mode))
            # Проверяет условие перед выполнением следующего блока.
            if sha256(target.read_bytes()) != sha256(old_data):
                # Прерывает операцию с диагностическим исключением.
                raise PublishError(f'backup verification failed: {target}')

    # Сохраняет или обновляет вычисленное значение для последующих операций.
    committed = []
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Перебирает элементы набора для последовательной обработки.
        for rel, data in content.items():
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            dest = output / rel
            # Вызывает функцию для выполнения операции.
            _assert_no_symlinks(dest)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            dest.parent.mkdir(parents = True, exist_ok = True)
            # Вызывает функцию для выполнения операции.
            _assert_no_symlinks(dest)
            # Вызывает функцию для выполнения операции.
            _atomic_replace(dest, data, existing[rel][1] if rel in existing else None)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            committed.append(rel)
            # Проверяет условие перед выполнением следующего блока.
            if sha256(dest.read_bytes()) != sha256(data):
                # Прерывает операцию с диагностическим исключением.
                raise PublishError(f'write verification failed: {dest}')
    # Перехватывает указанное исключение для безопасной обработки.
    except BaseException as exc:
        # Best-effort rollback. Never hide an incomplete restore.
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        restore_errors = []
        # Перебирает элементы набора для последовательной обработки.
        for rel in reversed(committed):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            dest = output / rel
            # Начинает блок с контролируемой обработкой исключений.
            try:
                # Вызывает функцию для выполнения операции.
                _assert_no_symlinks(dest)
                # Проверяет условие перед выполнением следующего блока.
                if rel in existing:
                    # Вызывает функцию для выполнения операции.
                    _atomic_replace(dest, existing[rel][0], existing[rel][1])
                    # Проверяет условие перед выполнением следующего блока.
                    if sha256(dest.read_bytes()) != sha256(existing[rel][0]):
                        # Прерывает операцию с диагностическим исключением.
                        raise PublishError(f'restored bytes mismatch: {dest}')
                # Проверяет альтернативное условие.
                elif dest.exists():
                    # Формирует часть выражения или передаёт аргумент в текущую операцию.
                    dest.unlink()
            # Перехватывает указанное исключение для безопасной обработки.
            except Exception as rollback_exc:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                restore_errors.append(str(rollback_exc))
        # Проверяет условие перед выполнением следующего блока.
        if restore_errors:
            # Прерывает операцию с диагностическим исключением.
            raise PublishError('publish failed and rollback incomplete: ' + 
                               # Формирует часть выражения или передаёт аргумент в текущую операцию.
                               '; '.join(restore_errors)) from exc
        # Прерывает операцию с диагностическим исключением.
        raise PublishError(f'publish failed; committed files rolled back: {exc}') from exc

    # Возвращает вычисленный результат вызывающему коду.
    return {
        # Устанавливает поле status в словаре или описании.
        'status': 'COMPLETE',
        # Устанавливает поле output в словаре или описании.
        'output': str(output),
        # Устанавливает поле files_written в словаре или описании.
        'files_written': [rel.as_posix() for rel in content],
        # Устанавливает поле files_replaced в словаре или описании.
        'files_replaced': [rel.as_posix() for rel in existing],
        # Устанавливает поле backups в словаре или описании.
        'backups': str(backup_dir) if backup_dir else None,
        # Устанавливает поле legacy_deleted в словаре или описании.
        'legacy_deleted': False,
    }


# Объявляет функцию main и её параметры.
def main() -> int:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    parser = argparse.ArgumentParser(description = __doc__)
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--staging', type = Path, required = True,
                        # Сохраняет или обновляет вычисленное значение для последующих операций.
                        help = 'Directory containing reviewed README.md/docs/translations')
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--output', type = Path, required = True,
                        # Сохраняет или обновляет вычисленное значение для последующих операций.
                        help = 'Explicit report-only destination (normally <target>/audit)')
    # Настраивает аргументы, параметры или состояние объекта.
    parser.add_argument('--overwrite', action = 'store_true',
                        # Сохраняет или обновляет вычисленное значение для последующих операций.
                        help = 'Explicitly permit replacing existing report docs after verified backup')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args = parser.parse_args()
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = publish(args.staging, args.output, overwrite = args.overwrite)
    # Перехватывает указанное исключение для безопасной обработки.
    except PublishError as exc:
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps({'status': 'FAILED', 'error': str(exc)}, ensure_ascii = False, indent = 2))
        # Возвращает вычисленный результат вызывающему коду.
        return 1
    # Выводит диагностическую информацию о результате выполнения.
    print(json.dumps(result, ensure_ascii = False, indent = 2))
    # Возвращает вычисленный результат вызывающему коду.
    return 0

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit(main())
