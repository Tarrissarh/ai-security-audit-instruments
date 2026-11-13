#!/usr/bin/env python3
"""Safe, offline project-level installer and structural compatibility probes.

NOT an AI-client integration harness: never executes client CLIs, untrusted project
code, installed skill scripts or external network commands. Client runtime remains
NOT_TESTED until independent real-client evidence is collected.
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
import re
# Импортирует модуль или имена, используемые в этом файле.
import shutil
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path

# Проверяет переносимость имён в исходном комплекте и целевом каталоге.
from portable_names import find_collisions, assert_no_existing_aliases, is_link_or_reparse_point

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Сохраняет или обновляет вычисленное значение для последующих операций.
SKILLS_ROOT = ROOT / "skills"
# Сохраняет или обновляет вычисленное значение для последующих операций.
IDS = (
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'audit-workflow', 'audit-skill', 'audit-agent', 'audit-command',
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'audit-mcp', 'audit-lsp', 'audit-hooks', 'audit-docs',
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'audit-improve', 'audit-modernize', 'ai-tool-generator'
)
# Сохраняет или обновляет вычисленное значение для последующих операций.
PLATFORMS = {
    # Устанавливает поле opencode в словаре или описании.
    'opencode': {'native': '.opencode/skills', 'shared': '.agents/skills', 'binary': 'opencode'},
    # Устанавливает поле deepseek-harness в словаре или описании.
    'deepseek-harness': {'native': '.dsh/skills', 'shared': '.agents/skills', 'binary': 'dsh'},
    # Устанавливает поле claude-code в словаре или описании.
    'claude-code': {'native': '.claude/skills', 'shared': None, 'binary': 'claude'},
    # Устанавливает поле codex в словаре или описании.
    'codex': {'native': '.agents/skills', 'shared': '.agents/skills', 'binary': 'codex'},
    # Устанавливает поле cursor в словаре или описании.
    'cursor': {'native': '.cursor/skills', 'shared': '.agents/skills', 'binary': 'cursor'},
}
# Сохраняет или обновляет вычисленное значение для последующих операций.
CANDIDATES = {
    # Устанавливает поле opencode в словаре или описании.
    'opencode': ['.opencode/skills', '.agents/skills', '.claude/skills'],
    # Устанавливает поле deepseek-harness в словаре или описании.
    'deepseek-harness': ['.dsh/skills', '.agents/skills'],
    # Устанавливает поле claude-code в словаре или описании.
    'claude-code': ['.claude/skills'],
    # Устанавливает поле codex в словаре или описании.
    'codex': ['.agents/skills'],
    # Устанавливает поле cursor в словаре или описании.
    'cursor': ['.cursor/skills', '.agents/skills', '.claude/skills', '.codex/skills'],
}
# Сохраняет или обновляет вычисленное значение для последующих операций.
NAME = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


# Объявляет функцию _read_frontmatter и её параметры.
def _read_frontmatter(path: Path) -> dict:
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Импортирует модуль или имена, используемые в этом файле.
        import yaml
    # Перехватывает указанное исключение для безопасной обработки.
    except ImportError as exc:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('PyYAML is needed for frontmatter checking; see requirements-validation.txt') from exc
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    content = path.read_text(encoding = 'utf-8-sig')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    parts = content.splitlines()
    # Проверяет условие перед выполнением следующего блока.
    if not parts or parts[0].strip() != '---':
        # Прерывает операцию с диагностическим исключением.
        raise ValueError(f'{path}: missing YAML frontmatter')
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        end = next(i for i in range(1, len(parts)) if parts[i].strip() == '---')
    # Перехватывает указанное исключение для безопасной обработки.
    except StopIteration as exc:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError(f'{path}: missing YAML closing separator') from exc
    # Bundle validator (v5.1) rejects duplicate keys; reuse its strict parser.
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    sys.path.insert(0, str(ROOT / 'scripts'))
    # Импортирует модуль или имена, используемые в этом файле.
    from validate_skills import read_frontmatter
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    fm, errors = read_frontmatter(path)
    # Проверяет условие перед выполнением следующего блока.
    if errors:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError(f'{path}: ' + ', '.join(errors))
    # Возвращает вычисленный результат вызывающему коду.
    return fm


# Объявляет функцию validate_bundle и её параметры.
def validate_bundle(bundle: Path = SKILLS_ROOT) -> list[str]:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    bundle = bundle / "skills" if (bundle / "skills").is_dir() else bundle
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    errors = []
    # Перебирает элементы набора для последовательной обработки.
    for name in IDS:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = bundle / name / 'SKILL.md'
        # Проверяет условие перед выполнением следующего блока.
        if not p.is_file() or p.is_symlink():
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append(f'{name}: missing/non-regular SKILL.md')
            # Переходит к следующей итерации цикла.
            continue
        # Начинает блок с контролируемой обработкой исключений.
        try:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            fm = _read_frontmatter(p)
            # Проверяет условие перед выполнением следующего блока.
            if fm['name'] != name or not NAME.fullmatch(name):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append(f'{name}: invalid or mismatched frontmatter.name')
            # Проверяет условие перед выполнением следующего блока.
            if not isinstance(fm.get('description'), str) or not fm['description'].strip():
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append(f'{name}: missing description')
            # Проверяет условие перед выполнением следующего блока.
            if name == 'ai-tool-generator' and fm.get('disable-model-invocation') != 'true':
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append('ai-tool-generator: must not be model-invocable')
        # Перехватывает указанное исключение для безопасной обработки.
        except (ValueError, OSError) as exc:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append(str(exc))
        # Перебирает элементы набора для последовательной обработки.
        for nested in (bundle / name).rglob('*'):
            # Проверяет условие перед выполнением следующего блока.
            if is_link_or_reparse_point(nested):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append(f'{name}: source contains symbolic link {nested.relative_to(bundle)}')
    # Проверяет все имена, включая каталоги, на запрещённые имена Windows.
    entries = (nested.relative_to(bundle) for nested in bundle.rglob('*'))
    # Добавляет ошибки коллизий регистра и Unicode к общим ошибкам пакета.
    errors.extend(find_collisions(entries))
    # Возвращает вычисленный результат вызывающему коду.
    return errors


# Объявляет функцию _safe_project и её параметры.
def _safe_project(project: Path) -> Path:
    # Проверяет условие перед выполнением следующего блока.
    if not project.exists() or not project.is_dir():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('project must be an existing directory')
    # Проверяет условие перед выполнением следующего блока.
    if is_link_or_reparse_point(project):
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('project root may not be a symbolic link')
    # Возвращает вычисленный результат вызывающему коду.
    return project.resolve()


# Объявляет функцию _reject_symlink_ancestors и её параметры.
def _reject_symlink_ancestors(root: Path, target: Path) -> None:
    # Проверяет условие перед выполнением следующего блока.
    if not target.is_relative_to(root):
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('destination would leave project root')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    current = root
    # Перебирает элементы набора для последовательной обработки.
    for part in target.relative_to(root).parts:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        current = current / part
        # Проверяет условие перед выполнением следующего блока.
        if is_link_or_reparse_point(current):
            # Прерывает операцию с диагностическим исключением.
            raise ValueError(f'symbolic-link path component is forbidden: {current}')


# Объявляет функцию target_root и её параметры.
def target_root(platform: str, layout: str) -> Path:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    rel = PLATFORMS[platform][layout]
    # Проверяет условие перед выполнением следующего блока.
    if rel is None:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError(f'{platform} has no documented shared skills root in this package')
    # Возвращает вычисленный результат вызывающему коду.
    return Path(rel)


# Объявляет функцию _scan и её параметры.
def _scan(root: Path, platform: str) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    result = {}
    # Перебирает элементы набора для последовательной обработки.
    for rel in CANDIDATES[platform]:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        parent = root / rel
        # Перебирает элементы набора для последовательной обработки.
        for name in IDS:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            file = parent / name / 'SKILL.md'
            # Проверяет условие перед выполнением следующего блока.
            if file.is_file():
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                result.setdefault(name, []).append(str(file.relative_to(root)))
    # Возвращает вычисленный результат вызывающему коду.
    return result


# Объявляет функцию stage и её параметры.
def stage(platform: str, project: Path, layout: str = 'native', apply: bool = False,
          # Устанавливает поле bundle в словаре или описании.
          bundle: Path = SKILLS_ROOT) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    bundle = bundle / "skills" if (bundle / "skills").is_dir() else bundle
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = _safe_project(project)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    destination = root / target_root(platform, layout)
    # Вызывает функцию для выполнения операции.
    _reject_symlink_ancestors(root, destination)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    issues = validate_bundle(bundle)
    # Never merge with existing identities from any other path the client may scan.
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    scanned = _scan(root, platform)
    # Проверяет существующие имена с учётом нечувствительной к регистру Windows ФС.
    try:
        # Проверяет псевдонимы имён до создания файлов и резервных каталогов.
        assert_no_existing_aliases(root, (target_root(platform, layout) / name for name in IDS))
    # Превращает обнаруженный конфликт в блокирующую ошибку плана установки.
    except ValueError as error:
        # Добавляет сообщение, не изменяя целевой проект.
        issues.append(str(error))
    # Перебирает элементы набора для последовательной обработки.
    for name in IDS:
        # Проверяет условие перед выполнением следующего блока.
        if name in scanned:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'duplicate/existing skill {name}: {scanned[name]}')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        candidate = destination / name
        # Вызывает функцию для выполнения операции.
        _reject_symlink_ancestors(root, candidate)
        # Проверяет условие перед выполнением следующего блока.
        if candidate.exists() or candidate.is_symlink():
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'destination exists: {candidate}')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    result = {
        # Устанавливает поле platform в словаре или описании.
        'platform': platform, 'destination': str(destination), 'layout': layout,
        # Устанавливает поле mode в словаре или описании.
        'mode': 'APPLY' if apply else 'DRY_RUN', 'errors': issues,
        # Устанавливает поле skills_planned в словаре или описании.
        'skills_planned': list(IDS), 'client_runtime': 'NOT_TESTED',
        # Устанавливает поле status в словаре или описании.
        'status': 'BLOCKED' if issues else 'READY',
    }
    # Проверяет условие перед выполнением следующего блока.
    if issues or not apply:
        # Возвращает вычисленный результат вызывающему коду.
        return result
    # Build outside final paths. Only trusted bundle files copied; source symlinks denied.
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    destination.mkdir(parents = True, exist_ok = True)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    staging = Path(tempfile.mkdtemp(prefix = '.skills-stage-', dir = destination))
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    moved = []
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Перебирает элементы набора для последовательной обработки.
        for name in IDS:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            shutil.copytree(bundle / name, staging / name, symlinks = False)
            # Проверяет условие перед выполнением следующего блока.
            if not (staging / name / 'SKILL.md').is_file():
                # Прерывает операцию с диагностическим исключением.
                raise ValueError(f'{name}: staged SKILL.md missing')
        # Перебирает элементы набора для последовательной обработки.
        for name in IDS:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            os.replace(staging / name, destination / name)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            moved.append(destination / name)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        result['status'] = 'LOCAL_INSTALL_PASS'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        result['installed'] = len(moved)
    # Перехватывает указанное исключение для безопасной обработки.
    except Exception:
        # Перебирает элементы набора для последовательной обработки.
        for item in reversed(moved):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            shutil.rmtree(item)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        raise
    # Выполняет завершающие действия независимо от результата.
    finally:
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        shutil.rmtree(staging, ignore_errors = True)
    # Возвращает вычисленный результат вызывающему коду.
    return result


# Объявляет функцию inspect и её параметры.
def inspect(platform: str, project: Path) -> dict:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = _safe_project(project)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    scanned = _scan(root, platform)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    duplicates = {k: v for k, v in scanned.items() if len(v) > 1}
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    missing = sorted(set(IDS) - set(scanned))
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    malformed = []
    # Перебирает элементы набора для последовательной обработки.
    for name, paths in scanned.items():
        # Перебирает элементы набора для последовательной обработки.
        for rel in paths:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = root / rel
            # Начинает блок с контролируемой обработкой исключений.
            try:
                # Проверяет условие перед выполнением следующего блока.
                if p.is_symlink():
                    # Прерывает операцию с диагностическим исключением.
                    raise ValueError('symlinked SKILL.md')
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                fm = _read_frontmatter(p)
                # Проверяет условие перед выполнением следующего блока.
                if fm.get('name') != name:
                    # Прерывает операцию с диагностическим исключением.
                    raise ValueError('frontmatter ID mismatch')
                # Проверяет условие перед выполнением следующего блока.
                if name == 'ai-tool-generator' and fm.get('disable-model-invocation') != 'true':
                    # Прерывает операцию с диагностическим исключением.
                    raise ValueError('generator lacks explicit model-invocation guard')
            # Перехватывает указанное исключение для безопасной обработки.
            except (ValueError, OSError) as exc:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                malformed.append(f'{rel}: {exc}')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    binary = PLATFORMS[platform]['binary']
    # Cursor documents `agent` CLI; `cursor` alone is not a reliable check.
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    binaries = ('agent', 'cursor-agent') if platform == 'cursor' else (binary,)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    command = next((shutil.which(name) for name in binaries if shutil.which(name)), None)
    # Проверяет условие перед выполнением следующего блока.
    if platform == 'deepseek-harness':
        # Finding a binary is not proof that the 3 plugin packages are mounted.
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        preconditions = ['dsh-skill registry mounted', 'dsh-skill-filesystem provider mounted',
                         # Формирует часть выражения или передаёт аргумент в текущую операцию.
                         'dsh-tool-skill consumer mounted']
    # Выполняет ветку, когда предыдущие условия не сработали.
    else:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        preconditions = ['host skill registry/permissions enabled', 'workspace visible to client']
    # Возвращает вычисленный результат вызывающему коду.
    return {
        # Устанавливает поле platform в словаре или описании.
        'platform': platform, 'project': str(root), 'found': scanned,
        # Устанавливает поле missing в словаре или описании.
        'missing': missing, 'duplicates': duplicates, 'invalid': malformed,
        # Устанавливает поле client_binary в словаре или описании.
        'client_binary': command or None, 'client_runtime': 'NOT_TESTED',
        # Устанавливает поле client_binary_identity в словаре или описании.
        'client_binary_identity': 'UNVERIFIED',
        # Устанавливает поле preconditions_not_verified в словаре или описании.
        'preconditions_not_verified': preconditions,
        # Устанавливает поле local_discovery_static в словаре или описании.
        'local_discovery_static': 'PASS' if not(missing or duplicates or malformed) else 'FAIL',
        # Устанавливает поле disclaimer в словаре или описании.
        'disclaimer': 'Directory layout inspection is not a real client loader test.',
    }


# Объявляет функцию smoke и её параметры.
def smoke(platform: str, bundle: Path = SKILLS_ROOT) -> dict:
    # Открывает управляемый контекст и гарантирует его корректное завершение.
    with tempfile.TemporaryDirectory(prefix = 'audit-skills-v60-') as d:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        project = Path(d)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (project / '.git').mkdir()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        staged = stage(platform, project, bundle = bundle, apply = True)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        checked = inspect(platform, project)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        files = [p for name in IDS for p in (project / target_root(platform, 'native') / name).rglob('*') if p.is_file()]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        hash_bytes = hashlib.sha256(''.join(sorted(p.relative_to(project).as_posix() + ':' + hashlib.sha256(p.read_bytes()).hexdigest() for p in files)).encode()).hexdigest()
        # Возвращает вычисленный результат вызывающему коду.
        return {
            # Устанавливает поле platform в словаре или описании.
            'platform': platform, 'install': staged['status'], 'local_discovery': checked['local_discovery_static'],
            # Устанавливает поле skill_count в словаре или описании.
            'skill_count': len(checked['found']), 'file_count': len(files), 'file_manifest_sha256': hash_bytes,
            # Устанавливает поле real_client_discovery в словаре или описании.
            'real_client_discovery': 'NOT_TESTED', 'real_client_activation': 'NOT_TESTED',
            # Устанавливает поле real_client_orchestration в словаре или описании.
            'real_client_orchestration': 'NOT_TESTED', 'real_client_safety': 'NOT_TESTED',
        }


# Объявляет функцию main и её параметры.
def main(argv = None) -> int:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    ap = argparse.ArgumentParser(description = __doc__)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    sp = ap.add_subparsers(dest = 'action', required = True)
    # Перебирает элементы набора для последовательной обработки.
    for action in ('stage', 'inspect', 'smoke'):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = sp.add_parser(action)
        # Настраивает аргументы, параметры или состояние объекта.
        p.add_argument('--platform', required = True, choices = sorted(PLATFORMS))
        # Проверяет условие перед выполнением следующего блока.
        if action != 'smoke':
            # Настраивает аргументы, параметры или состояние объекта.
            p.add_argument('--project', required = True, type = Path)
        # Проверяет условие перед выполнением следующего блока.
        if action == 'stage':
            # Настраивает аргументы, параметры или состояние объекта.
            p.add_argument('--layout', choices = ('native', 'shared'), default = 'native')
            # Настраивает аргументы, параметры или состояние объекта.
            p.add_argument('--apply', action = 'store_true', help = 'Explicitly allow copying files into specified project')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args = ap.parse_args(argv)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = {'stage': stage, 'inspect': inspect, 'smoke': smoke}[args.action](args.platform, * ( [args.project, args.layout, args.apply] if args.action == 'stage' else [args.project] if args.action == 'inspect' else []))
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps(result, ensure_ascii = False, indent = 2))
        # Проверяет условие перед выполнением следующего блока.
        if result.get('errors') or result.get('local_discovery_static') == 'FAIL':
            # Возвращает вычисленный результат вызывающему коду.
            return 2
        # Возвращает вычисленный результат вызывающему коду.
        return 0
    # Перехватывает указанное исключение для безопасной обработки.
    except (ValueError, OSError) as exc:
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False), file = sys.stderr)
        # Возвращает вычисленный результат вызывающему коду.
        return 1

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit(main())
