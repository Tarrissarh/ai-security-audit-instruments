"""Тесты генератора findings.json / report.sarif (audit-docs/scripts/emit_findings.py)."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'skills' / 'audit-docs' / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def _load_emit_findings():
    spec = importlib.util.spec_from_file_location('emit_findings', SCRIPTS / 'emit_findings.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


emit = _load_emit_findings()


class EmitFindingsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.doc = {
            'schema_version': '1.0',
            'target': {'path': '/tmp/skill', 'type': 'skill'},
            'generated_at': '2026-11-17T00:00:00+00:00',
            'verdict': 'МОЖНО С ОГРАНИЧЕНИЯМИ',
            'coverage': {'total_checks': 9, 'performed': 7},
            'findings': [
                {'id': 'F-1', 'severity': 'HIGH', 'confidence': 'VERIFIED',
                 'file': 'SKILL.md', 'line': 3, 'evidence': 'подозрительный вызов'},
                {'id': 'F-2', 'severity': 'LOW', 'confidence': 'INFERRED', 'file': 'README.md'},
            ],
        }

    def tearDown(self):
        self._tmp.cleanup()

    def test_emit_writes_both_files(self):
        inp = self.base / 'doc.json'
        inp.write_text(json.dumps(self.doc, ensure_ascii=False), encoding='utf-8')
        out = self.base / 'out'
        result = emit.emit(inp, out)
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertEqual(result['count'], 2)
        self.assertTrue((out / 'findings.json').is_file())
        self.assertTrue((out / 'report.sarif').is_file())

    def test_sarif_levels_and_location(self):
        sarif = emit.to_sarif(self.doc)
        results = sarif['runs'][0]['results']
        self.assertEqual(sarif['version'], '2.1.0')
        self.assertEqual(results[0]['level'], 'error')
        self.assertEqual(results[1]['level'], 'note')
        loc = results[0]['locations'][0]['physicalLocation']
        self.assertEqual(loc['artifactLocation']['uri'], 'SKILL.md')
        self.assertEqual(loc['region']['startLine'], 3)
        # находка без line не должна иметь region
        self.assertNotIn('region', results[1]['locations'][0]['physicalLocation'])

    def test_rejects_invalid_severity(self):
        doc = {**self.doc, 'findings': [{'id': 'x', 'severity': 'HUGE', 'confidence': 'VERIFIED', 'file': 'f'}]}
        with self.assertRaises(emit.FindingsError):
            emit.validate_document(doc)

    def test_rejects_missing_target(self):
        doc = {k: v for k, v in self.doc.items() if k != 'target'}
        with self.assertRaises(emit.FindingsError):
            emit.validate_document(doc)

    def test_accepts_empty_findings(self):
        doc = {**self.doc, 'findings': []}
        emit.validate_document(doc)
        self.assertEqual(emit.to_sarif(doc)['runs'][0]['results'], [])


if __name__ == '__main__':
    unittest.main()
