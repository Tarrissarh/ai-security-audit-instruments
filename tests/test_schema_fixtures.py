"""Валидация JSON-схем и example-фикстур (защита от дрейфа схем).

Требует jsonschema.
"""
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMAS = REPO / 'skills' / 'audit-workflow' / 'schemas'

try:
    from jsonschema import Draft202012Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


@unittest.skipUnless(HAS_JSONSCHEMA, 'требуется jsonschema')
class SchemaFixtureTest(unittest.TestCase):
    def _load(self, rel):
        return json.loads((REPO / rel).read_text(encoding='utf-8'))

    def _validator(self, schema_path):
        return Draft202012Validator(self._load(schema_path))

    def test_audit_example_validates(self):
        validator = self._validator('skills/audit-workflow/schemas/stage-result.schema.json')
        example = self._load('skills/audit-workflow/examples/AUDIT.example.json')
        self.assertEqual(list(validator.iter_errors(example)), [])

    def test_manifest_schema_includes_rules_type(self):
        manifest = self._load('skills/audit-workflow/schemas/manifest.schema.json')
        enum = manifest['properties']['target']['properties']['type']['enum']
        self.assertIn('rules', enum)

    def test_findings_schema_accepts_minimal(self):
        validator = self._validator('skills/audit-workflow/schemas/findings.schema.json')
        doc = {
            'schema_version': '1.0',
            'target': {'path': '/x', 'type': 'skill'},
            'generated_at': '2026-11-17T00:00:00Z',
            'verdict': 'НЕДОСТАТОЧНО ДАННЫХ',
            'findings': [],
        }
        self.assertEqual(list(validator.iter_errors(doc)), [])

    def test_findings_schema_rejects_bad_severity(self):
        validator = self._validator('skills/audit-workflow/schemas/findings.schema.json')
        doc = {
            'schema_version': '1.0',
            'target': {'path': '/x', 'type': 'skill'},
            'generated_at': '2026-11-17T00:00:00Z',
            'verdict': 'X',
            'findings': [{'id': 'f', 'severity': 'HUGE', 'confidence': 'VERIFIED', 'file': 'x'}],
        }
        self.assertTrue(list(validator.iter_errors(doc)))

    def test_all_schemas_parse(self):
        for name in ('stage-result.schema.json', 'manifest.schema.json', 'findings.schema.json'):
            schema = self._load(f'skills/audit-workflow/schemas/{name}')
            self.assertIsInstance(schema, dict)
            self.assertIn('type', schema)


if __name__ == '__main__':
    unittest.main()
