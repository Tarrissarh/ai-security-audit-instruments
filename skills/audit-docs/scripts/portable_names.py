"""Cross-platform filename validation for trusted artifact and Skill publishers.

These rules reject names that are valid on POSIX but unsupported or ambiguous on
Windows. This is a portability preflight, not a defense against hostile filesystem
races or a guarantee that Windows ACLs permit access.

This module is mirrored in skills/audit-docs/scripts/portable_names.py because
installed Skills must work without files from the distribution's root scripts/.
"""

# Позволяет использовать современные аннотации типов без раннего вычисления.
from __future__ import annotations

# Предоставляет платформенно-нейтральное представление относительных путей.
from pathlib import Path, PurePath
# Проверяет Windows-атрибуты reparse points, включая NTFS junctions.
import stat
# Нормализует Unicode, чтобы распознать эквивалентные имена файлов.
import unicodedata
# Позволяет проверять коллекции файлов и каталогов.
from typing import Iterable

# Зарезервированные имена Windows нельзя использовать даже с расширением.
RESERVED_DEVICES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)

# Символы ниже запрещены в имени компонента файловой системы Windows.
INVALID_CHARACTERS = frozenset('<>:"/\\|?*')


def validate_component(name: str) -> None:
    """Reject components with reserved/ambiguous Windows path syntax."""
    # Исключает пустой сегмент, '.' и '..'.
    if name in ("", ".", ".."):
        raise ValueError(f"invalid portable path segment: {name!r}")
    # Windows удаляет или запрещает завершающие пробелы и точки.
    if name.endswith((" ", ".")):
        raise ValueError(f"Windows trailing space/dot is not portable: {name!r}")
    # Исключает недопустимые символы и управляющие коды ASCII.
    if any(character in INVALID_CHARACTERS or ord(character) < 32 for character in name):
        raise ValueError(f"Windows invalid filename character: {name!r}")
    # Проверяет базовое имя до точки, чтобы отклонить 'CON.txt' и аналоги.
    base_name = name.split(".", 1)[0].rstrip(" ").upper()
    # Windows дополнительно распознаёт COM/LPT с цифрами-надстрочными знаками.
    for superscript, digit in (("¹", "1"), ("²", "2"), ("³", "3")):
        # Приводит служебную надстрочную цифру к обычной для сравнения.
        base_name = base_name.replace(superscript, digit)
    # Windows резервирует имена устройств независимо от регистра.
    if base_name in RESERVED_DEVICES:
        raise ValueError(f"Windows reserved device filename: {name!r}")
    # NTFS обычно ограничивает компонент 255 единицами UTF-16.
    if len(name.encode("utf-16-le")) // 2 > 255:
        raise ValueError(f"Windows filename component exceeds 255 UTF-16 units: {name!r}")


def portable_key(relative_path: PurePath) -> str:
    """Return a case-insensitive NFC key and validate each path component."""
    # Запрещает абсолютные пути, чтобы применять проверку к относительным целям.
    if relative_path.is_absolute():
        raise ValueError(f"expected a relative path: {relative_path}")
    # Собирает нормализованные компоненты отдельно от фактических имён.
    normalized_parts: list[str] = []
    # Проверяет каждый компонент исходного относительного пути.
    for component in relative_path.parts:
        # Проверяет совместимость конкретного имени с Windows.
        validate_component(component)
        # Приводит Unicode к NFC и применяет Unicode casefold.
        normalized_parts.append(unicodedata.normalize("NFC", component).casefold())
    # Объединяет ключи через универсальный разделитель для сравнения.
    return "/".join(normalized_parts)


def find_collisions(paths: Iterable[PurePath]) -> list[str]:
    """Identify incompatible names and distinct paths that alias on Windows."""
    # Хранит ранее встреченные нормализованные имена путей.
    observed: dict[str, str] = {}
    # Накапливает диагностические сообщения, не прерывая остальные проверки.
    errors: list[str] = []
    # Перебирает все исходные относительные пути.
    for item in paths:
        # Представляет путь в стабильном виде с разделителем '/'.
        raw = item.as_posix()
        # Обрабатывает невалидные пути как диагностическую ошибку.
        try:
            # Создаёт нормализованный ключ для этого файла или каталога.
            key = portable_key(item)
        # Сохраняет причину несовместимости пути.
        except ValueError as error:
            errors.append(f"{raw}: {error}")
            # Продолжает проверку остальных компонентов.
            continue
        # Получает путь, занявший тот же ключ на Windows.
        previous = observed.get(key)
        # Сообщает о конфликте, только если имена действительно отличаются.
        if previous is not None and previous != raw:
            errors.append(f"Windows filename collision: {previous!r} vs {raw!r}")
        # Для последующих сравнений запоминает первое имя.
        else:
            observed[key] = raw
    # Возвращает полный список выявленных проблем переносимости.
    return errors


def assert_no_existing_aliases(root: Path, relative_paths: Iterable[Path]) -> None:
    """Reject existing entries differing only by case or Unicode normalization."""
    # Проверяет каждый путь, который планируется записать в дерево.
    for relative_path in relative_paths:
        # Проверяет, что относительный путь переносим между ОС.
        portable_key(relative_path)
        # Начинает обход от заданного корня каталога.
        parent = root
        # Перебирает составляющие целевого пути слева направо.
        for component in relative_path.parts:
            # Не выполняет обход, если следующий родитель ещё не создан.
            if not parent.is_dir():
                break
            # Вычисляет Windows-совместимый ключ нужного компонента.
            expected_key = unicodedata.normalize("NFC", component).casefold()
            # Сверяет имена уже находящихся в родительском каталоге элементов.
            for sibling in parent.iterdir():
                # Нормализует имя соседнего файла без модификации исходника.
                sibling_key = unicodedata.normalize("NFC", sibling.name).casefold()
                # Отклоняет неоднозначное имя независимо от ОС сборки.
                if sibling_key == expected_key and sibling.name != component:
                    raise ValueError(f"existing Windows filename alias: {sibling} vs {component!r}")
            # Переходит к следующему уровню целевого пути.
            parent = parent / component


def is_link_or_reparse_point(path: Path) -> bool:
    """Reject symlinks and Windows reparse points (including NTFS junctions)."""
    # Проверяет обычные символические ссылки на Linux, macOS и Windows.
    if path.is_symlink():
        # Немедленно сообщает вызывающему коду о небезопасной ссылке.
        return True
    # Получает свойства самого элемента, не переходя по ссылкам.
    try:
        # Запрашивает метаданные файла без разыменования NTFS reparse point.
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    # Отсутствующие элементы пути не являются существующими reparse points.
    except FileNotFoundError:
        # Продолжение пути может быть безопасно создано позднее.
        return False
    # Получает флаг Windows FILE_ATTRIBUTE_REPARSE_POINT, если он объявлен.
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    # Запрещает junctions и прочие reparse points при ненулевом флаге.
    return bool(attributes & flag)
