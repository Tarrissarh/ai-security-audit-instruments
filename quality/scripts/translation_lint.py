#!/usr/bin/env python3
"""Static translation integrity checks, not a semantic translation-quality judge.
Does not execute input files. Source/translation are plain text with bounded size.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None

MAX_BYTES = 5_000_000
FENCE_OPEN = re.compile(r'^\s{0,3}(`{3,}|~{3,})([^\r\n]*)$')
YAML_START = re.compile(r'^---\s*$')
PLACEHOLDERS = re.compile(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}|\{[A-Z][A-Z0-9_]*\}|\{\{[^{}]+\}\}')
URLS = re.compile(r'https?://[^\s)>]+')
INLINE = re.compile(r'(?<!`)`([^`\n]+)`(?!`)')
MD_LINK = re.compile(r'!?(?:\[[^\]]+\])\(([^)]+)\)')
MD_HEADING = re.compile(r'^\s{0,3}#{1,6}\s+\S', re.M)

class IntegrityError(ValueError):
    pass

def read(path: Path):
    if path.stat().st_size > MAX_BYTES:
        raise IntegrityError('File exceeds 5 MB validation limit')
    return path.read_text(encoding = 'utf-8')

def separate_frontmatter(text: str):
    """Отделяет YAML-метаданные от переводимого текста, чтобы проверить сохранность машинных идентификаторов."""
    lines = text.splitlines(keepends = True)
    if not lines or not YAML_START.match(lines[0].strip()):
        return None, text
    for i in range(1, len(lines)):
        if YAML_START.match(lines[i].strip()):
            if yaml is None:
                raise IntegrityError('PyYAML required to validate frontmatter')
            header = yaml.safe_load(''.join(lines[1: i]))
            if not isinstance(header, dict):
                raise IntegrityError('Frontmatter should be YAML mapping')
            return header, ''.join(lines[i + 1:])
    raise IntegrityError('Unclosed YAML frontmatter')

def fences(content):
    """Get original fenced code block bodies + info strings, ignoring translation of surrounding prose."""
    blocks = []
    open_token = None
    info = ''
    buf = []
    for line in content.splitlines():
        if open_token is None:
            match = FENCE_OPEN.match(line)
            if match:
                open_token = match.group(1)
                info = match.group(2).strip()
                buf = []
            continue
        if re.match(r'^\s{0,3}' + re.escape(open_token[0]) + r'{' + str(len(open_token)) + r',}\s*$', line):
            blocks.append({'info': info, 'body': '\n'.join(buf)})
            open_token = None
        else:
            buf.append(line)
    if open_token is not None:
        raise IntegrityError('Unclosed Markdown code fence')
    return blocks

def compare(source: str, translated: str, link_map = None) -> dict:
    """Проверяет структурные инварианты перевода: YAML, код, плейсхолдеры и ссылки; семантическую точность отдельно не гарантирует."""
    if link_map is None:
        link_map = {}
    original_header, original_body = separate_frontmatter(source)
    translated_header, translated_body = separate_frontmatter(translated)
    problems = []
    if (original_header is None) != (translated_header is None):
        problems.append('frontmatter_presence_changed')
    elif original_header is not None:
        if set(original_header) != set(translated_header):
            problems.append('frontmatter_keys_changed')
        for key in set(original_header).intersection(translated_header):
            if key not in ('description', 'summary') and original_header[key] != translated_header[key]:
                problems.append('frontmatter_machine_field_changed:' + str(key))
    try:
        if fences(original_body) != fences(translated_body):
            problems.append('code_fences_or_contents_changed')
    except IntegrityError as exc:
        problems.append(str(exc))
    for name, pattern in (('placeholders', PLACEHOLDERS), ('urls', URLS), ('inline_code', INLINE)):
        if Counter(pattern.findall(original_body)) != Counter(pattern.findall(translated_body)):
            problems.append(name + '_changed')
    src_links = Counter(link_map.get(x, x) for x in MD_LINK.findall(original_body))
    trans_links = Counter(MD_LINK.findall(translated_body))
    if src_links != trans_links:
        problems.append('markdown_link_targets_changed')
    if len(MD_HEADING.findall(original_body)) != len(MD_HEADING.findall(translated_body)):
        problems.append('heading_count_changed')
    return {'ok': not problems, 'issues': sorted(set(problems)),
            'checks': ['yaml_frontmatter', 'code_fences', 'placeholders', 'urls', 'inline_code', 'markdown_link_targets', 'heading_count'],
            'limitations': ['No semantic equivalence or terminology correctness is asserted.',
                           'Reference-style links and nested Markdown require separate link validation.',
                           'Heading counts do not prove correct translation or section order.']}

def main(argv = None):
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--source', type = Path, required = True)
    parser.add_argument('--translation', type = Path, required = True)
    parser.add_argument('--link-map', type = Path)
    parser.add_argument('--output', type = Path)
    args = parser.parse_args(argv)
    try:
        mapping = json.loads(read(args.link_map)) if args.link_map else {}
        if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
            raise IntegrityError('link-map must be object {original_path:translated_path}')
        result = compare(read(args.source), read(args.translation), mapping)
        output = json.dumps(result, ensure_ascii = False, indent = 2) + '\n'
        if args.output:
            args.output.parent.mkdir(parents = True, exist_ok = True)
            args.output.write_text(output, encoding = 'utf-8')
        print(output, end = '')
        return 0 if result['ok'] else 2
    except (OSError, UnicodeError, ValueError, yaml.YAMLError if yaml else ValueError) as exc:
        print('TRANSLATION_CHECK_ERROR: ' + str(exc), file = sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
