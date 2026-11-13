"""evidence preparation and provenance tests: never execute a model client."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('real_client', ROOT / 'integration/runtime/real_client.py')
real = importlib.util.module_from_spec(spec)
spec.loader.exec_module(real)

class TestRuntimeEvidence(unittest.TestCase):
    def test_probe_never_calls_clients(self):
        with patch.object(real.shutil, 'which', return_value = None) as which:
            r = real.probe()
        self.assertEqual(r['client_commands_executed'], 0)
        self.assertEqual(set(r['clients']), set(real.CLIENT_BINS))
        self.assertTrue(which.called)
        self.assertTrue(all(v['actual_skill_execution'] == 'NOT_TESTED' for v in r['clients'].values()))

    def test_prepare_all_five_and_assess_without_claim(self):
        for platform in real.PLATFORMS:
            with self.subTest(platform = platform), tempfile.TemporaryDirectory() as d:
                p = Path(d)
                prepared = real.prepare(platform, p, 'skill-clean')
                self.assertEqual(prepared['status'], 'READY_FOR_MANUAL_CLIENT_TEST')
                self.assertEqual(prepared['installed_skill_count'], 11)
                self.assertFalse(prepared['client_executed'])
                r = real.assess(p)
                self.assertTrue(r['source_unchanged'])
                self.assertFalse(r['client_pass_certified'])
                self.assertFalse(r['issues'])
                self.assertEqual(r['checks']['discovery']['operator_assertion'], 'NOT_TESTED')

    def test_prepare_requires_empty_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / 'keep.txt').write_text('DO NOT DELETE')
            with self.assertRaisesRegex(ValueError, 'empty'):
                real.prepare('codex', p, 'skill-clean')
            self.assertEqual((p / 'keep.txt').read_text(), 'DO NOT DELETE')

    def test_prepare_symlink_workspace_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            link = p / 'link'
            link.symlink_to(p, target_is_directory = True)
            with self.assertRaisesRegex(ValueError, 'regular'):
                real.prepare('opencode', link, 'skill-clean')

    def test_modified_subject_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real.prepare('claude-code', p, 'skill-clean')
            (p / 'subject/SKILL.md').write_text('modified')
            r = real.assess(p)
            self.assertFalse(r['source_unchanged'])
            self.assertEqual(r['status'], 'FAILED_VALIDATION')
            self.assertTrue(any('AUDITED_SOURCE_CHANGED' in x for x in r['issues']))

    def test_fake_pass_without_log_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real.prepare('codex', p, 'skill-clean')
            f = p / '.integration-test/evidence.json'
            data = json.loads(f.read_text())
            data['checks']['discovery']['status'] = 'PASS'
            f.write_text(json.dumps(data))
            r = real.assess(p)
            self.assertEqual(r['status'], 'FAILED_VALIDATION')
            self.assertTrue(any('UNSUPPORTED_PASS: discovery' in x for x in r['issues']))

    def test_attested_pass_still_requires_independent_review(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real.prepare('opencode', p, 'skill-clean')
            evidence = p / '.integration-test/evidence.json'
            data = json.loads(evidence.read_text())
            (p / '.integration-test/session.log').write_text('synthetic test log', encoding = 'utf-8')
            data['checks']['discovery'].update(status = 'PASS', evidence_files = ['.integration-test/session.log'])
            evidence.write_text(json.dumps(data))
            r = real.assess(p)
            self.assertEqual(r['status'], 'EVIDENCE_REVIEW_REQUIRED')
            self.assertEqual(r['checks']['discovery']['independent_client_verification'], 'REVIEW_REQUIRED')
            self.assertFalse(r['client_pass_certified'])

    def test_evidence_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real.prepare('cursor', p, 'skill-clean')
            f = p / '.integration-test/evidence.json'
            data = json.loads(f.read_text())
            data['checks']['discovery'].update(status = 'PASS', evidence_files = ['../escape.log'])
            f.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'escapes'):
                real.assess(p)

    def test_evidence_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            p = Path(d)
            real.prepare('codex', p, 'skill-clean')
            z = Path(outside) / 'log.txt'
            z.write_text('outside')
            (p / '.integration-test/link.log').symlink_to(z)
            f = p / '.integration-test/evidence.json'
            data = json.loads(f.read_text())
            data['checks']['discovery'].update(status = 'PASS', evidence_files = ['.integration-test/link.log'])
            f.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'symlink'):
                real.assess(p)

    def test_report_assertion_requires_actual_readme(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real.prepare('deepseek-harness', p, 'skill-clean')
            (p / '.integration-test/session.log').write_text('observed, but no report')
            f = p / '.integration-test/evidence.json'
            data = json.loads(f.read_text())
            data['checks']['reports'].update(status = 'PASS', evidence_files = ['.integration-test/session.log'])
            f.write_text(json.dumps(data))
            r = real.assess(p)
            self.assertTrue(any('no audit/README.md' in s for s in r['issues']))

    def test_invalid_check_status_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real.prepare('codex', p, 'skill-clean')
            f = p / '.integration-test/evidence.json'
            data = json.loads(f.read_text())
            data['checks']['quality']['status'] = 'SHOULD_PASS'
            f.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'unknown status'):
                real.assess(p)

if __name__ == '__main__':
    unittest.main()

class TestReportIsolation(unittest.TestCase):
    def test_report_created_under_subject_does_not_count_as_source_modification(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real.prepare('codex', p, 'skill-clean')
            out = p / 'subject/audit'
            out.mkdir()
            (out / 'README.md').write_text('# Audit\n', encoding = 'utf-8')
            r = real.assess(p)
            self.assertTrue(r['source_unchanged'])
            self.assertEqual(r['status'], 'NOT_TESTED')

    def test_extra_non_audit_file_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real.prepare('codex', p, 'skill-clean')
            (p / 'subject/unknown.txt').write_text('unexpected')
            r = real.assess(p)
            self.assertEqual(r['status'], 'FAILED_VALIDATION')

    def test_assess_follows_no_symlink_to_state_files(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            p = Path(d)
            real.prepare('codex', p, 'skill-clean')
            manifest = p / '.integration-test/baseline.json'
            manifest.unlink()
            manifest.symlink_to(Path(outside) / 'file.json')
            with self.assertRaisesRegex(ValueError, 'symbolic link'):
                real.assess(p)

class TestReportSymlinks(unittest.TestCase):
    def test_report_symlink_cannot_justify_pass(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            p = Path(d)
            real.prepare('codex', p, 'skill-clean')
            (Path(outside) / 'README.md').write_text('# Wrong report')
            (p / 'audit').symlink_to(outside, target_is_directory = True)
            (p / '.integration-test/log.txt').write_text('placeholder')
            f = p / '.integration-test/evidence.json'
            data = json.loads(f.read_text())
            data['checks']['reports'].update(status = 'PASS', evidence_files = ['.integration-test/log.txt'])
            f.write_text(json.dumps(data))
            result = real.assess(p)
            self.assertEqual(result['status'], 'FAILED_VALIDATION')
