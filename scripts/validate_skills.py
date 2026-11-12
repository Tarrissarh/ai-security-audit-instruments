#!/usr/bin/env python3
"""Pure-stdlib, read-only static check for AI Audit & Tooling Skills bundles.
Does not run skill contents, scripts from audited projects, or network requests.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from urllib.parse import unquote

EXPECTED = {
    'audit-workflow', 'audit-skill', 'audit-agent', 'audit-command',
    'audit-mcp', 'audit-lsp', 'audit-hooks', 'audit-docs',
    'audit-improve', 'audit-modernize', 'ai-tool-generator'
}
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
LINK_RE = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
FIELDS = {'name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools', 'disable-model-invocation', 'user-invocable'}


def read_frontmatter(path: Path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    if not lines or lines[0].strip() != '---':
        return {}, ['missing YAML frontmatter opening marker']
    try:
        ix = next(i for i in range(1, len(lines)) if lines[i].strip() == '---')
    except StopIteration:
        return {}, ['missing YAML frontmatter closing marker']
    front = {}; issues=[]
    # Minimal standard-library check (full YAML syntax needs external YAML library).
    for line in lines[1:ix]:
        if not line.strip() or line.lstrip().startswith('#') or line[:1].isspace():
            continue
        m = re.match(r'^([A-Za-z0-9_-]+)\s*:\s*(.*)$', line)
        if not m:
            issues.append('unrecognized top-level YAML line: '+line[:80]); continue
        k,v=m.groups()
        if k in front: issues.append(f'duplicate frontmatter key: {k}')
        front[k] = v.strip().strip('"\'')
    for req in ['name','description']:
        if not front.get(req): issues.append(f'missing/empty required key: {req}')
    return front, issues


def prose_without_fences(s: str) -> str:
    s = re.sub(r'(?ms)^\s*```.*?^\s*```\s*$', '', s)
    return re.sub(r'`[^`\n]+`','',s)


def validate(root: Path):
    root=root.resolve()
    errors=[]; warnings=[]; found={}
    for skill_dir in sorted(root.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir/'SKILL.md').exists(): continue
        p=skill_dir/'SKILL.md'; fm, problems=read_frontmatter(p)
        errors += [f'{p.relative_to(root)}: {x}' for x in problems]
        name=fm.get('name','')
        if not NAME_RE.fullmatch(name) or len(name)>64: errors.append(f'{p.relative_to(root)}: invalid skill name {name!r}')
        if name!=skill_dir.name: errors.append(f'{p.relative_to(root)}: name does not match directory')
        if len(fm.get('description',''))>1024: errors.append(f'{p.relative_to(root)}: description over 1024 chars')
        if fm.get('disable-model-invocation') and fm.get('disable-model-invocation') not in ('true','false'):
            errors.append(f'{p.relative_to(root)}: invalid disable-model-invocation flag')
        if name in found: errors.append(f'duplicate skill name {name}: {p} and {found[name]}')
        found[name]=p
        if len(p.read_text(encoding='utf8').splitlines())>500:
            warnings.append(f'{p.relative_to(root)}: SKILL.md >500 lines')
    absent = EXPECTED - found.keys()
    if absent: errors.append('missing expected skills: '+', '.join(sorted(absent)))
    # validate relative markdown links throughout bundle
    for p in sorted(root.rglob('*.md')):
        cleaned=prose_without_fences(p.read_text(encoding='utf-8'))
        for raw in LINK_RE.findall(cleaned):
            href=raw.split(' ',1)[0].strip().strip('<>')
            if not href or href.startswith(('#','/','~','mailto:','data:')) or re.match(r'^[a-zA-Z][a-zA-Z\d+.-]*:',href):continue
            href=unquote(href.split('#',1)[0].split('?',1)[0])
            target=(p.parent/href).resolve()
            if not target.is_relative_to(root):
                errors.append(f'{p.relative_to(root)}: link escapes bundle: {raw}'); continue
            if not target.exists(): errors.append(f'{p.relative_to(root)}: missing link target: {raw}')
    guard=found.get('ai-tool-generator')
    if guard:
        fm,_=read_frontmatter(guard)
        if fm.get('disable-model-invocation')!='true':
            errors.append('ai-tool-generator must set disable-model-invocation: true')
        if 'явн' not in guard.read_text(encoding='utf8').lower():
            errors.append('ai-tool-generator requires explicit human instruction rule')
    workflow=found.get('audit-workflow')
    if workflow:
        s=workflow.read_text(encoding='utf8')
        for p in ['platform-matrix.md','platform-opencode.md','platform-deepseek-harness.md','platform-claude-code.md','platform-codex.md','platform-cursor.md','acceptance.md','preflight.md','handoff-contract.md']:
            if not (workflow.parent/'references'/p).is_file():errors.append('audit-workflow missing reference '+p)
        if 'не вызывай** `ai-tool-generator`' not in s:
            warnings.append('audit-workflow generator prohibition should be reviewed')
    return found,errors,warnings


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('root',nargs='?',default='.',type=Path)
    args=ap.parse_args()
    found,errors,warnings=validate(args.root)
    print(f'Skills detected: {len(found)} / {len(EXPECTED)}')
    for w in warnings:print('WARN:',w)
    for e in errors:print('ERROR:',e)
    if errors: print(f'FAIL: {len(errors)} problems');return 1
    print('PASS: basic frontmatter, links, references and generator guards')
    print('NOTE: this is static validation; it does not prove runtime support in clients.')
    return 0
if __name__=='__main__':raise SystemExit(main())
