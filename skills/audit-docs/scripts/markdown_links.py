#!/usr/bin/env python3
"""Check local links in Markdown using CommonMark tokens (never execute content).

Validation tooling dependency: markdown-it-py. Handles inline, image and reference
links, fenced/inline code and common GitHub-style heading fragments.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

_PARSER = MarkdownIt('commonmark', {'html': False, 'linkify': False})
_HTML_ANCHOR_RE = re.compile(r'<(?:a|\w+)\s+[^>]*?\b(?:id|name)=[\'\"]([^\'\"]+)[\'\"]', re.I)

def _headings(path: Path) -> set[str]:
    """Формирует список допустимых якорей Markdown с учётом одинаковых заголовков и их порядковых суффиксов."""
    markdown = path.read_text(encoding = 'utf-8-sig')
    tokens = _PARSER.parse(markdown)
    names: set[str] = set()
    repeats: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if token.type != 'heading_open':
            continue
        if index + 1 >= len(tokens):
            continue
        inline = tokens[index + 1]
        text = ''.join(child.content for child in inline.children or []
                       if child.type in ('text', 'code_inline', 'html_inline', 'image'))
        text = re.sub(r'<[^>]*>', '', text)
        text = re.sub(r'[^\w\s-]', '', text.casefold(), flags = re.UNICODE).strip()
        slug = re.sub(r'\s+', '-', text)
        count = repeats.get(slug, 0)
        repeats[slug] = count + 1
        if count:
            slug = f'{slug}-{count}'
        names.add(slug)
    names.update(_HTML_ANCHOR_RE.findall(markdown))
    return names

def _links(path: Path):
    """Извлекает обычные, справочные и графические Markdown-ссылки для последующей проверки целей."""
    text = path.read_text(encoding = 'utf-8-sig')
    for token in _PARSER.parse(text):
        if token.type != 'inline':
            continue
        for item in token.children or []:
            if item.type == 'link_open':
                url = item.attrGet('href')
            elif item.type == 'image':
                url = item.attrGet('src')
            else:
                continue
            if url:
                yield url, (token.map[0] + 1 if token.map else None)

def check_markdown_links(root: Path, paths: list[Path] | None = None) -> tuple[list[str], list[str]]:
    """Return errors, warnings for local links under root; no external access.

    Root-relative site links and remote URLs cannot be verified locally; warn
    for site-root links rather than silently treating them as valid.
    """
    root = root.resolve(strict = True)
    errors: list[str] = []
    warnings: list[str] = []
    targets = sorted(paths if paths is not None else root.rglob('*.md'))
    heading_cache: dict[Path, set[str]] = {}
    for p in targets:
        if not p.is_file():
            continue
        try:
            relative = p.relative_to(root)
        except ValueError:
            errors.append(f'{p}: Markdown source outside root')
            continue
        for raw, line in _links(p):
            where = f'{relative}:{line}' if line is not None else str(relative)
            if raw.startswith('//'):
                continue
            parsed = urlsplit(raw)
            if parsed.scheme or parsed.netloc:
                continue
            if parsed.path.startswith('/'):
                warnings.append(f'{where}: site-root link cannot be checked locally: {raw}')
                continue
            rel_path = unquote(parsed.path)
            if '\\' in rel_path or '\x00' in rel_path:
                errors.append(f'{where}: invalid local link path: {raw}')
                continue
            candidate = (p.parent / rel_path).resolve()
            if not candidate.is_relative_to(root):
                errors.append(f'{where}: link escapes package: {raw}')
                continue
            if not candidate.exists():
                errors.append(f'{where}: missing local link target: {raw}')
                continue
            if not candidate.is_file() and not candidate.is_dir():
                errors.append(f'{where}: unreadable local link target: {raw}')
                continue
            if parsed.fragment and candidate.is_file() and candidate.suffix.lower() == '.md':
                fragment = unquote(parsed.fragment)
                if candidate not in heading_cache:
                    heading_cache[candidate] = _headings(candidate)
                if fragment not in heading_cache[candidate]:
                    errors.append(f'{where}: unknown Markdown heading fragment: {raw}')
    return errors, warnings
