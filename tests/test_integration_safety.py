"""regressions for client launcher and evidence verification.

All tests are mocked or local-only: NO actual AI client/model is invoked.
"""
from pathlib import Path
import importlib.util
import json
import sys
import subprocess
import tempfile
import unittest
from tests.symlink_support import symlink_or_skip
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integration' / 'runtime'))
import cli_e2e as cli
import real_client

class TestIntegrationSafety(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
    def tearDown(self):
        self.t.cleanup()

    def test_deepseek_documented_headless_command_has_no_invented_flags(self):
        self.assertEqual(cli.command_for('deepseek-harness')[: 3], ['dsh', '--profile', 'headless'])
        argv = cli.command_for('deepseek-harness')
        for fake in ('--permission-mode', '--approval-policy', '--json', 'read-only'):
            self.assertNotIn(fake, argv)

    def test_deepseek_launch_blocked_without_verified_read_only_policy(self):
        real_client.prepare('deepseek-harness', self.root, 'skill-clean')
        with patch.object(cli.shutil, 'which', return_value = '/bin/dsh'), patch.object(cli.subprocess, 'run') as execution:
            self.assertEqual(cli.plan(self.root)['status'], 'BLOCKED_READ_ONLY_UNVERIFIED')
            result = cli.run(self.root, execute = True, consent = True)
        self.assertEqual(result['status'], 'BLOCKED_READ_ONLY_UNVERIFIED')
        self.assertFalse(result['client_executed'])
        execution.assert_not_called()

    def test_symlink_inside_audit_folder_is_rejected(self):
        real_client.prepare('codex', self.root, 'skill-clean')
        target = self.root / 'elsewhere'
        target.mkdir()
        audit = self.root / 'subject/audit'
        audit.mkdir()
        symlink_or_skip(self, audit / 'leak', target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink forbidden'):
            cli.plan(self.root)

    def test_symlink_audit_root_is_rejected(self):
        real_client.prepare('codex', self.root, 'skill-clean')
        outside = self.root / 'elsewhere'
        outside.mkdir()
        symlink_or_skip(self, self.root / 'subject/audit', outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink forbidden'):
            real_client.assess(self.root)

    def test_normal_report_directory_remains_ignored(self):
        real_client.prepare('codex', self.root, 'skill-clean')
        audit = self.root / 'subject/audit'
        audit.mkdir()
        (audit / 'README.md').write_text('# report', encoding = 'utf-8')
        self.assertTrue(cli.plan(self.root)['source_unchanged'])

    def test_helpful_but_unverified_mock_execution_does_not_certify(self):
        real_client.prepare('codex', self.root, 'skill-issues')
        mock_response = subprocess.CompletedProcess(['codex'], 0, stdout = b'{"skill_name":"audit-workflow"}', stderr = b'')
        with patch.object(cli.shutil, 'which', return_value = '/mock/codex'), patch.object(cli.subprocess, 'run', return_value = mock_response):
            result = cli.run(self.root, execute = True, consent = True)
        self.assertFalse(result['client_pass_certified'])
        self.assertEqual(result['client_skill_activation'], 'REVIEW_REQUIRED')
        self.assertEqual(cli.verify(self.root)['status'], 'LOCAL_LOGS_VERIFIED_CLIENT_REVIEW_REQUIRED')

    def test_large_logs_flagged_for_truncation(self):
        real_client.prepare('codex', self.root, 'skill-clean')
        mock_response = subprocess.CompletedProcess(['codex'], 0, stdout = b'a' * (cli.MAX_STDIO + 1), stderr = b'')
        with patch.object(cli.shutil, 'which', return_value = '/mock/codex'), patch.object(cli.subprocess, 'run', return_value = mock_response):
            result = cli.run(self.root, execute = True, consent = True)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['stdout_raw_bytes'], cli.MAX_STDIO + 1)
        self.assertLessEqual((self.root / result['stdout_file']).stat().st_size, cli.MAX_STDIO)

    def test_binary_not_present_keeps_not_tested(self):
        real_client.prepare('cursor', self.root, 'skill-clean')
        with patch.object(cli.shutil, 'which', return_value = None), patch.object(cli.subprocess, 'run') as execution:
            result = cli.run(self.root, execute = True, consent = True)
        self.assertEqual(result['status'], 'BLOCKED_CLI_NOT_FOUND')
        self.assertFalse(result['client_executed'])
        execution.assert_not_called()

if __name__ == '__main__':
    unittest.main()
