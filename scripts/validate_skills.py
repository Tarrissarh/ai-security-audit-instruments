#!/usr/bin/env python3
"""Read-only validation for the AI Audit & Tooling Skills bundle (v6.0).

Requires PyYAML and markdown-it-py for *validation only*, not for using skills.
Does not execute audited projects, install packages, or make network requests.
"""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations

# Импортирует модуль или имена, используемые в этом файле.
import argparse
# Импортирует модуль или имена, используемые в этом файле.
import re
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "audit-docs" / "scripts"))
# Начинает блок с контролируемой обработкой исключений.
try:
    # Импортирует модуль или имена, используемые в этом файле.
    import yaml
    # Импортирует модуль или имена, используемые в этом файле.
    import jsonschema
    # Импортирует модуль или имена, используемые в этом файле.
    from yaml.constructor import ConstructorError
    # Импортирует модуль или имена, используемые в этом файле.
    from markdown_links import check_markdown_links
# Перехватывает указанное исключение для безопасной обработки.
except ModuleNotFoundError as exc:
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit(f'Missing validation dependency: {exc.name}. '
                     # Формирует часть выражения или передаёт аргумент в текущую операцию.
                     'Manually install requirements-validation.txt before validating.') from exc

# Сохраняет или обновляет вычисленное значение для последующих операций.
EXPECTED = {
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'audit-workflow', 'audit-skill', 'audit-agent', 'audit-command',
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'audit-mcp', 'audit-lsp', 'audit-hooks', 'audit-docs',
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    'audit-improve', 'audit-modernize', 'ai-tool-generator'
}
# Сохраняет или обновляет вычисленное значение для последующих операций.
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
# Сохраняет или обновляет вычисленное значение для последующих операций.
FIELDS = {'name', 'description', 'license', 'compatibility', 'metadata',
          # Формирует часть выражения или передаёт аргумент в текущую операцию.
          'allowed-tools', 'disable-model-invocation', 'user-invocable'}


# Определяет класс и его интерфейс.
class StrictSafeLoader(yaml.SafeLoader):
    # Описывает назначение блока в многострочной строке документации.
    """SafeLoader that rejects duplicate mapping keys instead of overwriting."""


# Объявляет функцию _strict_mapping и её параметры.
def _strict_mapping(loader, node):
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    loader.flatten_mapping(node)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    mapping = {}
    # Перебирает элементы набора для последовательной обработки.
    for key_node, value_node in node.value:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        key = loader.construct_object(key_node, deep = True)
        # Проверяет условие перед выполнением следующего блока.
        if not isinstance(key, (str, int, bool, float)):
            # Прерывает операцию с диагностическим исключением.
            raise ConstructorError(None, None, 'non-scalar mapping key', key_node.start_mark)
        # Проверяет условие перед выполнением следующего блока.
        if key in mapping:
            # Прерывает операцию с диагностическим исключением.
            raise ConstructorError(None, None, f'duplicate YAML key: {key}', key_node.start_mark)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        mapping[key] = loader.construct_object(value_node, deep = True)
    # Возвращает вычисленный результат вызывающему коду.
    return mapping


# Формирует часть выражения или передаёт аргумент в текущую операцию.
StrictSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _strict_mapping)


# Объявляет функцию read_frontmatter и её параметры.
def read_frontmatter(path: Path):
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    lines = path.read_text(encoding = 'utf-8-sig').splitlines()
    # Проверяет условие перед выполнением следующего блока.
    if not lines or lines[0].strip() != '---':
        # Возвращает вычисленный результат вызывающему коду.
        return {}, ['missing YAML frontmatter opening marker']
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        ix = next(i for i in range(1, len(lines)) if lines[i].strip() == '---')
    # Перехватывает указанное исключение для безопасной обработки.
    except StopIteration:
        # Возвращает вычисленный результат вызывающему коду.
        return {}, ['missing YAML frontmatter closing marker']
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        front = yaml.load('\n'.join(lines[1: ix]), Loader = StrictSafeLoader)
    # Перехватывает указанное исключение для безопасной обработки.
    except yaml.YAMLError as exc:
        # Возвращает вычисленный результат вызывающему коду.
        return {}, [f'invalid YAML frontmatter: {exc}']
    # Проверяет условие перед выполнением следующего блока.
    if not isinstance(front, dict):
        # Возвращает вычисленный результат вызывающему коду.
        return {}, ['YAML frontmatter must be a mapping']
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    issues = []
    # Перебирает элементы набора для последовательной обработки.
    for k in ('name', 'description'):
        # Проверяет условие перед выполнением следующего блока.
        if not isinstance(front.get(k), str) or not front[k].strip():
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'missing/invalid required string key: {k}')
    # Перебирает элементы набора для последовательной обработки.
    for k in ('disable-model-invocation', 'user-invocable'):
        # Проверяет условие перед выполнением следующего блока.
        if k in front and not isinstance(front[k], bool):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            issues.append(f'{k} must be boolean true/false')
    # Preserve legacy string interface for existing consumers/tests.
    # Перебирает элементы набора для последовательной обработки.
    for k in ('disable-model-invocation', 'user-invocable'):
        # Проверяет условие перед выполнением следующего блока.
        if isinstance(front.get(k), bool):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            front[k] = str(front[k]).lower()
    # Возвращает вычисленный результат вызывающему коду.
    return front, issues


# Объявляет функцию validate и её параметры.
def validate(root: Path):
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = root.resolve()
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    errors = []
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    warnings = []
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    found = {}
    # Проверяет условие перед выполнением следующего блока.
    if not root.is_dir():
        # Возвращает вычисленный результат вызывающему коду.
        return found, [f'missing bundle directory: {root}'], warnings
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    skills_root = root / "skills" if (root / "skills").is_dir() else root
    # Перебирает элементы набора для последовательной обработки.
    for skill_dir in sorted(skills_root.iterdir()):
        # Проверяет условие перед выполнением следующего блока.
        if not skill_dir.is_dir() or not (skill_dir / 'SKILL.md').is_file():
            # Переходит к следующей итерации цикла.
            continue
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = skill_dir / 'SKILL.md'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fm, problems = read_frontmatter(p)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        errors.extend(f'{p.relative_to(root)}: {x}' for x in problems)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        name = fm.get('name', '')
        # Проверяет условие перед выполнением следующего блока.
        if not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > 64:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append(f'{p.relative_to(root)}: invalid skill name {name!r}')
        # Проверяет условие перед выполнением следующего блока.
        if name != skill_dir.name:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append(f'{p.relative_to(root)}: name does not match directory')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        description = fm.get('description', '')
        # Проверяет условие перед выполнением следующего блока.
        if isinstance(description, str) and len(description) > 1024:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append(f'{p.relative_to(root)}: description over 1024 chars')
        # Проверяет условие перед выполнением следующего блока.
        if name in found:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append(f'duplicate skill name {name}: {p} and {found[name]}')
        # Проверяет условие перед выполнением следующего блока.
        if isinstance(name, str):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            found[name] = p
        # Проверяет условие перед выполнением следующего блока.
        if len(p.read_text(encoding = 'utf-8').splitlines()) > 500:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            warnings.append(f'{p.relative_to(root)}: SKILL.md >500 lines')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    absent = EXPECTED - found.keys()
    # Проверяет условие перед выполнением следующего блока.
    if absent:
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        errors.append('missing expected skills: ' + ', '.join(sorted(absent)))
    # Deliberately broken links inside quality/fixtures are a regression target,
    # not a packaging error. Validate the authored package docs separately.
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    md_paths = [p for p in root.rglob('*.md')
              # Проверяет условие перед выполнением следующего блока.
              if p.relative_to(root).parts[: 2] != ('quality', 'fixtures')]
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    link_errors, link_warnings = check_markdown_links(root, md_paths)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    required_quality = [
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'quality/README.md', 'quality/REPORT_TEMPLATE.md', 'quality/gold/cases.json',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'quality/scripts/evaluate.py', 'quality/scripts/translation_lint.py',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'skills/audit-workflow/references/quality-benchmark.md',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'skills/audit-docs/references/quality-translation.md',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'skills/audit-improve/references/recommendation-evaluation.md',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'tests/test_quality_v53.py'
    ]
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    required_v60 = [
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'scripts/platform_compat.py', 'tests/test_platform_v60.py',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'integration/README.md', 'integration/MATRIX.md',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'integration/offline-results.json', 'integration/evidence-template.json',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'skills/audit-workflow/references/platform-runtime-verification.md',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'skills/audit-workflow/references/runtime-test-protocol.md',
    ]
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    required_v61 = [
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'integration/runtime/README.md', 'integration/runtime/real_client.py',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'integration/runtime/local-probe.json', 'integration/runtime/offline-checks.json',
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        'skills/audit-workflow/references/runtime-evidence.md', 'tests/test_runtime_v61.py',
    ]
    # Перебирает элементы набора для последовательной обработки.
    for rel in required_v61:
        # Проверяет условие перед выполнением следующего блока.
        if not (root / rel).is_file():
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append('v6.1 missing runtime evidence material: ' + rel)
    # Перебирает элементы набора для последовательной обработки.
    for rel in required_v60:
        # Проверяет условие перед выполнением следующего блока.
        if not (root / rel).is_file():
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append('v6.0 missing compatibility material: ' + rel)
    # Перебирает элементы набора для последовательной обработки.
    for rel in required_quality:
        # Проверяет условие перед выполнением следующего блока.
        if not (root / rel).is_file():
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append('v5.3 missing QA material: ' + rel)
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    errors += link_errors
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    warnings += link_warnings
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    guard = found.get('ai-tool-generator')
    # Проверяет условие перед выполнением следующего блока.
    if guard:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        fm, _ = read_frontmatter(guard)
        # Проверяет условие перед выполнением следующего блока.
        if fm.get('disable-model-invocation') != 'true':
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append('ai-tool-generator must set disable-model-invocation: true')
        # Проверяет условие перед выполнением следующего блока.
        if 'явн' not in guard.read_text(encoding = 'utf-8').lower():
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append('ai-tool-generator requires explicit human instruction rule')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    workflow = found.get('audit-workflow')
    # Проверяет условие перед выполнением следующего блока.
    if workflow:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        s = workflow.read_text(encoding = 'utf-8')
        # Перебирает элементы набора для последовательной обработки.
        for p in ['platform-matrix.md', 'platform-opencode.md', 'platform-deepseek-harness.md',
                  # Формирует часть выражения или передаёт аргумент в текущую операцию.
                  'platform-claude-code.md', 'platform-codex.md', 'platform-cursor.md',
                  # Формирует часть выражения или передаёт аргумент в текущую операцию.
                  'acceptance.md', 'preflight.md', 'handoff-contract.md']:
            # Проверяет условие перед выполнением следующего блока.
            if not (workflow.parent / 'references' / p).is_file():
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append('audit-workflow missing reference ' + p)
        # Проверяет условие перед выполнением следующего блока.
        if 'не вызывай** `ai-tool-generator`' not in s:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            warnings.append('audit-workflow generator prohibition should be reviewed')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        required_v52 = ['scripts/workflow_state.py', 'scripts/markdown_links.py',
                        # Формирует часть выражения или передаёт аргумент в текущую операцию.
                        'scripts/requirements.txt', 'scripts/README.md',
                        # Формирует часть выражения или передаёт аргумент в текущую операцию.
                        'schemas/stage-result.schema.json', 'schemas/manifest.schema.json']
        # Перебирает элементы набора для последовательной обработки.
        for relative in required_v52:
            # Проверяет условие перед выполнением следующего блока.
            if not (workflow.parent / relative).is_file():
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append('audit-workflow v5.2 missing ' + relative)
        # Перебирает элементы набора для последовательной обработки.
        for filename in ('stage-result.schema.json', 'manifest.schema.json'):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            schema_path = workflow.parent / 'schemas' / filename
            # Проверяет условие перед выполнением следующего блока.
            if schema_path.is_file():
                # Начинает блок с контролируемой обработкой исключений.
                try:
                    # Импортирует модуль или имена, используемые в этом файле.
                    import json
                    # Формирует часть выражения или передаёт аргумент в текущую операцию.
                    jsonschema.Draft202012Validator.check_schema(json.loads(schema_path.read_text('utf-8')))
                # Перехватывает указанное исключение для безопасной обработки.
                except (ValueError, jsonschema.exceptions.SchemaError) as exc:
                    # Формирует часть выражения или передаёт аргумент в текущую операцию.
                    errors.append(f'{filename}: invalid JSON Schema: {exc}')
    # Возвращает вычисленный результат вызывающему коду.
    return found, errors, warnings


# Объявляет функцию main и её параметры.
def main():
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    ap = argparse.ArgumentParser(description = __doc__)
    # Настраивает аргументы, параметры или состояние объекта.
    ap.add_argument('root', nargs = '?', default = '.', type = Path)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args = ap.parse_args()
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    found, errors, warnings = validate(args.root)
    # Выводит диагностическую информацию о результате выполнения.
    print(f'Skills detected: {len(found)} / {len(EXPECTED)}')
    # Перебирает элементы набора для последовательной обработки.
    for w in warnings:
        # Выводит предупреждение, сформированное валидатором.
        print('WARN:', w)
    # Перебирает элементы набора для последовательной обработки.
    for e in errors:
        # Выводит сообщение об обнаруженной ошибке.
        print('ERROR:', e)
    # Проверяет условие перед выполнением следующего блока.
    if errors:
        # Выводит диагностическую информацию о результате выполнения.
        print(f'FAIL: {len(errors)} problems')
        # Возвращает вычисленный результат вызывающему коду.
        return 1
    # Выводит диагностическую информацию о результате выполнения.
    print('PASS: YAML, Markdown links, JSON Schemas, references and generator guards')
    # Выводит диагностическую информацию о результате выполнения.
    print('NOTE: static validation only; runtime support in AI clients remains unverified.')
    # Возвращает вычисленный результат вызывающему коду.
    return 0

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Прерывает операцию с диагностическим исключением.
    raise SystemExit(main())
