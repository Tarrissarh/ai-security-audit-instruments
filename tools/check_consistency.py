#!/usr/bin/env python3
"""Консистентность набора ai-security-audit-instruments (без внешних зависимостей).

Проверки:
  1. Множество «конкретных» типов инструментов ({skill,agent,command,mcp,lsp,hooks,rules})
     одинаково во всех точках объявления: workflow_state.py, manifest.schema.json,
     строки TARGET_TYPE в SKILL.md и оба AI-справочника. Пропуск/лишний тип = ошибка.
  2. Каждый каталог под skills/ содержит SKILL.md с frontmatter name/version/description,
     причём `name` совпадает с именем каталога; ожидаются ровно 12 скиллов.
  3. Локальные файловые ссылки (references/, scripts/, schemas/, examples/, assets/, ../)
     в каждом SKILL.md разрешаются в существующий файл. Кросс-скилловые ссылки
     (первый сегмент — имя скилла) пропускаются: это не относительные пути.
  4. (флаг --check-profile-boilerplate) 7 профильных аудиторов содержат общий набор
     разделов H2, а инвариантные секции (безопасный режим, передаваемый результат,
     JSON-контракт, создание документации) совпадают дословно — ловит структурный
     и текстовый дрейф между ними.
  5. Состав скиллов в README.md («Состав набора») и в docs/SKILLS-REFERENCE-AI.md
     («Инвентарь скиллов») совпадает с фактическим набором skills/.

Код выхода: 0 — всё в порядке, 1 — есть ошибки.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_CONCRETE_TYPES = {'skill', 'agent', 'command', 'mcp', 'lsp', 'hooks', 'rules'}
EXPECTED_SKILLS = {
    'ai-tool-generator', 'audit-agent', 'audit-command', 'audit-docs', 'audit-hooks',
    'audit-improve', 'audit-lsp', 'audit-mcp', 'audit-modernize', 'audit-rules',
    'audit-skill', 'audit-workflow',
}
PROFILE_AUDITORS = {
    'audit-skill', 'audit-agent', 'audit-command', 'audit-mcp', 'audit-lsp',
    'audit-hooks', 'audit-rules',
}
COMMON_PROFILE_HEADINGS = {
    '## Обязательный безопасный режим',
    '## Общий процесс',
    '## Кроссплатформенный контракт и режим оркестрации',
    '## Обязательное создание документации после аудита',
    '## Дополнительные этапы после аудита (только предложения)',
    '## Передаваемый результат и критерии оценки',
    '## Особое требование',
    '## JSON-контракт при запуске через audit-workflow',
}
# Секции, которые обязаны быть дословно одинаковыми у всех профильных аудиторов
# (не содержат тип-специфичного текста). Тип-специфичные («Профильные проверки …»,
# «Особое требование», отдельные пункты «Общего процесса») сюда не входят.
INVARIANT_SECTIONS = {
    'Обязательный безопасный режим',
    'Обязательное создание документации после аудита',
    'Передаваемый результат и критерии оценки',
    'JSON-контракт при запуске через audit-workflow',
}
SKILL_NAME_RE = re.compile(r'`(audit-[a-z]+|ai-tool-generator)`')


class CheckError(Exception):
    pass


def parse_type_list(raw: str) -> set[str]:
    """Разбирает список типов, разделённый | (в т.ч. экранированным), пробелами или запятыми."""
    tokens = [t.strip("'\"`<>") for t in re.split(r'[|\s,]+', raw.strip())]
    return {t for t in tokens if t}


def md_type_set(rel: str, anchor: str = 'TARGET_TYPE') -> set[str]:
    text = (ROOT / rel).read_text(encoding='utf-8')
    m = re.search(re.escape(anchor) + r'[^\n]*', text)
    if not m:
        raise CheckError(f'{rel}: не найдено упоминание {anchor}')
    line = m.group(0).replace('\\|', '|')
    cap = re.search(r'[`<]([a-z]+(?:[ |,]+[a-z]+)*)[`>]', line)
    if not cap:
        raise CheckError(f'{rel}: не удалось разобрать список типов из строки: {line!r}')
    return parse_type_list(cap.group(1))


def scripts_doc_type_set() -> set[str]:
    text = (ROOT / 'docs/SKILLS-REFERENCE-AI-SCRIPTS.md').read_text(encoding='utf-8')
    m = re.search(r'--type\s*<([^>]+)>', text)
    if not m:
        raise CheckError('docs/SKILLS-REFERENCE-AI-SCRIPTS.md: не найден список --type')
    return parse_type_list(m.group(1))


def type_declarations() -> list[tuple[str, set[str]]]:
    """Собирает набор типов из каждой точки объявления."""
    results: list[tuple[str, set[str]]] = []

    py = (ROOT / 'skills/audit-workflow/scripts/workflow_state.py').read_text(encoding='utf-8')
    m = re.search(r'TARGET_TYPES\s*=\s*\(([^)]*)\)', py)
    if not m:
        raise CheckError('workflow_state.py: не найдена константа TARGET_TYPES')
    results.append(('workflow_state.py TARGET_TYPES', parse_type_list(m.group(1))))

    schema = json.loads((ROOT / 'skills/audit-workflow/schemas/manifest.schema.json').read_text(encoding='utf-8'))
    enum = schema.get('properties', {}).get('target', {}).get('properties', {}).get('type', {}).get('enum')
    if not enum:
        raise CheckError('manifest.schema.json: не найден enum target.type')
    results.append(('manifest.schema.json target.type', set(enum)))

    results.append(('audit-workflow/SKILL.md TARGET_TYPE', md_type_set('skills/audit-workflow/SKILL.md')))
    results.append(('audit-docs/SKILL.md TARGET_TYPE', md_type_set('skills/audit-docs/SKILL.md')))
    results.append(('ai-tool-generator/SKILL.md TARGET_TYPE', md_type_set('skills/ai-tool-generator/SKILL.md')))
    results.append(('docs/SKILLS-REFERENCE-AI.md TARGET_TYPE', md_type_set('docs/SKILLS-REFERENCE-AI.md')))
    results.append(('docs/SKILLS-REFERENCE-AI-SCRIPTS.md --type', scripts_doc_type_set()))
    return results


def check_types(errors: list[str]) -> None:
    for label, declared in type_declarations():
        concrete = declared - {'auto'}
        if concrete != CANONICAL_CONCRETE_TYPES:
            missing = sorted(CANONICAL_CONCRETE_TYPES - concrete)
            extra = sorted(concrete - CANONICAL_CONCRETE_TYPES)
            errors.append(
                f'{label}: расхождение типов '
                f'(не хватает: {missing or "—"}, лишние: {extra or "—"}, получено: {sorted(concrete)})'
            )


def parse_frontmatter(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end = i
            break
    if end is None:
        return None
    result: dict[str, str] = {}
    for line in lines[1:end]:
        if ':' in line:
            key, value = line.split(':', 1)
            result[key.strip()] = value.strip()
    return result


def check_skills(errors: list[str]) -> None:
    skills_dir = ROOT / 'skills'
    dirs = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    if dirs != EXPECTED_SKILLS:
        missing = sorted(EXPECTED_SKILLS - dirs)
        extra = sorted(dirs - EXPECTED_SKILLS)
        errors.append(f'skills/: неожиданный состав каталогов (нет: {missing or "—"}, лишние: {extra or "—"})')
        return
    for name in sorted(dirs):
        skill_md = skills_dir / name / 'SKILL.md'
        if not skill_md.is_file():
            errors.append(f'{name}: отсутствует SKILL.md')
            continue
        fm = parse_frontmatter(skill_md.read_text(encoding='utf-8'))
        if fm is None:
            errors.append(f'{name}: некорректный YAML frontmatter')
            continue
        for field in ('name', 'version', 'description'):
            if not fm.get(field):
                errors.append(f'{name}: во frontmatter отсутствует поле {field}')
        if fm.get('name') != name:
            errors.append(f"{name}: поле name ({fm.get('name')!r}) не совпадает с именем каталога")


def check_links(errors: list[str]) -> None:
    link_re = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
    for skill_dir in (ROOT / 'skills').iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / 'SKILL.md'
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding='utf-8')
        for raw in link_re.findall(text):
            target = raw.split('#', 1)[0]
            if not target or target.startswith(('http://', 'https://', 'mailto:', '//', '/')):
                continue
            first = target.split('/')[0].strip()
            if first in EXPECTED_SKILLS or first in ('docs', 'skills') or first == '.':
                # кросс-скилловая ссылка — это не относительный путь из данного каталога
                continue
            resolved = (skill_md.parent / target).resolve()
            if not resolved.exists():
                errors.append(f'{skill_dir.name}/SKILL.md: битая локальная ссылка {raw!r}')


def skill_names_in_section(text: str, heading: str) -> set[str]:
    """Извлекает имена скиллов (audit-*/ai-tool-generator) из конкретного раздела H2."""
    pattern = r'^## ' + re.escape(heading) + r'\b.*?(?=^## |\Z)'
    m = re.search(pattern, text, flags=re.M | re.S)
    if not m:
        raise CheckError(f'раздел {heading!r} не найден')
    return set(SKILL_NAME_RE.findall(m.group(0)))


def check_docs_skills(errors: list[str]) -> None:
    """Сверяет перечни скиллов в README и AI-справочнике с фактическим набором skills/."""
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    reference = (ROOT / 'docs/SKILLS-REFERENCE-AI.md').read_text(encoding='utf-8')
    sources = [
        ('README.md «Состав набора»', skill_names_in_section(readme, 'Состав набора')),
        ('docs/SKILLS-REFERENCE-AI.md «Инвентарь скиллов»', skill_names_in_section(reference, '1. Инвентарь скиллов')),
    ]
    for label, names in sources:
        if names != EXPECTED_SKILLS:
            missing = sorted(EXPECTED_SKILLS - names)
            extra = sorted(names - EXPECTED_SKILLS)
            errors.append(f'{label}: не совпадает с skills/ (нет: {missing or "—"}, лишние: {extra or "—"})')


def headings(text: str) -> set[str]:
    return {line.strip() for line in text.splitlines() if line.startswith('## ')}


def section_body(text: str, title: str) -> str | None:
    """Возвращает тело раздела H2 по заголовку (без строки заголовка)."""
    for part in re.split(r'^## ', text, flags=re.M)[1:]:
        if part.splitlines()[0].strip() == title:
            return '\n'.join(part.splitlines()[1:]).strip()
    return None


def check_profile_boilerplate(errors: list[str]) -> None:
    bodies: dict[str, str] = {}
    for name in sorted(PROFILE_AUDITORS):
        skill_md = ROOT / 'skills' / name / 'SKILL.md'
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding='utf-8')
        bodies[name] = text
        actual = headings(text)
        missing = sorted(COMMON_PROFILE_HEADINGS - actual)
        if missing:
            errors.append(f'{name}: отсутствуют общие разделы: {missing}')
    for section in sorted(INVARIANT_SECTIONS):
        reference: tuple[str, str] | None = None
        for name in sorted(bodies):
            body = section_body(bodies[name], section)
            if body is None:
                errors.append(f'{name}: отсутствует инвариантная секция {section!r}')
                continue
            if reference is None:
                reference = (name, body)
            elif body != reference[1]:
                errors.append(f'{name}: секция {section!r} дословно расходится с {reference[0]}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-profile-boilerplate', action='store_true',
                        help='дополнительно сверить структуру разделов 7 профильных аудиторов')
    args = parser.parse_args()

    errors: list[str] = []
    check_types(errors)
    check_skills(errors)
    check_docs_skills(errors)
    check_links(errors)
    if args.check_profile_boilerplate:
        check_profile_boilerplate(errors)

    if errors:
        print(f'КОНСИСТЕНТНОСТЬ НАРУШЕНА — найдено ошибок: {len(errors)}')
        for e in errors:
            print(f'  - {e}')
        return 1
    print('OK: консистентность набора не нарушена')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
