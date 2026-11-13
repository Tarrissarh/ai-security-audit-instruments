# Описывает назначение блока в многострочной строке документации.
"""v6.0 offline integration tests; no AI client is executed."""
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import importlib.util
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
import unittest

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Сохраняет или обновляет вычисленное значение для последующих операций.
spec = importlib.util.spec_from_file_location('platform_compat', ROOT / 'scripts/platform_compat.py')
# Сохраняет или обновляет вычисленное значение для последующих операций.
platform_compat = importlib.util.module_from_spec(spec)
# Формирует часть выражения или передаёт аргумент в текущую операцию.
spec.loader.exec_module(platform_compat)

# Определяет класс и его интерфейс.
class TestPlatformCompatibility(unittest.TestCase):
    # Объявляет функцию test_all_five_native_staging_smokes и её параметры.
    def test_all_five_native_staging_smokes(self):
        # Перебирает элементы набора для последовательной обработки.
        for platform in platform_compat.PLATFORMS:
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.subTest(platform = platform):
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                result = platform_compat.smoke(platform)
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertEqual(result['install'], 'LOCAL_INSTALL_PASS')
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertEqual(result['local_discovery'], 'PASS')
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertEqual(result['skill_count'], 11)
                # Перебирает элементы набора для последовательной обработки.
                for k in ('real_client_discovery', 'real_client_activation', 'real_client_orchestration', 'real_client_safety'):
                    # Проверяет ожидаемое поведение средствами unittest.
                    self.assertEqual(result[k], 'NOT_TESTED')

    # Объявляет функцию test_shared_four_and_claude_reject и её параметры.
    def test_shared_four_and_claude_reject(self):
        # Перебирает элементы набора для последовательной обработки.
        for platform in ('opencode', 'deepseek-harness', 'codex', 'cursor'):
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with tempfile.TemporaryDirectory() as d:
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                project = Path(d)
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                result = platform_compat.stage(platform, project, 'shared', True)
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertEqual(result['status'], 'LOCAL_INSTALL_PASS')
                # Проверяет ожидаемое поведение средствами unittest.
                self.assertEqual(platform_compat.inspect(platform, project)['local_discovery_static'], 'PASS')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaises(ValueError):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                platform_compat.stage('claude-code', Path(d), 'shared', True)

    # Объявляет функцию test_dry_run_has_no_side_effects и её параметры.
    def test_dry_run_has_no_side_effects(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = platform_compat.stage('codex', p, 'native', False)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['status'], 'READY')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse((p / '.agents').exists())

    # Объявляет функцию test_staging_refuses_existing_and_no_overwrite и её параметры.
    def test_staging_refuses_existing_and_no_overwrite(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            existing = p / '.agents/skills/audit-docs'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            existing.mkdir(parents = True)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            sentinel = existing / 'SKILL.md'
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            sentinel.write_text('original')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            plan = platform_compat.stage('codex', p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(plan['status'], 'BLOCKED')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue(any('audit-docs' in e for e in plan['errors']))
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            applied = platform_compat.stage('codex', p, apply = True)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(applied['status'], 'BLOCKED')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(sentinel.read_text(), 'original')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse((p / '.agents/skills/audit-workflow').exists())

    # Объявляет функцию test_deduplicate_across_scanned_roots и её параметры.
    def test_deduplicate_across_scanned_roots(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / '.claude/skills/audit-skill').mkdir(parents = True)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / '.claude/skills/audit-skill/SKILL.md').write_text('anything')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = platform_compat.stage('cursor', p, apply = True)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['status'], 'BLOCKED')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse((p / '.cursor/skills').exists())

    # Объявляет функцию test_refuse_symlink_target и её параметры.
    def test_refuse_symlink_target(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (p / '.agents').symlink_to(outside, target_is_directory = True)
            # Открывает управляемый контекст и гарантирует его корректное завершение.
            with self.assertRaises(ValueError):
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                platform_compat.stage('codex', p, apply = True)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(list(Path(outside).iterdir()), [])

    # Объявляет функцию test_only_skill_dirs_and_no_benchmark_gold_are_installed и её параметры.
    def test_only_skill_dirs_and_no_benchmark_gold_are_installed(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            platform_compat.stage('opencode', p, apply = True)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            root = p / '.opencode/skills'
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(set(n.name for n in root.iterdir()), set(platform_compat.IDS))
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertFalse(any(f.name == 'cases.json' for f in root.rglob('*')))
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue((root / 'audit-workflow/references/preflight.md').is_file())
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertTrue((root / 'audit-docs/references/report-template.md').is_file())

    # Объявляет функцию test_generator_must_retain_manual_only_guard и её параметры.
    def test_generator_must_retain_manual_only_guard(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        f = platform_compat._read_frontmatter(ROOT / 'skills/ai-tool-generator/SKILL.md')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(f['disable-model-invocation'], 'true')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(platform_compat.validate_bundle(), [])

    # Объявляет функцию test_fake_malformed_skill_rejected и её параметры.
    def test_fake_malformed_skill_rejected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            b = Path(d)
            # Перебирает элементы набора для последовательной обработки.
            for name in platform_compat.IDS:
                # Сохраняет или обновляет вычисленное значение для последующих операций.
                t = b / name
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                t.mkdir()
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                (t / 'SKILL.md').write_text((ROOT / 'skills' / name / 'SKILL.md').read_text(encoding = 'utf-8'), encoding = 'utf-8')
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            (b / 'audit-skill/SKILL.md').write_text('---\nname: audit-skill\ndescription: [bad\n---\n')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = platform_compat.stage('codex', Path(d), bundle = b)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['status'], 'BLOCKED')

    # Объявляет функцию test_discovery_requires_all_skills_and_reports_not_tested и её параметры.
    def test_discovery_requires_all_skills_and_reports_not_tested(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            p = Path(d)
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            result = platform_compat.inspect('claude-code', p)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(len(result['missing']), 11)
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['local_discovery_static'], 'FAIL')
            # Проверяет ожидаемое поведение средствами unittest.
            self.assertEqual(result['client_runtime'], 'NOT_TESTED')

    # Объявляет функцию test_staged_source_bundle_unchanged и её параметры.
    def test_staged_source_bundle_unchanged(self):
        # Импортирует модуль или имена, используемые в этом файле.
        import hashlib
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = ROOT / 'skills/ai-tool-generator/SKILL.md'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        original = hashlib.sha256(p.read_bytes()).hexdigest()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with tempfile.TemporaryDirectory() as d:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            platform_compat.stage('cursor', Path(d), apply = True)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), original)

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Запускает автоматические проверки при прямом запуске файла.
    unittest.main()
