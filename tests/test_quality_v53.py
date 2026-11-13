# Описывает назначение блока в многострочной строке документации.
"""v5.3 benchmark tests: evaluate data only, never execute fixture tools."""
# Импортирует модуль или имена, используемые в этом файле.
import copy
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
import unittest

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(ROOT / 'quality/scripts'))
# Импортирует модуль или имена, используемые в этом файле.
import evaluate
# Импортирует модуль или имена, используемые в этом файле.
import translation_lint

# Определяет класс и его интерфейс.
class BenchmarkTests(unittest.TestCase):
    # Применяет указанный декоратор к следующему объявлению.
    @classmethod
    # Объявляет функцию setUpClass и её параметры.
    def setUpClass(cls):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        q = ROOT / 'quality'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cls.gold = evaluate.load_json(q / 'gold/cases.json')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cls.perfect = evaluate.load_json(q / 'examples/predictions-perfect.json')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cls.empty = evaluate.load_json(q / 'examples/predictions-empty.json')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cls.false_positive = evaluate.load_json(q / 'examples/predictions-false-positive.json')

    # Объявляет функцию score и её параметры.
    def score(self, pred):
        # Возвращает вычисленный результат вызывающему коду.
        return evaluate.evaluate(self.gold, pred, ROOT)

    # Объявляет функцию test_gold_is_valid и её параметры.
    def test_gold_is_valid(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        evaluate.validate_gold(self.gold, ROOT)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(len(self.gold['cases']), 12)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(len({c['tool_type'] for c in self.gold['cases']}), 6)

    # Объявляет функцию test_perfect_synthetic_scoring и её параметры.
    def test_perfect_synthetic_scoring(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = self.score(self.perfect)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['counts']['tp'], 11)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['counts']['fp'], 0)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['counts']['fn'], 0)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['metrics']['f1'], 1)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['metrics']['recommendation_recall'], 1)

    # Объявляет функцию test_per_type_metrics_exist и её параметры.
    def test_per_type_metrics_exist(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = self.score(self.perfect)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(set(result['per_type']), {'skill', 'agent', 'command', 'mcp', 'lsp', 'hooks'})
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(all(x['cases'] == 2 for x in result['per_type'].values()))

    # Объявляет функцию test_empty_output_not_passing и её параметры.
    def test_empty_output_not_passing(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = self.score(self.empty)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['counts']['fn'], 11)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['metrics']['f1'], 0)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['metrics']['severity_accuracy_on_detected'], None)

    # Объявляет функцию test_false_positive_penalized и её параметры.
    def test_false_positive_penalized(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = self.score(self.false_positive)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['counts']['fp'], 1)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['metrics']['f1'], 0)

    # Объявляет функцию test_bad_evidence_rejected и её параметры.
    def test_bad_evidence_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        f = next(c['findings'][0] for c in p['cases'] if c['findings'])
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        f['line'] = 9999
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = self.score(p)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['counts']['tp'], 10)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['counts']['fp'], 1)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(result['counts']['fn'], 1)

    # Объявляет функцию test_line_must_be_integer и её параметры.
    def test_line_must_be_integer(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Вызывает функцию для выполнения операции.
        next(c['findings'][0] for c in p['cases'] if c['findings'])['line'] = True
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(self.score(p)['counts']['tp'], 10)

    # Объявляет функцию test_wrong_category_rejected и её параметры.
    def test_wrong_category_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Вызывает функцию для выполнения операции.
        next(c['findings'][0] for c in p['cases'] if c['findings'])['category'] = 'unsupported'
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(self.score(p)['counts']['tp'], 10)

    # Объявляет функцию test_wrong_severity_counted_separately и её параметры.
    def test_wrong_severity_counted_separately(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Вызывает функцию для выполнения операции.
        next(c['findings'][0] for c in p['cases'] if c['findings'])['severity'] = 'LOW'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = self.score(p)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['counts']['tp'], 11)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['counts']['severity_wrong'], 1)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertLess(r['metrics']['severity_accuracy_on_detected'], 1)

    # Объявляет функцию test_duplicate_finding_penalized и её параметры.
    def test_duplicate_finding_penalized(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        c = next(c for c in p['cases'] if c['findings'])
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        c['findings'].append(copy.deepcopy(c['findings'][0]))
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(self.score(p)['counts']['fp'], 1)

    # Объявляет функцию test_missing_case_rejected и её параметры.
    def test_missing_case_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        p['cases'].pop()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(evaluate.EvaluationError, 'every case'):
            # Вызывает проверку или метод текущего объекта.
            self.score(p)

    # Объявляет функцию test_unknown_case_rejected и её параметры.
    def test_unknown_case_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        p['cases'][0]['case_id'] = 'unknown'
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(evaluate.EvaluationError, 'every case'):
            # Вызывает проверку или метод текущего объекта.
            self.score(p)

    # Объявляет функцию test_duplicate_case_rejected и её параметры.
    def test_duplicate_case_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        p['cases'].append(p['cases'][0])
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(evaluate.EvaluationError, 'Duplicate'):
            # Вызывает проверку или метод текущего объекта.
            self.score(p)

    # Объявляет функцию test_unsupported_recommendation_penalized и её параметры.
    def test_unsupported_recommendation_penalized(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        p['cases'][0]['recommendations'].append({'finding_ids': ['fake'],
            # Устанавливает поле priority в словаре или описании.
            'priority': 'P1', 'change': 'change', 'rationale': 'reason', 'validation': 'test',
            # Устанавливает поле compatibility в словаре или описании.
            'compatibility': 'check', 'rollback': 'undo'})
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = self.score(p)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['counts']['recommendations_unsupported'], 1)

    # Объявляет функцию test_missing_recommendation_field_penalized и её параметры.
    def test_missing_recommendation_field_penalized(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = copy.deepcopy(self.perfect)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        x = next(c['recommendations'][0] for c in p['cases'] if c['recommendations'])
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        x['validation'] = ''
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = self.score(p)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['counts']['recommendations_unsupported'], 1)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(r['counts']['recommendations_missing'], 1)

    # Объявляет функцию test_gold_evidence_tamper_fails и её параметры.
    def test_gold_evidence_tamper_fails(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        g = copy.deepcopy(self.gold)
        # Вызывает функцию для выполнения операции.
        next(c['expected_findings'][0] for c in g['cases'] if c['expected_findings'])['evidence_contains'] = 'absent-source-text'
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaises(evaluate.EvaluationError):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            evaluate.validate_gold(g, ROOT)

    # Объявляет функцию test_path_traversal_is_rejected и её параметры.
    def test_path_traversal_is_rejected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaises(evaluate.EvaluationError):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            evaluate.safe_target(ROOT, '../anywhere')

    # Объявляет функцию test_gold_traversal_rejected и её параметры.
    def test_gold_traversal_rejected(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        g = copy.deepcopy(self.gold)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        g['cases'][0]['target'] = '../../tmp'
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaises(evaluate.EvaluationError):
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            evaluate.validate_gold(g, ROOT)

# Определяет класс и его интерфейс.
class TranslationTests(unittest.TestCase):
    # Применяет указанный декоратор к следующему объявлению.
    @classmethod
    # Объявляет функцию setUpClass и её параметры.
    def setUpClass(cls):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        d = ROOT / 'quality/examples/translations'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cls.source = (d / 'original.md').read_text(encoding = 'utf8')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cls.valid = (d / 'valid-ru.md').read_text(encoding = 'utf8')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        cls.invalid = (d / 'invalid-ru.md').read_text(encoding = 'utf8')

    # Объявляет функцию test_valid_translation и её параметры.
    def test_valid_translation(self):
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(translation_lint.compare(self.source, self.valid)['ok'])

    # Объявляет функцию test_invalid_translation и её параметры.
    def test_invalid_translation(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        result = translation_lint.compare(self.source, self.invalid)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertFalse(result['ok'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('code_fences_or_contents_changed', result['issues'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('frontmatter_machine_field_changed:name', result['issues'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('inline_code_changed', result['issues'])

    # Объявляет функцию test_placeholder_mismatch и её параметры.
    def test_placeholder_mismatch(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        bad = self.valid.replace('`{TARGET_PATH}`', '`{OTHER_PATH}`')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        r = translation_lint.compare(self.source, bad)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('placeholders_changed', r['issues'])

    # Объявляет функцию test_broken_link и её параметры.
    def test_broken_link(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        bad = self.valid.replace('(references/guide.md)', '(references/missing.md)')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('markdown_link_targets_changed', translation_lint.compare(self.source, bad)['issues'])

    # Объявляет функцию test_explicit_link_remap и её параметры.
    def test_explicit_link_remap(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        translated = self.valid.replace('(references/guide.md)', '(../references/guide.md)')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(translation_lint.compare(self.source, translated,
                         # Формирует часть выражения или передаёт аргумент в текущую операцию.
                         {'references/guide.md': '../references/guide.md'})['ok'])

    # Объявляет функцию test_fenced_code_changed и её параметры.
    def test_fenced_code_changed(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        bad = self.valid.replace('"sample"', '"changed"')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('code_fences_or_contents_changed', translation_lint.compare(self.source, bad)['issues'])

    # Объявляет функцию test_heading_omitted и её параметры.
    def test_heading_omitted(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        bad = self.valid.replace('# Введение\n', '')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('heading_count_changed', translation_lint.compare(self.source, bad)['issues'])

    # Объявляет функцию test_frontmatter_omitted и её параметры.
    def test_frontmatter_omitted(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        bad = self.valid.split('---\n', 2)[ - 1]
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('frontmatter_presence_changed', translation_lint.compare(self.source, bad)['issues'])

    # Объявляет функцию test_unclosed_fence и её параметры.
    def test_unclosed_fence(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        bad = self.valid.rsplit('```', 1)[0]
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('Unclosed Markdown code fence', translation_lint.compare(self.source, bad)['issues'])

    # Объявляет функцию test_url_change и её параметры.
    def test_url_change(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        original = 'Read https://example.org/manual'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        translated = 'Открой https://example.net/manual'
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIn('urls_changed', translation_lint.compare(original, translated)['issues'])

    # Объявляет функцию test_non_translated_meaning_not_measurable и её параметры.
    def test_non_translated_meaning_not_measurable(self):
        # Both texts keep formal structure, but meaning is wrong; semantic judge needed.
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        bad = self.valid.replace('Используй плейсхолдер', 'Никогда не используй плейсхолдер')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertTrue(translation_lint.compare(self.source, bad)['ok'])

# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    unittest.main()
