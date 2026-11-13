"""offline evidence aggregation; fake client runs use mock subprocess only."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.symlink_support import symlink_or_skip
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integration' / 'runtime'))
import real_client
import cli_e2e
import compatibility_report as review

class TestEvidenceReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        real_client.prepare('codex', self.workspace, 'skill-clean')

    def tearDown(self):
        self.tmp.cleanup()

    def _fake_run(self):
        fake = subprocess.CompletedProcess(['codex'], 0, stdout = b'{"observations":[]}', stderr = b'')
        with patch.object(cli_e2e.shutil, 'which', return_value = '/fake/codex'), \
             patch.object(cli_e2e.subprocess, 'run', return_value = fake):
            return cli_e2e.run(self.workspace, execute = True, consent = True)

    def test_no_logs_no_assertions_stays_not_tested(self):
        result = review.create_report([self.workspace], include_probe = False)
        self.assertEqual(result['overall_status'], 'NOT_TESTED')
        self.assertEqual(result['client_matrix']['codex']['supplied_workspaces'], 1)
        self.assertEqual(result['client_matrix']['cursor']['supplied_workspaces'], 0)
        self.assertFalse(result['client_pass_certified'])

    def test_empty_workspaces_never_certifies(self):
        r = review.create_report([], include_probe = False)
        self.assertEqual(r['overall_status'], 'NOT_TESTED')
        self.assertEqual(len(r['client_matrix']), 5)
        self.assertTrue(all(v['actual_client_e2e'] == 'NOT_TESTED' for v in r['client_matrix'].values()))

    def test_operator_pass_with_log_never_becomes_client_pass(self):
        run = self._fake_run()
        assert cli_e2e.verify(self.workspace)['status'] == 'LOCAL_LOGS_VERIFIED_CLIENT_REVIEW_REQUIRED'
        file = self.workspace / '.integration-test/evidence.json'
        evidence = json.loads(file.read_text())
        evidence['checks']['activation'] = {
            'status': 'PASS', 'notes': 'human claims success',
            'evidence_files': [run['stdout_file']],
        }
        file.write_text(json.dumps(evidence), encoding = 'utf-8')
        result = review.create_report([self.workspace], include_probe = False)
        self.assertEqual(result['overall_status'], 'REVIEW_REQUIRED')
        self.assertEqual(result['workspaces'][0]['checks']['activation']['independent_status'], 'REVIEW_REQUIRED')
        self.assertEqual(result['client_matrix']['codex']['actual_client_e2e'], 'NOT_TESTED')
        self.assertFalse(result['client_pass_certified'])

    def test_missing_log_invalid_evidence(self):
        file = self.workspace / '.integration-test/evidence.json'
        evidence = json.loads(file.read_text())
        evidence['checks']['reports'] = {
            'status': 'PASS', 'notes': 'not real',
            'evidence_files': ['.integration-test/nonexistent.log'],
        }
        file.write_text(json.dumps(evidence), encoding = 'utf-8')
        result = review.create_report([self.workspace], include_probe = False)
        self.assertEqual(result['overall_status'], 'INVALID_EVIDENCE')
        self.assertFalse(result['client_pass_certified'])

    def test_modified_subject_invalid(self):
        (self.workspace / 'subject/SKILL.md').write_text('# modified', encoding = 'utf-8')
        result = review.create_report([self.workspace], include_probe = False)
        self.assertEqual(result['overall_status'], 'INVALID_EVIDENCE')
        self.assertFalse(result['client_pass_certified'])

    def test_invalid_workspace_safe_failure(self):
        result = review.evaluate_workspace(self.workspace / 'no-such-workspace')
        self.assertEqual(result['integration_status'], 'INVALID_EVIDENCE')
        self.assertFalse(result['client_pass_certified'])

    def test_mismatching_run_name_is_detected(self):
        run = self._fake_run()
        p = self.workspace / '.integration-test/client-runs' / f"{run['run_id']}.json"
        p.rename(p.with_name('f' * 32 + '.json'))
        checked = cli_e2e.verify(self.workspace)
        self.assertEqual(checked['status'], 'FAILED_LOG_INTEGRITY')
        self.assertTrue(any('INVALID_RUN_ID' in x for x in checked['issues']))

    def test_forged_record_metadata_is_detected(self):
        run = self._fake_run()
        p = self.workspace / '.integration-test/client-runs' / f"{run['run_id']}.json"
        data = json.loads(p.read_text())
        data['execution_attempted'] = False
        data['started_at'] = 'not-a-date'
        p.write_text(json.dumps(data))
        checked = cli_e2e.verify(self.workspace)
        self.assertEqual(checked['status'], 'FAILED_LOG_INTEGRITY')
        self.assertTrue(any('INVALID_TIMESTAMP' in x for x in checked['issues']))
        self.assertTrue(any('UNTRUSTED_RECORD_FIELDS' in x for x in checked['issues']))

    def test_wrong_log_reference_from_valid_run_is_detected(self):
        run = self._fake_run()
        p = self.workspace / '.integration-test/client-runs' / f"{run['run_id']}.json"
        data = json.loads(p.read_text())
        data['stdout_file'] = '.integration-test/client-runs/something-else.stdout.txt'
        p.write_text(json.dumps(data))
        checked = cli_e2e.verify(self.workspace)
        self.assertTrue(any('INVALID_PATH' in x for x in checked['issues']))

    def test_symlinked_evidence_invalid(self):
        run = self._fake_run()
        evidence = json.loads((self.workspace / '.integration-test/evidence.json').read_text())
        linked = self.workspace / '.integration-test/link.log'
        symlink_or_skip(self, linked, self.workspace / run['stdout_file'])
        evidence['checks']['discovery'].update(status = 'PASS', evidence_files = ['.integration-test/link.log'])
        (self.workspace / '.integration-test/evidence.json').write_text(json.dumps(evidence))
        result = review.create_report([self.workspace], include_probe = False)
        self.assertEqual(result['overall_status'], 'INVALID_EVIDENCE')

if __name__ == '__main__':
    unittest.main()
