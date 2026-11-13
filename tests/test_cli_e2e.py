"""Offline-only regression tests for real-client runner.
All client subprocesses are mocked. Never tests real LLM skill discovery.
"""
from pathlib import Path
import importlib.util
import json
import os
from unittest.mock import patch
import tempfile
import subprocess
import unittest
from tests.symlink_support import symlink_or_skip

ROOT = Path(__file__).resolve().parents[1]
modpath = ROOT / 'integration/runtime/cli_e2e.py'
spec = importlib.util.spec_from_file_location('cli_e2e', modpath)
import sys
sys.path.insert(0, str(modpath.parent))
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
import real_client

class TestExplicitClientRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def prepare(self, platform = 'codex', fixture = 'skill-clean'):
        real_client.prepare(platform, self.path, fixture)

    def test_commands_have_explicit_read_only_modes(self):
        for platform in cli.BINARY_NAMES:
            argv = cli.command_for(platform)
            self.assertEqual(argv[ - 1], cli.PROMPT)
            self.assertFalse(any(x in argv for x in ['--full-auto', '--force', '--dangerously-skip-permissions', '--auto']))
        self.assertIn('read-only', cli.command_for('codex'))
        self.assertIn('plan', cli.command_for('claude-code'))
        self.assertEqual(cli.command_for('deepseek-harness')[: 3], ['dsh', '--profile', 'headless'])
        self.assertIn('--mode=ask', cli.command_for('cursor'))
        self.assertEqual(cli.command_for('opencode')[4], 'plan')

    def test_missing_binary_does_not_execute(self):
        self.prepare()
        with patch.object(cli.shutil, 'which', return_value = None), patch.object(cli.subprocess, 'run') as sub:
            r = cli.run(self.path, execute = True, consent = True)
        self.assertEqual(r['status'], 'BLOCKED_CLI_NOT_FOUND')
        self.assertFalse(r['client_executed'])
        sub.assert_not_called()

    def test_plan_never_executes_and_marks_not_tested(self):
        self.prepare('cursor')
        with patch.object(cli.subprocess, 'run') as sub, patch.object(cli.shutil, 'which', return_value = None):
            p = cli.plan(self.path)
        sub.assert_not_called()
        self.assertEqual(p['status'], 'BLOCKED_CLI_NOT_FOUND')
        self.assertEqual(p['client_skill_discovery'], 'NOT_TESTED')

    def test_consent_required(self):
        self.prepare()
        with patch.object(cli.subprocess, 'run') as sub:
            with self.assertRaisesRegex(ValueError, 'BOTH'):
                cli.run(self.path, execute = True, consent = False)
            sub.assert_not_called()

    def test_implicit_run_is_plan(self):
        self.prepare()
        with patch.object(cli.shutil, 'which', return_value = None), patch.object(cli.subprocess, 'run') as sub:
            result = cli.run(self.path)
        self.assertEqual(result['status'], 'BLOCKED_CLI_NOT_FOUND')
        sub.assert_not_called()

    def test_modified_source_blocks_launch(self):
        self.prepare()
        (self.path / 'subject/SKILL.md').write_text('corrupted', encoding = 'utf-8')
        with patch.object(cli.subprocess, 'run') as sub:
            with self.assertRaisesRegex(ValueError, 'fixture was changed'):
                cli.run(self.path, execute = True, consent = True)
            sub.assert_not_called()

    def test_client_binary_restrictions(self):
        self.assertNotIn('cursor', cli.BINARY_NAMES['cursor'])
        self.assertNotIn('cursor', real_client.CLIENT_BINS['cursor'])
        self.assertEqual(set(cli.BINARY_NAMES), set(real_client.PLATFORMS))

    def test_opencode_denies_risky_tools(self):
        self.prepare('opencode')
        result = cli._read_only_opencode_config(self.path)
        blocked = {x['resource'] for x in result['policies']}
        for item in ('shell:*', 'edit:*', 'external_directory:*', 'webfetch:*', 'websearch:*', 'execute:*'):
            self.assertIn(item, blocked)
        (self.path / 'opencode.json').write_text('already exists', encoding = 'utf-8')
        with self.assertRaisesRegex(ValueError, 'existing'):
            cli._read_only_opencode_config(self.path)

    def test_isolated_environment_does_not_inherit_random_secrets(self):
        self.prepare()
        with patch.dict(os.environ, {'UNRELATED_PASSWORD': 'private value'}, clear = False):
            env = cli._isolated_env(self.path)
        self.assertNotIn('UNRELATED_PASSWORD', env)
        self.assertEqual(Path(env['HOME']), self.path / '.integration-test/client-home')

    def test_api_key_redacted(self):
        env = {'OPENAI_API_KEY': 'sk-FICTIONALabcdefghijklmno'}
        redacted = cli._redact(b'API key sk-FICTIONALabcdefghijklmno', env)
        self.assertNotIn('abcdefghijklmno', redacted)

    def test_mocked_success_does_not_certify_client(self):
        self.prepare('claude-code')
        fake = subprocess.CompletedProcess(['claude'], 0, stdout = b'{"status":"success"}', stderr = b'')
        with patch.object(cli.shutil, 'which', return_value = '/fake/claude'), patch.object(cli.subprocess, 'run', return_value = fake) as sub:
            r = cli.run(self.path, execute = True, consent = True)
        self.assertEqual(r['process_status'], 'EXIT_ZERO')
        self.assertFalse(r['client_pass_certified'])
        self.assertEqual(r['client_skill_activation'], 'REVIEW_REQUIRED')
        self.assertTrue(r['source_unchanged'])
        self.assertEqual(sub.call_args.kwargs['cwd'], self.path.resolve())
        self.assertFalse(sub.call_args.kwargs.get('shell', False))
        self.assertTrue((self.path / r['stdout_file']).is_file())

    def test_nonzero_execution_is_not_skill_test(self):
        self.prepare('codex')
        fake = subprocess.CompletedProcess(['codex'], 1, stdout = b'', stderr = b'auth failed')
        with patch.object(cli.shutil, 'which', return_value = '/fake/codex'), patch.object(cli.subprocess, 'run', return_value = fake):
            r = cli.run(self.path, execute = True, consent = True)
        self.assertEqual(r['process_status'], 'NONZERO_EXIT')
        self.assertEqual(r['client_skill_activation'], 'NOT_TESTED')

    def test_timeout_recorded_without_certification(self):
        self.prepare('claude-code')
        with patch.object(cli.shutil, 'which', return_value = '/fake/claude'), patch.object(cli.subprocess, 'run', side_effect = subprocess.TimeoutExpired(cmd = 'claude', timeout = 60)):
            r = cli.run(self.path, execute = True, consent = True)
        self.assertEqual(r['process_status'], 'TIMEOUT')
        self.assertFalse(r['client_pass_certified'])

    def test_out_of_range_timeout(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'timeout'):
            cli.run(self.path, execute = True, consent = True, timeout = 0)

    def test_log_writer_never_overwrites(self):
        path = self.path / 'file.txt'
        cli._write_private(path, 'one')
        with self.assertRaisesRegex(ValueError, 'overwriting'):
            cli._write_private(path, 'two')
        self.assertEqual(path.read_text(), 'one')

    def test_detect_symlink_fixture(self):
        self.prepare()
        other = self.path / 'other'
        other.write_text('outside')
        symlink_or_skip(self, self.path / 'subject/unsafe-link', other)
        with self.assertRaises(ValueError):
            cli.plan(self.path)

    def test_executed_opencode_writes_restricted_config_only(self):
        self.prepare('opencode')
        fake = subprocess.CompletedProcess(['opencode'], 0, stdout = b'{}', stderr = b'')
        with patch.object(cli.shutil, 'which', return_value = '/fake/opencode'), patch.object(cli.subprocess, 'run', return_value = fake):
            r = cli.run(self.path, execute = True, consent = True)
        self.assertTrue((self.path / 'opencode.json').is_file())
        self.assertTrue(r['source_unchanged'])
        with patch.object(cli.shutil, 'which', return_value = '/fake/opencode'), patch.object(cli.subprocess, 'run', return_value = fake):
            second = cli.run(self.path, execute = True, consent = True)
        self.assertEqual(second['process_status'], 'EXIT_ZERO')

if __name__ == '__main__':
    unittest.main()

class TestEvidenceCheck(unittest.TestCase):
    def test_no_run_remains_not_tested(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real_client.prepare('codex', p, 'skill-clean')
            self.assertEqual(cli.verify(p)['status'], 'NOT_TESTED')

    def test_mock_run_logs_verified_but_not_certified(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real_client.prepare('codex', p, 'skill-clean')
            fake = subprocess.CompletedProcess(['codex'], 0, stdout = b'{"text":"a"}', stderr = b'')
            with patch.object(cli.shutil, 'which', return_value = '/fake/codex'), patch.object(cli.subprocess, 'run', return_value = fake):
                cli.run(p, execute = True, consent = True)
            result = cli.verify(p)
            self.assertEqual(result['status'], 'LOCAL_LOGS_VERIFIED_CLIENT_REVIEW_REQUIRED')
            self.assertFalse(result['client_pass_certified'])

    def test_tampered_log_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real_client.prepare('codex', p, 'skill-clean')
            fake = subprocess.CompletedProcess(['codex'], 0, stdout = b'{"text":"a"}', stderr = b'')
            with patch.object(cli.shutil, 'which', return_value = '/fake/codex'), patch.object(cli.subprocess, 'run', return_value = fake):
                record = cli.run(p, execute = True, consent = True)
            (p / record['stdout_file']).write_text('tampered', encoding = 'utf-8')
            result = cli.verify(p)
            self.assertEqual(result['status'], 'FAILED_LOG_INTEGRITY')
            self.assertTrue(any('LOG_CHANGED' in x for x in result['issues']))

    def test_unsafe_log_path_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            real_client.prepare('codex', p, 'skill-clean')
            out = p / '.integration-test/client-runs'
            out.mkdir()
            r = {'platform': 'codex', 'client_pass_certified': False, 'stdout_file': '../../etc/passwd', 'stderr_file': '../../etc/passwd'}
            (out / 'fake.json').write_text(json.dumps(r), encoding = 'utf-8')
            result = cli.verify(p)
            self.assertEqual(result['status'], 'FAILED_LOG_INTEGRITY')
            self.assertTrue(any('INVALID_PATH' in x for x in result['issues']))
