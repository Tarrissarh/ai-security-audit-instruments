"""fixture-only tests; fake outputs are never labeled real client runs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integration/runtime'))
import real_client  # noqa
import quality_bridge  # noqa
import evidence_export  # noqa

class EvidenceQualityFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.created = []

    def prep(self, case = 'skill-clean', platform = 'codex', prediction = None):
        folder = self.parent / f'sandbox-{len(self.created)}'
        folder.mkdir()
        real_client.prepare(platform, folder, case)
        if prediction is not None:
            (folder / '.integration-test/predictions.json').write_text(
                json.dumps(prediction, ensure_ascii = False), encoding = 'utf-8')
        self.created.append(folder)
        return folder

    def prediction(self, cid):
        return {'case_id': cid, 'findings': [], 'recommendations': []}

    def test_prediction_missing_returns_invalid_not_zero(self):
        r = quality_bridge.report([self.prep()])
        self.assertEqual(r['status'], 'INVALID_INPUT')
        self.assertFalse(r['client_pass_certified'])

    def test_single_prediction_is_incomplete(self):
        p = self.prep(prediction = self.prediction('skill-clean'))
        r = quality_bridge.report([p])
        self.assertEqual(r['status'], 'INCOMPLETE')
        self.assertIn('skill-issues', r['missing_cases'])
        self.assertIsNone(r['quality_metrics'])
        self.assertFalse(r['actual_client_execution_confirmed'])

    def test_mismatched_case_rejected(self):
        p = self.prep(prediction = self.prediction('skill-issues'))
        r = quality_bridge.report([p])
        self.assertEqual(r['status'], 'INVALID_INPUT')

    def test_duplicate_case_rejected(self):
        p1 = self.prep(prediction = self.prediction('skill-clean'))
        p2 = self.prep(prediction = self.prediction('skill-clean'))
        r = quality_bridge.report([p1, p2])
        self.assertEqual(r['status'], 'INVALID_INPUT')

    def test_changed_source_rejected(self):
        p = self.prep(prediction = self.prediction('skill-clean'))
        (p / 'subject/SKILL.md').write_text('tampered', encoding = 'utf-8')
        r = quality_bridge.report([p])
        self.assertEqual(r['status'], 'INVALID_INPUT')

    def test_symlinked_prediction_rejected(self):
        p = self.prep()
        external = self.parent / 'outside.json'
        external.write_text(json.dumps(self.prediction('skill-clean')))
        try:
            (p / '.integration-test/predictions.json').symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks unsupported')
        r = quality_bridge.report([p])
        self.assertEqual(r['status'], 'INVALID_INPUT')

    def test_all_twelve_synthetic_scores_but_not_client_pass(self):
        # Идеальные ответы искусственные: этот тест проверяет метрики оценщика, а не качество модели.
        perfect = json.loads((ROOT / 'quality/examples/predictions-perfect.json').read_text('utf-8'))
        paths = []
        for case in perfect['cases']:
            paths.append(self.prep(case['case_id'], prediction = case))
        result = quality_bridge.report(paths, score = True)
        self.assertEqual(result['status'], 'SCORED_UNVERIFIED_CLIENT_OUTPUT')
        self.assertEqual(result['quality_metrics']['metrics']['f1'], 1)
        self.assertFalse(result['client_pass_certified'])

    def test_export_summary_only_no_private_workspace_path(self):
        p = self.prep()
        z = self.parent / 'export.zip'
        result = evidence_export.export([p], z)
        self.assertEqual(result['status'], 'EXPORTED_UNVERIFIED_EVIDENCE')
        with ZipFile(z) as f:
            self.assertEqual(sorted(f.namelist()), ['README.txt', 'SUMMARY.json'])
            s = f.read('SUMMARY.json').decode()
            self.assertNotIn(str(self.parent), s)
            self.assertFalse(json.loads(s)['client_pass_certified'])

    def test_export_does_not_overwrite(self):
        p = self.prep()
        z = self.parent / 'export.zip'
        evidence_export.export([p], z)
        with self.assertRaises(ValueError):
            evidence_export.export([p], z)

    def test_logs_require_separate_privacy_acknowledgement(self):
        p = self.prep()
        with self.assertRaises(ValueError):
            evidence_export.export([p], self.parent / 'evidence.zip', include_logs = True)

    def test_untracked_logs_not_exported(self):
        p = self.prep()
        d = p / '.integration-test/client-runs'
        d.mkdir(parents = True)
        (d / 'untracked.stdout.txt').write_text('PRIVATE TEST TEXT')
        z = self.parent / 'evidence.zip'
        evidence_export.export([p], z, include_logs = True, privacy_reviewed = True)
        with ZipFile(z) as f:
            self.assertEqual(sorted(f.namelist()), ['README.txt', 'SUMMARY.json'])

if __name__ == '__main__':
    unittest.main()
