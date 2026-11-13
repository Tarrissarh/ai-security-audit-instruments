"""Контроль понятности комментариев и отсутствия релизных меток в рабочих файлах."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MaintainabilityTests(unittest.TestCase):
    """Не позволяет возвращать шумные комментарии и версии в названия файлов."""

    def test_unversioned_internal_filenames(self):
        # Внутренние скрипты и снимки данных должны называться по назначению.
        pattern = re.compile(r"(?i)(?:^|[-_])v[56](?:[._-]\d+)+")
        for path in ROOT.rglob("*"):
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(pattern.search(path.name))

    def test_no_generated_comments(self):
        # Проверяем только характерные фразы генератора, а не любые пояснения.
        forbidden = (
            "Объявляет функцию", "Сохраняет или обновляет вычисленное",
            "Проверяет условие перед выполнением", "Формирует часть выражения",
            "Возвращает вычисленный результат", "Проверяет ожидаемое поведение",
        )
        for path in ROOT.rglob("*.py"):
            with self.subTest(path=str(path.relative_to(ROOT))):
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.lstrip().startswith("#"):
                        self.assertFalse(any(token in line for token in forbidden))

    def test_no_releases_in_operational_documents(self):
        # Версии протоколов допускаются; заголовки истории выпусков — нет.
        marker = re.compile(r"(?im)^#{1,6}\s*(?:дополнение\s+)?v[56]\.\d+")
        for path in ROOT.rglob("*.md"):
            if path.name == "CHANGELOG.md":
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotRegex(path.read_text(encoding="utf-8"), marker)


if __name__ == "__main__":
    unittest.main()
