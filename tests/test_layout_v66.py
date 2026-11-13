"""Regression tests for portable package layout and Windows documentation."""

# Импортирует инструменты чтения путей и создания временных каталогов.
from pathlib import Path
# Импортирует инструменты тестирования и временного хранения.
import tempfile
# Импортирует стандартную библиотеку unittest.
import unittest
# Импортирует модуль без изменения исполняемого проекта.
import importlib.util

# Определяет корень исходного дистрибутива.
ROOT = Path(__file__).resolve().parents[1]
# Определяет корень только устанавливаемых скиллов.
SKILLS = ROOT / 'skills'
# Определяет путь к офлайн-установщику.
SCRIPT = ROOT / 'scripts' / 'platform_compat.py'
# Создаёт загрузочную спецификацию для локального модуля.
SPEC = importlib.util.spec_from_file_location('platform_compat_v66', SCRIPT)
# Загружает модуль по сформированной спецификации.
MODULE = importlib.util.module_from_spec(SPEC)
# Исполняет только доверенный модуль установщика пакета.
SPEC.loader.exec_module(MODULE)


# Определяет набор тестов нового расположения файлов.
class TestPortableLayout(unittest.TestCase):
    # Проверяет, что только каталоги скиллов лежат в устанавливаемом дереве.
    def test_only_skill_directories_in_installable_root(self):
        # Получает имена всех корневых элементов устанавливаемого дерева.
        names = {item.name for item in SKILLS.iterdir()}
        # Проверяет, что число и названия каталогов соответствуют манифесту.
        self.assertEqual(names, set(MODULE.IDS))
        # Проверяет наличие основного файла у каждого скилла.
        for identifier in MODULE.IDS:
            # Проверяет файл с действующей инструкцией инструмента.
            self.assertTrue((SKILLS / identifier / 'SKILL.md').is_file())
            # Проверяет отсутствие дубля скилла в корне дистрибутива.
            self.assertFalse((ROOT / identifier / 'SKILL.md').exists())

    # Проверяет правильность размещения файлов после установки.
    def test_installer_does_not_copy_developer_docs(self):
        # Создаёт временный проект, изолированный от пользователя.
        with tempfile.TemporaryDirectory() as temporary:
            # Представляет временный проект в виде Path.
            project = Path(temporary)
            # Выполняет установку в тестовый каталог без запуска AI-клиентов.
            result = MODULE.stage('claude-code', project, apply=True)
            # Убеждается, что установка тестовых файлов прошла корректно.
            self.assertEqual(result['status'], 'LOCAL_INSTALL_PASS')
            # Вычисляет путь к созданным каталогам скиллов.
            destination = project / '.claude' / 'skills'
            # Проверяет, что все 11 каталогов появились на месте.
            self.assertEqual({item.name for item in destination.iterdir()}, set(MODULE.IDS))
            # Проверяет, что документация и эталоны не попали в каталог клиента.
            for unrelated in ('WINDOWS.md', 'CHANGELOG.md', 'quality', 'integration', 'tests'):
                # Проверяет отсутствие неустановочных материалов.
                self.assertFalse((destination / unrelated).exists())

    # Проверяет, что для основных UNIX-путей существуют аналоги Windows.
    def test_windows_documentation_has_user_profile_variants(self):
        # Читает инструкцию платформенных путей без изменения файла.
        content = (ROOT / 'WINDOWS.md').read_text(encoding='utf-8')
        # Проверяет переменную Windows-профиля пользователя.
        self.assertIn('%USERPROFILE%', content)
        # Проверяет документацию переменной переопределения DeepSeek Harness.
        self.assertIn('DSH_HOME', content)
        # Проверяет предупреждение о возможном отличии конфигурации OpenCode.
        self.assertIn('XDG', content)
        # Проверяет наличие примера запуска из PowerShell.
        self.assertIn('py -3', content)

    # Проверяет, что журнал имеет стандартные секции и последовательность.
    def test_keep_a_changelog(self):
        # Загружает журнал изменений из корня пакета.
        changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        # Проверяет заголовок формата Keep a Changelog.
        self.assertTrue(changelog.startswith('# Changelog'))
        # Проверяет раздел ещё не выпущенных изменений.
        self.assertIn('## [Unreleased]', changelog)
        # Проверяет дату текущей версии.
        self.assertIn('## [6.6.0] - 2026-11-12', changelog)
        # Проверяет наличие архивной копии старых записей.
        self.assertFalse((ROOT / 'CHANGELOG-LEGACY.md').exists())


# Запускает проверки при прямом вызове файла пользователем.
if __name__ == '__main__':
    # Выполняет стандартный тестовый раннер.
    unittest.main()
