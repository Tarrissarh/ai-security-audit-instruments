"""Regression tests for Windows/Linux portability without running AI clients."""

# Загружает модули из пакета независимо от рабочего каталога тестов.
import importlib.util
# Предоставляет операции chmod для проверки read-only файлов.
import os
# Позволяет строить реальные и Windows-пути без запуска Windows.
from pathlib import Path, PureWindowsPath
# Создаёт независимые копии тестовых файлов.
import shutil
# Подключает путь к автономным скриптам установленных скиллов.
import sys
# Создаёт временные директории для безопасных операций.
import tempfile
# Даёт инструменты unittest и подмены системных вызовов.
import unittest
from unittest import mock

# Вычисляет корень комплекта для повторяемых запусков на любой ОС.
ROOT = Path(__file__).resolve().parents[1]
# Указывает каталог проверочного установщика пакета.
SCRIPTS = ROOT / 'scripts'
# Указывает автономный каталог скриптов audit-docs.
WRITER_SCRIPTS = ROOT / 'skills' / 'audit-docs' / 'scripts'

# Добавляет оба каталога в стандартный путь импортов теста.
for directory in (SCRIPTS, WRITER_SCRIPTS):
    # Сохраняет абсолютную строку пути каталога модулей.
    directory_text = str(directory)
    # Исключает повторную вставку в список путей.
    if directory_text not in sys.path:
        # Разрешает импорт только доверенных модулей из текущего пакета.
        sys.path.insert(0, directory_text)

# Загружает общий проверяющий модуль имён из корневого каталога.
import portable_names
# Загружает безопасный модуль публикации отчётов.
import safe_writer

# Создаёт спецификацию загрузки установщика без установки самого пакета.
SPEC = importlib.util.spec_from_file_location('platform_compat_v67', SCRIPTS / 'platform_compat.py')
# Создаёт объект доверенного модуля по спецификации.
INSTALLER = importlib.util.module_from_spec(SPEC)
# Исполняет модуль установщика, не вызывая ни один AI-клиент.
SPEC.loader.exec_module(INSTALLER)


# Группирует проверки Windows-совместимости имён путей.
class PortableNameTests(unittest.TestCase):
    # Проверяет запрет зарезервированных имён Windows с расширением.
    def test_windows_device_names(self):
        # Перебирает несколько устройств, которые Windows трактует особым образом.
        for filename in ('CON.md', 'prn.txt', 'AUX', 'LPT9.md', 'com1.py', 'COM¹.md', 'nul.json'):
            # Выводит проверяемое имя в случае неудачи теста.
            with self.subTest(filename=filename):
                # Подтверждает запрет неподходящего имени файла.
                with self.assertRaises(ValueError):
                    # Валидирует один компонент пути.
                    portable_names.validate_component(filename)

    # Проверяет запрет проблемных завершающих символов и двоеточия.
    def test_forbidden_names_and_characters(self):
        # Перебирает примеры имён, которые Windows не сможет сохранить.
        for filename in ('report.', 'report ', 'a:b.md', 'a?.md', 'bad\x01.md'):
            # Добавляет имя к диагностике конкретного запуска.
            with self.subTest(filename=filename):
                # Требует контролируемую ошибку.
                with self.assertRaises(ValueError):
                    # Проверяет имя без создания файлов.
                    portable_names.validate_component(filename)

    # Проверяет ограничение длины имени в единицах UTF-16.
    def test_windows_utf16_component_length(self):
        # Создаёт имя из эмодзи, которое превышает ограничение Windows.
        too_long = '🔍' * 128
        # Проверяет, что имя отклоняется до попытки записи.
        with self.assertRaises(ValueError):
            # Передаёт имя валидатору.
            portable_names.validate_component(too_long)

    # Проверяет переносимые Unicode-имена без транслитерации.
    def test_portable_unicode_names(self):
        # Использует кириллицу, пробел и японские символы.
        path = Path('docs') / 'Обзор_日本語.md'
        # Проверяет, что нормализация не повреждает путь.
        self.assertTrue(portable_names.portable_key(path))

    # Проверяет конфликт различного регистра на Windows.
    def test_casefold_collision(self):
        # Передаёт два разных POSIX-пути с одним Windows-именем.
        errors = portable_names.find_collisions([Path('docs/Report.md'), Path('docs/report.md')])
        # Убеждается в наличии диагностического сообщения.
        self.assertTrue(any('collision' in error for error in errors))

    # Проверяет конфликт одинаковых букв в NFC и NFD Unicode.
    def test_unicode_normalization_collision(self):
        # Создаёт имена, одинаковые визуально, но разные по байтам Unicode.
        errors = portable_names.find_collisions([Path('docs/é.md'), Path('docs/e\u0301.md')])
        # Требует обнаружения несовместимости без файловой системы.
        self.assertTrue(any('collision' in error for error in errors))

    # Проверяет совпадение алгоритмов в установщике и автономном audit-docs.
    def test_installed_writer_matches_root_portability_rules(self):
        # Изолированно загружает второй модуль правил из установленного Skill.
        spec = importlib.util.spec_from_file_location('writer_portable_names_v67', WRITER_SCRIPTS / 'portable_names.py')
        # Создаёт модуль по спецификации для независимой сверки.
        installed_module = importlib.util.module_from_spec(spec)
        # Выполняет независимый модуль без внешних команд.
        spec.loader.exec_module(installed_module)
        # Сверяет результаты для характерных путей и коллизий.
        samples = [Path('docs/é.md'), Path('docs/e\u0301.md'), Path('docs/readme.md')]
        # Гарантирует совпадение диагностики в двух местах использования.
        self.assertEqual(portable_names.find_collisions(samples), installed_module.find_collisions(samples))

    # Проверяет обнаружение NTFS junction по Windows-атрибутам, даже без symlink.
    def test_windows_reparse_attribute(self):
        # Подготавливает фиктивные метаданные Windows без настоящего NTFS.
        fake_metadata = mock.Mock(st_file_attributes=0x400)
        # Подменяет операции файловой системы у чисто тестового пути.
        with mock.patch.object(Path, 'is_symlink', return_value=False):
            # Подставляет системный атрибут FILE_ATTRIBUTE_REPARSE_POINT.
            with mock.patch.object(Path, 'lstat', return_value=fake_metadata):
                # Проверяет, что NTFS junction будет заблокирован.
                self.assertTrue(portable_names.is_link_or_reparse_point(Path('test-junction')))

    # Проверяет корректный разбор системных путей Windows без обращения к NTFS.
    def test_pure_windows_project_path(self):
        # Формирует типовой абсолютный путь Windows.
        root = PureWindowsPath(r'C:\Work\Проект')
        # Проверяет, что дочерний путь имеет правильные разделители Windows.
        self.assertEqual(str(root / '.claude' / 'skills'), r'C:\Work\Проект\.claude\skills')


# Объединяет сценарии установки на реальном временном POSIX/Windows каталоге.
class PortableInstallerTests(unittest.TestCase):
    # Проверяет отказ при различии регистра уже установленного идентификатора.
    def test_existing_case_variant_blocks_install(self):
        # Создаёт отдельную файловую песочницу.
        with tempfile.TemporaryDirectory() as directory:
            # Формирует путь существующего рабочего проекта.
            project = Path(directory)
            # Создаёт конфликтующий каталог с другим регистром.
            (project / '.claude/skills/Audit-Docs').mkdir(parents=True)
            # Получает план без записи новых файлов.
            result = INSTALLER.stage('claude-code', project)
            # Проверяет, что установка запрещена.
            self.assertEqual(result['status'], 'BLOCKED')
            # Проверяет присутствие причины конфликта в результатах.
            self.assertTrue(any('alias' in item for item in result['errors']))
            # Проверяет отсутствие скопированных скиллов.
            self.assertFalse((project / '.claude/skills/audit-workflow').exists())

    # Проверяет защиту от непереносимого имени во вложенных файлах скиллов.
    def test_source_reserved_filename_blocks_install(self):
        # Создаёт временный источник на основе безопасного пакета.
        with tempfile.TemporaryDirectory() as directory:
            # Формирует путь клонированного каталога.
            clone = Path(directory) / 'skills'
            # Копирует исходный пакет без выполнения скриптов.
            shutil.copytree(ROOT / 'skills', clone)
            # Добавляет специально неправильное имя в раздел справочников.
            (clone / 'audit-docs/references/CON.md').write_text('test', encoding='utf-8')
            # Анализирует имена и структуру локального комплекта.
            issues = INSTALLER.validate_bundle(clone)
            # Проверяет, что некорректное имя остановит установку.
            self.assertTrue(any('reserved device' in issue for issue in issues))


# Проверяет публикацию отчётов и резервных копий без запуска AI-инструментов.
class PortableWriterTests(unittest.TestCase):
    # Создаёт тестовые каталоги и стандартные Markdown-файлы.
    def setUp(self):
        # Создаёт временную песочницу.
        self.temporary = tempfile.TemporaryDirectory()
        # Формирует путь к корню временной директории.
        self.root = Path(self.temporary.name)
        # Формирует каталог для готовых проверенных документов.
        self.staging = self.root / 'staging'
        # Формирует отдельный каталог назначения.
        self.output = self.root / 'output'
        # Создаёт корень исходных документов.
        self.staging.mkdir()
        # Записывает обязательный исходный отчёт.
        (self.staging / 'README.md').write_text('# Отчёт\n', encoding='utf-8')

    # Удаляет тестовые каталоги после проверки.
    def tearDown(self):
        # Гарантирует удаление временной песочницы.
        self.temporary.cleanup()

    # Проверяет сохранность Unicode, UTF-8 BOM и CRLF по байтам.
    def test_utf8_bom_crlf_and_unicode_preserved(self):
        # Подготавливает кириллический документ с исходными окончаниями строк.
        content = b'\xef\xbb\xbf' + '# Отчёт\r\nОписание ✅\r\n'.encode('utf-8')
        # Записывает документ без преобразования переводов строк.
        (self.staging / 'README.md').write_bytes(content)
        # Публикует проверенные файлы в пустой каталог.
        result = safe_writer.publish(self.staging, self.output)
        # Требует успешной публикации.
        self.assertEqual(result['status'], 'COMPLETE')
        # Проверяет точное сохранение байтов BOM, Unicode и CRLF.
        self.assertEqual((self.output / 'README.md').read_bytes(), content)

    # Проверяет резервные копии с Unicode/CRLF и SHA-256.
    def test_backup_bytes_preserved(self):
        # Подготавливает старый отчёт с CRLF в отдельном каталоге.
        old = '# Старый отчёт\r\n'.encode('utf-8')
        # Создаёт каталог назначения.
        self.output.mkdir()
        # Записывает старое содержимое.
        (self.output / 'README.md').write_bytes(old)
        # Выполняет явную перезапись с обязательным резервированием.
        result = safe_writer.publish(self.staging, self.output, overwrite=True)
        # Проверяет создание каталога резервных копий.
        self.assertIsNotNone(result['backups'])
        # Проверяет совпадение байтов до и после копирования.
        self.assertEqual((Path(result['backups']) / 'README.md').read_bytes(), old)
        # Проверяет, что новый отчёт записан на место.
        self.assertIn('Отчёт', (self.output / 'README.md').read_text(encoding='utf-8'))

    # Проверяет отказ при попытке заменить Windows read-only или POSIX 0444 файл.
    def test_read_only_existing_report_blocked(self):
        # Создаёт каталог назначения.
        self.output.mkdir()
        # Подготавливает старый файл для попытки перезаписи.
        target = self.output / 'README.md'
        # Записывает исходные байты для подтверждения неизменности.
        target.write_bytes(b'# Original\n')
        # Устанавливает read-only бит на существующем файле.
        target.chmod(0o444)
        # Гарантирует восстановление прав после теста.
        try:
            # Требует блокировки опасной перезаписи.
            with self.assertRaises(safe_writer.PublishError):
                # Запрашивает публикацию с разрешённой перезаписью.
                safe_writer.publish(self.staging, self.output, overwrite=True)
            # Проверяет, что старое содержимое осталось без изменений.
            self.assertEqual(target.read_bytes(), b'# Original\n')
        # Восстанавливает права для удаления временного каталога.
        finally:
            # Возвращает право владельца на запись.
            target.chmod(0o644)

    # Проверяет защиту от существующего имени с несовпадающим регистром.
    def test_existing_case_variant_blocks_publish(self):
        # Создаёт родительский каталог назначения.
        self.output.mkdir()
        # Создаёт файл с отличающимся регистром.
        (self.output / 'readme.md').write_text('# Existing\n', encoding='utf-8')
        # Требует отказа до записи нового отчёта.
        with self.assertRaises(safe_writer.PublishError):
            # Пытается создать README.md поверх коллизии.
            safe_writer.publish(self.staging, self.output)

    # Проверяет защиту от ошибки доступа к файлу Windows-style.
    def test_locked_destination_is_not_overwritten(self):
        # Создаёт каталог назначения и старый документ.
        self.output.mkdir()
        # Вычисляет путь к существующему отчёту.
        target = self.output / 'README.md'
        # Записывает исходное содержимое для сравнения.
        target.write_bytes(b'# Original\n')
        # Имитирует ошибку Windows при замене занятого файла.
        with mock.patch.object(safe_writer.os, 'replace', side_effect=PermissionError('locked')):
            # Требует отказа с сохранением исходного файла.
            with self.assertRaises(safe_writer.PublishError):
                # Публикует новый документ в режиме явной перезаписи.
                safe_writer.publish(self.staging, self.output, overwrite=True)
        # Проверяет отсутствие изменения существующего отчёта.
        self.assertEqual(target.read_bytes(), b'# Original\n')

    # Проверяет отказ от имени файла устройства на POSIX через реальную публикацию.
    @unittest.skipIf(os.name == 'nt', 'Windows cannot create reserved device file in normal filesystem')
    def test_reserved_device_file_blocked_before_write(self):
        # Создаёт дополнительный справочник.
        folder = self.staging / 'docs'
        # Формирует каталог с документами.
        folder.mkdir()
        # Сохраняет файл с Windows-недопустимым именем на POSIX.
        (folder / 'CON.md').write_text('Document\n', encoding='utf-8')
        # Требует отказа до создания выходного каталога.
        with self.assertRaises(safe_writer.PublishError):
            # Пытается опубликовать некорректный отчёт.
            safe_writer.publish(self.staging, self.output)
        # Проверяет отсутствие записанных результатов.
        self.assertFalse(self.output.exists())


# Выполняет unit-тесты при прямом вызове файла.
if __name__ == '__main__':
    # Использует стандартный механизм тестирования unittest.
    unittest.main()
