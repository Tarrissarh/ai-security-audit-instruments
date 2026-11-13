"""benchmark tests: evaluate data only, never execute fixture tools."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'quality/scripts'))
import evaluate
import translation_lint

class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        q = ROOT / 'quality'
        cls.gold = evaluate.load_json(q / 'gold/cases.json')
        cls.perfect = evaluate.load_json(q / 'examples/predictions-perfect.json')
        cls.empty = evaluate.load_json(q / 'examples/predictions-empty.json')
        cls.false_positive = evaluate.load_json(q / 'examples/predictions-false-positive.json')

    def score(self, pred):
        return evaluate.evaluate(self.gold, pred, ROOT)

    def test_gold_is_valid(self):
        evaluate.validate_gold(self.gold, ROOT)
        self.assertEqual(len(self.gold['cases']), 12)
        self.assertEqual(len({c['tool_type'] for c in self.gold['cases']}), 6)

    def test_perfect_synthetic_scoring(self):
        result = self.score(self.perfect)
        self.assertEqual(result['counts']['tp'], 11)
        self.assertEqual(result['counts']['fp'], 0)
        self.assertEqual(result['counts']['fn'], 0)
        self.assertEqual(result['metrics']['f1'], 1)
        self.assertEqual(result['metrics']['recommendation_recall'], 1)

    def test_per_type_metrics_exist(self):
        result = self.score(self.perfect)
        self.assertEqual(set(result['per_type']), {'skill', 'agent', 'command', 'mcp', 'lsp', 'hooks'})
        self.assertTrue(all(x['cases'] == 2 for x in result['per_type'].values()))

    def test_empty_output_not_passing(self):
        r = self.score(self.empty)
        self.assertEqual(r['counts']['fn'], 11)
        self.assertEqual(r['metrics']['f1'], 0)
        self.assertEqual(r['metrics']['severity_accuracy_on_detected'], None)

    def test_false_positive_penalized(self):
        r = self.score(self.false_positive)
        self.assertEqual(r['counts']['fp'], 1)
        self.assertEqual(r['metrics']['f1'], 0)

    def test_bad_evidence_rejected(self):
        p = copy.deepcopy(self.perfect)
        f = next(c['findings'][0] for c in p['cases'] if c['findings'])
        f['line'] = 9999
        result = self.score(p)
        self.assertEqual(result['counts']['tp'], 10)
        self.assertEqual(result['counts']['fp'], 1)
        self.assertEqual(result['counts']['fn'], 1)

    def test_line_must_be_integer(self):
        p = copy.deepcopy(self.perfect)
        next(c['findings'][0] for c in p['cases'] if c['findings'])['line'] = True
        self.assertEqual(self.score(p)['counts']['tp'], 10)

    def test_wrong_category_rejected(self):
        p = copy.deepcopy(self.perfect)
        next(c['findings'][0] for c in p['cases'] if c['findings'])['category'] = 'unsupported'
        self.assertEqual(self.score(p)['counts']['tp'], 10)

    def test_wrong_severity_counted_separately(self):
        p = copy.deepcopy(self.perfect)
        next(c['findings'][0] for c in p['cases'] if c['findings'])['severity'] = 'LOW'
        r = self.score(p)
        self.assertEqual(r['counts']['tp'], 11)
        self.assertEqual(r['counts']['severity_wrong'], 1)
        self.assertLess(r['metrics']['severity_accuracy_on_detected'], 1)

    def test_duplicate_finding_penalized(self):
        p = copy.deepcopy(self.perfect)
        c = next(c for c in p['cases'] if c['findings'])
        c['findings'].append(copy.deepcopy(c['findings'][0]))
        self.assertEqual(self.score(p)['counts']['fp'], 1)

    def test_missing_case_rejected(self):
        p = copy.deepcopy(self.perfect)
        p['cases'].pop()
        with self.assertRaisesRegex(evaluate.EvaluationError, 'every case'):
            self.score(p)

    def test_unknown_case_rejected(self):
        p = copy.deepcopy(self.perfect)
        p['cases'][0]['case_id'] = 'unknown'
        with self.assertRaisesRegex(evaluate.EvaluationError, 'every case'):
            self.score(p)

    def test_duplicate_case_rejected(self):
        p = copy.deepcopy(self.perfect)
        p['cases'].append(p['cases'][0])
        with self.assertRaisesRegex(evaluate.EvaluationError, 'Duplicate'):
            self.score(p)

    def test_unsupported_recommendation_penalized(self):
        p = copy.deepcopy(self.perfect)
        p['cases'][0]['recommendations'].append({'finding_ids': ['fake'],
            'priority': 'P1', 'change': 'change', 'rationale': 'reason', 'validation': 'test',
            'compatibility': 'check', 'rollback': 'undo'})
        r = self.score(p)
        self.assertEqual(r['counts']['recommendations_unsupported'], 1)

    def test_missing_recommendation_field_penalized(self):
        p = copy.deepcopy(self.perfect)
        x = next(c['recommendations'][0] for c in p['cases'] if c['recommendations'])
        x['validation'] = ''
        r = self.score(p)
        self.assertEqual(r['counts']['recommendations_unsupported'], 1)
        self.assertEqual(r['counts']['recommendations_missing'], 1)

    def test_gold_evidence_tamper_fails(self):
        g = copy.deepcopy(self.gold)
        next(c['expected_findings'][0] for c in g['cases'] if c['expected_findings'])['evidence_contains'] = 'absent-source-text'
        with self.assertRaises(evaluate.EvaluationError):
            evaluate.validate_gold(g, ROOT)

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(evaluate.EvaluationError):
            evaluate.safe_target(ROOT, '../anywhere')

    def test_gold_traversal_rejected(self):
        g = copy.deepcopy(self.gold)
        g['cases'][0]['target'] = '../../tmp'
        with self.assertRaises(evaluate.EvaluationError):
            evaluate.validate_gold(g, ROOT)

class TranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = ROOT / 'quality/examples/translations'
        cls.source = (d / 'original.md').read_text(encoding = 'utf8')
        cls.valid = (d / 'valid-ru.md').read_text(encoding = 'utf8')
        cls.invalid = (d / 'invalid-ru.md').read_text(encoding = 'utf8')

    def test_valid_translation(self):
        self.assertTrue(translation_lint.compare(self.source, self.valid)['ok'])

    def test_invalid_translation(self):
        result = translation_lint.compare(self.source, self.invalid)
        self.assertFalse(result['ok'])
        self.assertIn('code_fences_or_contents_changed', result['issues'])
        self.assertIn('frontmatter_machine_field_changed:name', result['issues'])
        self.assertIn('inline_code_changed', result['issues'])

    def test_placeholder_mismatch(self):
        bad = self.valid.replace('`{TARGET_PATH}`', '`{OTHER_PATH}`')
        r = translation_lint.compare(self.source, bad)
        self.assertIn('placeholders_changed', r['issues'])

    def test_broken_link(self):
        bad = self.valid.replace('(references/guide.md)', '(references/missing.md)')
        self.assertIn('markdown_link_targets_changed', translation_lint.compare(self.source, bad)['issues'])

    def test_explicit_link_remap(self):
        translated = self.valid.replace('(references/guide.md)', '(../references/guide.md)')
        self.assertTrue(translation_lint.compare(self.source, translated,
                         {'references/guide.md': '../references/guide.md'})['ok'])

    def test_fenced_code_changed(self):
        bad = self.valid.replace('"sample"', '"changed"')
        self.assertIn('code_fences_or_contents_changed', translation_lint.compare(self.source, bad)['issues'])

    def test_heading_omitted(self):
        bad = self.valid.replace('# Введение\n', '')
        self.assertIn('heading_count_changed', translation_lint.compare(self.source, bad)['issues'])

    def test_frontmatter_omitted(self):
        bad = self.valid.split('---\n', 2)[ - 1]
        self.assertIn('frontmatter_presence_changed', translation_lint.compare(self.source, bad)['issues'])

    def test_unclosed_fence(self):
        bad = self.valid.rsplit('```', 1)[0]
        self.assertIn('Unclosed Markdown code fence', translation_lint.compare(self.source, bad)['issues'])

    def test_url_change(self):
        original = 'Read https://example.org/manual'
        translated = 'Открой https://example.net/manual'
        self.assertIn('urls_changed', translation_lint.compare(original, translated)['issues'])

    def test_non_translated_meaning_not_measurable(self):
        # Синтаксис перевода сохранён, но смысл искажён: автоматическая проверка этого не распознает.
        bad = self.valid.replace('Используй плейсхолдер', 'Никогда не используй плейсхолдер')
        self.assertTrue(translation_lint.compare(self.source, bad)['ok'])

if __name__ == '__main__':
    unittest.main()
