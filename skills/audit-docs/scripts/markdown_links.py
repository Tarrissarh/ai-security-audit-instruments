#!/usr/bin/env python3
"""Check local links in Markdown using CommonMark tokens (never execute content).

Validation tooling dependency: markdown-it-py. Handles inline, image and reference
links, fenced/inline code and common GitHub-style heading fragments.
"""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations

# Импортирует модуль или имена, используемые в этом файле.
import re
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
from urllib.parse import unquote, urlsplit

# Импортирует модуль или имена, используемые в этом файле.
from markdown_it import MarkdownIt

# Сохраняет или обновляет вычисленное значение для последующих операций.
_PARSER = MarkdownIt('commonmark', {'html': False, 'linkify': False})
# Сохраняет или обновляет вычисленное значение для последующих операций.
_HTML_ANCHOR_RE = re.compile(r'<(?:a|\w+)\s+[^>]*?\b(?:id|name)=[\'\"]([^\'\"]+)[\'\"]', re.I)


# Объявляет функцию _headings и её параметры.
def _headings(path: Path) -> set[str]:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    markdown = path.read_text(encoding = 'utf-8-sig')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    tokens = _PARSER.parse(markdown)
    # Устанавливает поле names в словаре или описании.
    names: set[str] = set()
    # Устанавливает поле repeats в словаре или описании.
    repeats: dict[str, int] = {}
    # Перебирает элементы набора для последовательной обработки.
    for index, token in enumerate(tokens):
        # Проверяет условие перед выполнением следующего блока.
        if token.type != 'heading_open':
            # Переходит к следующей итерации цикла.
            continue
        # Проверяет условие перед выполнением следующего блока.
        if index + 1 >= len(tokens):
            # Переходит к следующей итерации цикла.
            continue
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        inline = tokens[index + 1]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        text = ''.join(child.content for child in inline.children or []
                       # Проверяет условие перед выполнением следующего блока.
                       if child.type in ('text', 'code_inline', 'html_inline', 'image'))
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        text = re.sub(r'<[^>]*>', '', text)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        text = re.sub(r'[^\w\s-]', '', text.casefold(), flags = re.UNICODE).strip()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        slug = re.sub(r'\s+', '-', text)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        count = repeats.get(slug, 0)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        repeats[slug] = count + 1
        # Проверяет условие перед выполнением следующего блока.
        if count:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            slug = f'{slug}-{count}'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        names.add(slug)
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    names.update(_HTML_ANCHOR_RE.findall(markdown))
    # Возвращает вычисленный результат вызывающему коду.
    return names


# Объявляет функцию _links и её параметры.
def _links(path: Path):
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    text = path.read_text(encoding = 'utf-8-sig')
    # Перебирает элементы набора для последовательной обработки.
    for token in _PARSER.parse(text):
        # Проверяет условие перед выполнением следующего блока.
        if token.type != 'inline':
            # Переходит к следующей итерации цикла.
            continue
        # Перебирает элементы набора для последовательной обработки.
        for item in token.children or []:
            # Проверяет условие перед выполнением следующего блока.
            if item.type == 'link_open':
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                url = item.attrGet('href')
            # Проверяет альтернативное условие.
            elif item.type == 'image':
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                url = item.attrGet('src')
            # Выполняет ветку, когда предыдущие условия не сработали.
            else:
                # Переходит к следующей итерации цикла.
                continue
            # Проверяет условие перед выполнением следующего блока.
            if url:
                # Возвращает очередное значение генератора.
                yield url, (token.map[0] + 1 if token.map else None)


# Объявляет функцию check_markdown_links и её параметры.
def check_markdown_links(root: Path, paths: list[Path] | None = None) -> tuple[list[str], list[str]]:
    """Return errors, warnings for local links under root; no external access.

    Root-relative site links and remote URLs cannot be verified locally; warn
    for site-root links rather than silently treating them as valid.
    """
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    root = root.resolve(strict = True)
    # Устанавливает поле errors в словаре или описании.
    errors: list[str] = []
    # Устанавливает поле warnings в словаре или описании.
    warnings: list[str] = []
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    targets = sorted(paths if paths is not None else root.rglob('*.md'))
    # Устанавливает поле heading_cache в словаре или описании.
    heading_cache: dict[Path, set[str]] = {}
    # Перебирает элементы набора для последовательной обработки.
    for p in targets:
        # Проверяет условие перед выполнением следующего блока.
        if not p.is_file():
            # Переходит к следующей итерации цикла.
            continue
        # Начинает блок с контролируемой обработкой исключений.
        try:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            relative = p.relative_to(root)
        # Перехватывает указанное исключение для безопасной обработки.
        except ValueError:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            errors.append(f'{p}: Markdown source outside root')
            # Переходит к следующей итерации цикла.
            continue
        # Перебирает элементы набора для последовательной обработки.
        for raw, line in _links(p):
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            where = f'{relative}:{line}' if line is not None else str(relative)
            # Проверяет условие перед выполнением следующего блока.
            if raw.startswith('//'):
                # Переходит к следующей итерации цикла.
                continue
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            parsed = urlsplit(raw)
            # Проверяет условие перед выполнением следующего блока.
            if parsed.scheme or parsed.netloc:
                # Переходит к следующей итерации цикла.
                continue
            # Проверяет условие перед выполнением следующего блока.
            if parsed.path.startswith('/'):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                warnings.append(f'{where}: site-root link cannot be checked locally: {raw}')
                # Переходит к следующей итерации цикла.
                continue
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            rel_path = unquote(parsed.path)
            # Проверяет условие перед выполнением следующего блока.
            if '\\' in rel_path or '\x00' in rel_path:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append(f'{where}: invalid local link path: {raw}')
                # Переходит к следующей итерации цикла.
                continue
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            candidate = (p.parent / rel_path).resolve()
            # Проверяет условие перед выполнением следующего блока.
            if not candidate.is_relative_to(root):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append(f'{where}: link escapes package: {raw}')
                # Переходит к следующей итерации цикла.
                continue
            # Проверяет условие перед выполнением следующего блока.
            if not candidate.exists():
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append(f'{where}: missing local link target: {raw}')
                # Переходит к следующей итерации цикла.
                continue
            # Проверяет условие перед выполнением следующего блока.
            if not candidate.is_file() and not candidate.is_dir():
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                errors.append(f'{where}: unreadable local link target: {raw}')
                # Переходит к следующей итерации цикла.
                continue
            # Проверяет условие перед выполнением следующего блока.
            if parsed.fragment and candidate.is_file() and candidate.suffix.lower() == '.md':
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                fragment = unquote(parsed.fragment)
                # Проверяет условие перед выполнением следующего блока.
                if candidate not in heading_cache:
                    # Сохраняет или обновляет вычисленное значение для последующих операций.
                    heading_cache[candidate] = _headings(candidate)
                # Проверяет условие перед выполнением следующего блока.
                if fragment not in heading_cache[candidate]:
                    # Формирует часть выражения или передаёт аргумент в текущую операцию.
                    errors.append(f'{where}: unknown Markdown heading fragment: {raw}')
    # Возвращает вычисленный результат вызывающему коду.
    return errors, warnings
