"""Cross-platform filename validation for trusted artifact and Skill publishers.

These rules reject names that are valid on POSIX but unsupported or ambiguous on
Windows. This is a portability preflight, not a defense against hostile filesystem
races or a guarantee that Windows ACLs permit access.

This module is mirrored in skills/audit-docs/scripts/portable_names.py because
installed Skills must work without files from the distribution's root scripts/.
"""

from __future__ import annotations

from pathlib import Path, PurePath
import stat
import unicodedata
from typing import Iterable

RESERVED_DEVICES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)

INVALID_CHARACTERS = frozenset('<>:"/\\|?*')

def validate_component(name: str) -> None:
    """Reject components with reserved/ambiguous Windows path syntax."""
    if name in ("", ".", ".."):
        raise ValueError(f"invalid portable path segment: {name!r}")
    if name.endswith((" ", ".")):
        raise ValueError(f"Windows trailing space/dot is not portable: {name!r}")
    if any(character in INVALID_CHARACTERS or ord(character) < 32 for character in name):
        raise ValueError(f"Windows invalid filename character: {name!r}")
    base_name = name.split(".", 1)[0].rstrip(" ").upper()
    for superscript, digit in (("¹", "1"), ("²", "2"), ("³", "3")):
        base_name = base_name.replace(superscript, digit)
    if base_name in RESERVED_DEVICES:
        raise ValueError(f"Windows reserved device filename: {name!r}")
    if len(name.encode("utf-16-le")) // 2 > 255:
        raise ValueError(f"Windows filename component exceeds 255 UTF-16 units: {name!r}")

def portable_key(relative_path: PurePath) -> str:
    """Return a case-insensitive NFC key and validate each path component."""
    if relative_path.is_absolute():
        raise ValueError(f"expected a relative path: {relative_path}")
    normalized_parts: list[str] = []
    for component in relative_path.parts:
        validate_component(component)
        normalized_parts.append(unicodedata.normalize("NFC", component).casefold())
    return "/".join(normalized_parts)

def find_collisions(paths: Iterable[PurePath]) -> list[str]:
    """Identify incompatible names and distinct paths that alias on Windows."""
    observed: dict[str, str] = {}
    errors: list[str] = []
    for item in paths:
        raw = item.as_posix()
        try:
            key = portable_key(item)
        except ValueError as error:
            errors.append(f"{raw}: {error}")
            continue
        previous = observed.get(key)
        if previous is not None and previous != raw:
            errors.append(f"Windows filename collision: {previous!r} vs {raw!r}")
        else:
            observed[key] = raw
    return errors

def assert_no_existing_aliases(root: Path, relative_paths: Iterable[Path]) -> None:
    """Reject existing entries differing only by case or Unicode normalization."""
    for relative_path in relative_paths:
        portable_key(relative_path)
        parent = root
        for component in relative_path.parts:
            if not parent.is_dir():
                break
            expected_key = unicodedata.normalize("NFC", component).casefold()
            for sibling in parent.iterdir():
                sibling_key = unicodedata.normalize("NFC", sibling.name).casefold()
                if sibling_key == expected_key and sibling.name != component:
                    raise ValueError(f"existing Windows filename alias: {sibling} vs {component!r}")
            parent = parent / component

def is_link_or_reparse_point(path: Path) -> bool:
    """Reject symlinks and Windows reparse points (including NTFS junctions)."""
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & flag)
