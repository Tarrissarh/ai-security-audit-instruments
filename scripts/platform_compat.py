#!/usr/bin/env python3
"""Safe, offline project-level installer and structural compatibility probes.

NOT an AI-client integration harness: never executes client CLIs, untrusted project
code, installed skill scripts or external network commands. Client runtime remains
NOT_TESTED until independent real-client evidence is collected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from portable_names import find_collisions, assert_no_existing_aliases, is_link_or_reparse_point

ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
IDS = (
    'audit-workflow', 'audit-skill', 'audit-agent', 'audit-command',
    'audit-mcp', 'audit-lsp', 'audit-hooks', 'audit-docs',
    'audit-improve', 'audit-modernize', 'ai-tool-generator'
)
PLATFORMS = {
    'opencode': {'native': '.opencode/skills', 'shared': '.agents/skills', 'binary': 'opencode'},
    'deepseek-harness': {'native': '.dsh/skills', 'shared': '.agents/skills', 'binary': 'dsh'},
    'claude-code': {'native': '.claude/skills', 'shared': None, 'binary': 'claude'},
    'codex': {'native': '.agents/skills', 'shared': '.agents/skills', 'binary': 'codex'},
    'cursor': {'native': '.cursor/skills', 'shared': '.agents/skills', 'binary': 'cursor'},
}
CANDIDATES = {
    'opencode': ['.opencode/skills', '.agents/skills', '.claude/skills'],
    'deepseek-harness': ['.dsh/skills', '.agents/skills'],
    'claude-code': ['.claude/skills'],
    'codex': ['.agents/skills'],
    'cursor': ['.cursor/skills', '.agents/skills', '.claude/skills', '.codex/skills'],
}
NAME = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

def _read_frontmatter(path: Path) -> dict:
    """Читает метаданные SKILL.md через общий строгий YAML-парсер. Отказывает при некорректных или неоднозначных полях до установки."""
    try:
        import yaml
    except ImportError as exc:
        raise ValueError('PyYAML is needed for frontmatter checking; see requirements-validation.txt') from exc
    content = path.read_text(encoding = 'utf-8-sig')
    parts = content.splitlines()
    if not parts or parts[0].strip() != '---':
        raise ValueError(f'{path}: missing YAML frontmatter')
    try:
        end = next(i for i in range(1, len(parts)) if parts[i].strip() == '---')
    except StopIteration as exc:
        raise ValueError(f'{path}: missing YAML closing separator') from exc
    # Общий строгий парсер запрещает повторяющиеся YAML-ключи в обоих режимах проверки.
    sys.path.insert(0, str(ROOT / 'scripts'))
    from validate_skills import read_frontmatter
    fm, errors = read_frontmatter(path)
    if errors:
        raise ValueError(f'{path}: ' + ', '.join(errors))
    return fm

def validate_bundle(bundle: Path = SKILLS_ROOT) -> list[str]:
    """Проверяет обязательные скиллы, метаданные и небезопасные ссылки; обнаруживает коллизии имён для переносимости между ОС."""
    bundle = bundle / "skills" if (bundle / "skills").is_dir() else bundle
    errors = []
    for name in IDS:
        p = bundle / name / 'SKILL.md'
        if not p.is_file() or p.is_symlink():
            errors.append(f'{name}: missing/non-regular SKILL.md')
            continue
        try:
            fm = _read_frontmatter(p)
            if fm['name'] != name or not NAME.fullmatch(name):
                errors.append(f'{name}: invalid or mismatched frontmatter.name')
            if not isinstance(fm.get('description'), str) or not fm['description'].strip():
                errors.append(f'{name}: missing description')
            if name == 'ai-tool-generator' and fm.get('disable-model-invocation') != 'true':
                errors.append('ai-tool-generator: must not be model-invocable')
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
        for nested in (bundle / name).rglob('*'):
            if is_link_or_reparse_point(nested):
                errors.append(f'{name}: source contains symbolic link {nested.relative_to(bundle)}')
    entries = (nested.relative_to(bundle) for nested in bundle.rglob('*'))
    errors.extend(find_collisions(entries))
    return errors

def _safe_project(project: Path) -> Path:
    """Принимает только существующий обычный каталог проекта; запрещает использовать ссылку как корень установки."""
    if not project.exists() or not project.is_dir():
        raise ValueError('project must be an existing directory')
    if is_link_or_reparse_point(project):
        raise ValueError('project root may not be a symbolic link')
    return project.resolve()

def _reject_symlink_ancestors(root: Path, target: Path) -> None:
    """Не допускает выход из проекта и перенаправление через символические ссылки в существующих родительских каталогах."""
    if not target.is_relative_to(root):
        raise ValueError('destination would leave project root')
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        if is_link_or_reparse_point(current):
            raise ValueError(f'symbolic-link path component is forbidden: {current}')

def target_root(platform: str, layout: str) -> Path:
    """Определяет поддерживаемое расположение Skills для платформы и выбранной схемы установки."""
    rel = PLATFORMS[platform][layout]
    if rel is None:
        raise ValueError(f'{platform} has no documented shared skills root in this package')
    return Path(rel)

def _scan(root: Path, platform: str) -> dict:
    """Ищет уже установленные идентификаторы скиллов, чтобы избежать конфликта с каталогами, сканируемыми клиентом."""
    result = {}
    for rel in CANDIDATES[platform]:
        parent = root / rel
        for name in IDS:
            file = parent / name / 'SKILL.md'
            if file.is_file():
                result.setdefault(name, []).append(str(file.relative_to(root)))
    return result

def stage(platform: str, project: Path, layout: str = 'native', apply: bool = False,
          bundle: Path = SKILLS_ROOT) -> dict:
    """Сначала планирует безопасную установку; только по --apply копирует проверенные скиллы и запрещает перезапись существующих."""
    bundle = bundle / "skills" if (bundle / "skills").is_dir() else bundle
    root = _safe_project(project)
    destination = root / target_root(platform, layout)
    _reject_symlink_ancestors(root, destination)
    issues = validate_bundle(bundle)
    # Не объединяем одноимённые Skills из разных корней: клиент может загрузить не ту реализацию.
    scanned = _scan(root, platform)
    try:
        assert_no_existing_aliases(root, (target_root(platform, layout) / name for name in IDS))
    except ValueError as error:
        issues.append(str(error))
    for name in IDS:
        if name in scanned:
            issues.append(f'duplicate/existing skill {name}: {scanned[name]}')
        candidate = destination / name
        _reject_symlink_ancestors(root, candidate)
        if candidate.exists() or candidate.is_symlink():
            issues.append(f'destination exists: {candidate}')
    result = {
        'platform': platform, 'destination': str(destination), 'layout': layout,
        'mode': 'APPLY' if apply else 'DRY_RUN', 'errors': issues,
        'skills_planned': list(IDS), 'client_runtime': 'NOT_TESTED',
        'status': 'BLOCKED' if issues else 'READY',
    }
    if issues or not apply:
        return result
    # Сначала готовим изолированную копию, затем переносим проверенные файлы: ссылки исходников запрещены.
    destination.mkdir(parents = True, exist_ok = True)
    staging = Path(tempfile.mkdtemp(prefix = '.skills-stage-', dir = destination))
    moved = []
    try:
        for name in IDS:
            shutil.copytree(bundle / name, staging / name, symlinks = False)
            if not (staging / name / 'SKILL.md').is_file():
                raise ValueError(f'{name}: staged SKILL.md missing')
        for name in IDS:
            os.replace(staging / name, destination / name)
            moved.append(destination / name)
        result['status'] = 'LOCAL_INSTALL_PASS'
        result['installed'] = len(moved)
    except Exception:
        for item in reversed(moved):
            shutil.rmtree(item)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors = True)
    return result

def inspect(platform: str, project: Path) -> dict:
    """Проверяет обнаруживаемые каталоги проекта без запуска AI-клиента; результат не подтверждает реальную активацию."""
    root = _safe_project(project)
    scanned = _scan(root, platform)
    duplicates = {k: v for k, v in scanned.items() if len(v) > 1}
    missing = sorted(set(IDS) - set(scanned))
    malformed = []
    for name, paths in scanned.items():
        for rel in paths:
            p = root / rel
            try:
                if p.is_symlink():
                    raise ValueError('symlinked SKILL.md')
                fm = _read_frontmatter(p)
                if fm.get('name') != name:
                    raise ValueError('frontmatter ID mismatch')
                if name == 'ai-tool-generator' and fm.get('disable-model-invocation') != 'true':
                    raise ValueError('generator lacks explicit model-invocation guard')
            except (ValueError, OSError) as exc:
                malformed.append(f'{rel}: {exc}')
    binary = PLATFORMS[platform]['binary']
    # Для Cursor проверяем исполняемый агент, а не произвольную команду cursor из PATH.
    binaries = ('agent', 'cursor-agent') if platform == 'cursor' else (binary,)
    command = next((shutil.which(name) for name in binaries if shutil.which(name)), None)
    if platform == 'deepseek-harness':
        # Наличие бинарного файла не подтверждает, что подключены все компоненты платформы.
        preconditions = ['dsh-skill registry mounted', 'dsh-skill-filesystem provider mounted',
                         'dsh-tool-skill consumer mounted']
    else:
        preconditions = ['host skill registry/permissions enabled', 'workspace visible to client']
    return {
        'platform': platform, 'project': str(root), 'found': scanned,
        'missing': missing, 'duplicates': duplicates, 'invalid': malformed,
        'client_binary': command or None, 'client_runtime': 'NOT_TESTED',
        'client_binary_identity': 'UNVERIFIED',
        'preconditions_not_verified': preconditions,
        'local_discovery_static': 'PASS' if not(missing or duplicates or malformed) else 'FAIL',
        'disclaimer': 'Directory layout inspection is not a real client loader test.',
    }

def smoke(platform: str, bundle: Path = SKILLS_ROOT) -> dict:
    """Проверяет структуру набора на локальном временном проекте без выполнения недоверенного кода."""
    with tempfile.TemporaryDirectory(prefix = 'audit-skills-smoke-') as d:
        project = Path(d)
        (project / '.git').mkdir()
        staged = stage(platform, project, bundle = bundle, apply = True)
        checked = inspect(platform, project)
        files = [p for name in IDS for p in (project / target_root(platform, 'native') / name).rglob('*') if p.is_file()]
        hash_bytes = hashlib.sha256(''.join(sorted(p.relative_to(project).as_posix() + ':' + hashlib.sha256(p.read_bytes()).hexdigest() for p in files)).encode()).hexdigest()
        return {
            'platform': platform, 'install': staged['status'], 'local_discovery': checked['local_discovery_static'],
            'skill_count': len(checked['found']), 'file_count': len(files), 'file_manifest_sha256': hash_bytes,
            'real_client_discovery': 'NOT_TESTED', 'real_client_activation': 'NOT_TESTED',
            'real_client_orchestration': 'NOT_TESTED', 'real_client_safety': 'NOT_TESTED',
        }

def main(argv = None) -> int:
    ap = argparse.ArgumentParser(description = __doc__)
    sp = ap.add_subparsers(dest = 'action', required = True)
    for action in ('stage', 'inspect', 'smoke'):
        p = sp.add_parser(action)
        p.add_argument('--platform', required = True, choices = sorted(PLATFORMS))
        if action != 'smoke':
            p.add_argument('--project', required = True, type = Path)
        if action == 'stage':
            p.add_argument('--layout', choices = ('native', 'shared'), default = 'native')
            p.add_argument('--apply', action = 'store_true', help = 'Explicitly allow copying files into specified project')
    args = ap.parse_args(argv)
    try:
        result = {'stage': stage, 'inspect': inspect, 'smoke': smoke}[args.action](args.platform, * ( [args.project, args.layout, args.apply] if args.action == 'stage' else [args.project] if args.action == 'inspect' else []))
        print(json.dumps(result, ensure_ascii = False, indent = 2))
        if result.get('errors') or result.get('local_discovery_static') == 'FAIL':
            return 2
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii = False), file = sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
