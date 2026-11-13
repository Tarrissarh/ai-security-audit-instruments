# Описывает назначение блока в многострочной строке документации.
"""Local, read-only checks of validators and bundled skill conventions."""
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import sys, tempfile, unittest
# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
# Импортирует модуль или имена, используемые в этом файле.
from validate_skills import validate, read_frontmatter, NAME_RE, EXPECTED

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]

# Определяет класс и его интерфейс.
class TestBundle(unittest.TestCase):
    # Объявляет функцию test_expected_count и её параметры.
    def test_expected_count(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        found, errors, _ = validate(ROOT)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(set(found), EXPECTED)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(errors, '\n'.join(errors))
    # Объявляет функцию test_generator_manual_only и её параметры.
    def test_generator_manual_only(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        f, _ = read_frontmatter(ROOT / 'skills' / 'ai-tool-generator' / 'SKILL.md')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(f.get('disable-model-invocation'), 'true')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('явн', (ROOT / 'skills' / 'ai-tool-generator' / 'SKILL.md').read_text().lower())
    # Объявляет функцию test_deepseek_conditional и её параметры.
    def test_deepseek_conditional(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = (ROOT / 'skills/audit-workflow/references/platform-deepseek-harness.md').read_text()
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('dsh-skill-filesystem', p)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('dsh-tool-skill', p)
    # Объявляет функцию test_references_present и её параметры.
    def test_references_present(self):
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue((ROOT / 'skills/audit-workflow/references/handoff-contract.md').is_file())
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue((ROOT / 'skills/audit-docs/references/report-template.md').is_file())
    # Объявляет функцию test_name_regex и её параметры.
    def test_name_regex(self):
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(NAME_RE.fullmatch('audit-workflow'))
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(NAME_RE.fullmatch('Audit_Workflow'))
    # Объявляет функцию test_frontmatter_bad_input и её параметры.
    def test_frontmatter_bad_input(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d) / 'SKILL.md'
            # Настраивает аргументы, параметры или состояние объекта.
            p.write_text('not yaml\n')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            _, errs = read_frontmatter(p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue(errs)
    # Объявляет функцию test_workflow_no_automatic_generator и её параметры.
    def test_workflow_no_automatic_generator(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        s = (ROOT / 'skills/audit-workflow/SKILL.md').read_text().lower()
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('не вызывай', s)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('ai-tool-generator', s)

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Запускает автоматические проверки при прямом запуске файла.
    unittest.main()
