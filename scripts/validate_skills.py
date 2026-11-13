#!/usr/bin/env python3
"""Read-only validation for the AI Audit & Tooling Skills bundle .

Requires PyYAML and markdown-it-py for *validation only*, not for using skills.
Does not execute audited projects, install packages, or make network requests.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "audit-docs" / "scripts"))
try:
    import yaml
    import jsonschema
    from yaml.constructor import ConstructorError
    from markdown_links import check_markdown_links
except ModuleNotFoundError as exc:
    raise SystemExit(f'Missing validation dependency: {exc.name}. '
                     'Manually install requirements-validation.txt before validating.') from exc

EXPECTED = {
    'audit-workflow', 'audit-skill', 'audit-agent', 'audit-command',
    'audit-mcp', 'audit-lsp', 'audit-hooks', 'audit-docs',
    'audit-improve', 'audit-modernize', 'ai-tool-generator'
}
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
FIELDS = {'name', 'description', 'license', 'compatibility', 'metadata',
          'allowed-tools', 'disable-model-invocation', 'user-invocable'}

class StrictSafeLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of overwriting."""

def _strict_mapping(loader, node):
    """Отклоняет дублирующиеся YAML-ключи, иначе последняя запись могла бы незаметно переопределить ограничения скилла."""
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep = True)
        if not isinstance(key, (str, int, bool, float)):
            raise ConstructorError(None, None, 'non-scalar mapping key', key_node.start_mark)
        if key in mapping:
            raise ConstructorError(None, None, f'duplicate YAML key: {key}', key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep = True)
    return mapping

StrictSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _strict_mapping)

def read_frontmatter(path: Path):
    """Извлекает frontmatter из SKILL.md и валидирует YAML с запретом неоднозначных ключей и неверных типов."""
    lines = path.read_text(encoding = 'utf-8-sig').splitlines()
    if not lines or lines[0].strip() != '---':
        return {}, ['missing YAML frontmatter opening marker']
    try:
        ix = next(i for i in range(1, len(lines)) if lines[i].strip() == '---')
    except StopIteration:
        return {}, ['missing YAML frontmatter closing marker']
    try:
        front = yaml.load('\n'.join(lines[1: ix]), Loader = StrictSafeLoader)
    except yaml.YAMLError as exc:
        return {}, [f'invalid YAML frontmatter: {exc}']
    if not isinstance(front, dict):
        return {}, ['YAML frontmatter must be a mapping']
    issues = []
    for k in ('name', 'description'):
        if not isinstance(front.get(k), str) or not front[k].strip():
            issues.append(f'missing/invalid required string key: {k}')
    for k in ('disable-model-invocation', 'user-invocable'):
        if k in front and not isinstance(front[k], bool):
            issues.append(f'{k} must be boolean true/false')
    # Сохраняем прежний строковый интерфейс, чтобы не нарушить вызовы валидатора.
    for k in ('disable-model-invocation', 'user-invocable'):
        if isinstance(front.get(k), bool):
            front[k] = str(front[k]).lower()
    return front, issues

def validate(root: Path):
    """Сверяет состав, обязательные ресурсы, форматы конфигураций и внутренние ссылки всего дистрибутива."""
    root = root.resolve()
    errors = []
    warnings = []
    found = {}
    if not root.is_dir():
        return found, [f'missing bundle directory: {root}'], warnings
    skills_root = root / "skills" if (root / "skills").is_dir() else root
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / 'SKILL.md').is_file():
            continue
        p = skill_dir / 'SKILL.md'
        fm, problems = read_frontmatter(p)
        errors.extend(f'{p.relative_to(root)}: {x}' for x in problems)
        name = fm.get('name', '')
        if not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > 64:
            errors.append(f'{p.relative_to(root)}: invalid skill name {name!r}')
        if name != skill_dir.name:
            errors.append(f'{p.relative_to(root)}: name does not match directory')
        description = fm.get('description', '')
        if isinstance(description, str) and len(description) > 1024:
            errors.append(f'{p.relative_to(root)}: description over 1024 chars')
        if name in found:
            errors.append(f'duplicate skill name {name}: {p} and {found[name]}')
        if isinstance(name, str):
            found[name] = p
        if len(p.read_text(encoding = 'utf-8').splitlines()) > 500:
            warnings.append(f'{p.relative_to(root)}: SKILL.md >500 lines')
    absent = EXPECTED - found.keys()
    if absent:
        errors.append('missing expected skills: ' + ', '.join(sorted(absent)))
    # Сломанные ссылки в quality/fixtures — тестовые дефекты; документы дистрибутива проверяем отдельно.
    md_paths = [p for p in root.rglob('*.md')
              if p.relative_to(root).parts[: 2] != ('quality', 'fixtures')]
    link_errors, link_warnings = check_markdown_links(root, md_paths)
    required_quality = [
        'quality/README.md', 'quality/REPORT_TEMPLATE.md', 'quality/gold/cases.json',
        'quality/scripts/evaluate.py', 'quality/scripts/translation_lint.py',
        'skills/audit-workflow/references/quality-benchmark.md',
        'skills/audit-docs/references/quality-translation.md',
        'skills/audit-improve/references/recommendation-evaluation.md',
        'tests/test_quality.py'
    ]
    required_compatibility = [
        'scripts/platform_compat.py', 'tests/test_platform.py',
        'integration/README.md', 'integration/MATRIX.md',
        'integration/offline-results.json', 'integration/evidence-template.json',
        'skills/audit-workflow/references/platform-runtime-verification.md',
        'skills/audit-workflow/references/runtime-test-protocol.md',
    ]
    required_runtime = [
        'integration/runtime/README.md', 'integration/runtime/real_client.py',
        'integration/runtime/local-probe.json', 'integration/runtime/offline-checks.json',
        'skills/audit-workflow/references/runtime-evidence.md', 'tests/test_runtime.py',
    ]
    for rel in required_runtime:
        if not (root / rel).is_file():
            errors.append('missing runtime evidence material: ' + rel)
    for rel in required_compatibility:
        if not (root / rel).is_file():
            errors.append('missing compatibility material: ' + rel)
    for rel in required_quality:
        if not (root / rel).is_file():
            errors.append('missing QA material: ' + rel)
    errors += link_errors
    warnings += link_warnings
    guard = found.get('ai-tool-generator')
    if guard:
        fm, _ = read_frontmatter(guard)
        if fm.get('disable-model-invocation') != 'true':
            errors.append('ai-tool-generator must set disable-model-invocation: true')
        if 'явн' not in guard.read_text(encoding = 'utf-8').lower():
            errors.append('ai-tool-generator requires explicit human instruction rule')
    workflow = found.get('audit-workflow')
    if workflow:
        s = workflow.read_text(encoding = 'utf-8')
        for p in ['platform-matrix.md', 'platform-opencode.md', 'platform-deepseek-harness.md',
                  'platform-claude-code.md', 'platform-codex.md', 'platform-cursor.md',
                  'acceptance.md', 'preflight.md', 'handoff-contract.md']:
            if not (workflow.parent / 'references' / p).is_file():
                errors.append('audit-workflow missing reference ' + p)
        if 'не вызывай** `ai-tool-generator`' not in s:
            warnings.append('audit-workflow generator prohibition should be reviewed')
        required_workflow = ['scripts/workflow_state.py', 'scripts/markdown_links.py',
                        'scripts/requirements.txt', 'scripts/README.md',
                        'schemas/stage-result.schema.json', 'schemas/manifest.schema.json']
        for relative in required_workflow:
            if not (workflow.parent / relative).is_file():
                errors.append('audit-workflow missing ' + relative)
        for filename in ('stage-result.schema.json', 'manifest.schema.json'):
            schema_path = workflow.parent / 'schemas' / filename
            if schema_path.is_file():
                try:
                    import json
                    jsonschema.Draft202012Validator.check_schema(json.loads(schema_path.read_text('utf-8')))
                except (ValueError, jsonschema.exceptions.SchemaError) as exc:
                    errors.append(f'{filename}: invalid JSON Schema: {exc}')
    return found, errors, warnings

def main():
    ap = argparse.ArgumentParser(description = __doc__)
    ap.add_argument('root', nargs = '?', default = '.', type = Path)
    args = ap.parse_args()
    found, errors, warnings = validate(args.root)
    print(f'Skills detected: {len(found)} / {len(EXPECTED)}')
    for w in warnings:
        print('WARN:', w)
    for e in errors:
        print('ERROR:', e)
    if errors:
        print(f'FAIL: {len(errors)} problems')
        return 1
    print('PASS: YAML, Markdown links, JSON Schemas, references and generator guards')
    print('NOTE: static validation only; runtime support in AI clients remains unverified.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
