"""Standalone CLI smoke tests against a temporary mock Skill."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills' / 'audit-workflow' / 'scripts' / 'workflow_state.py'

class CliSmoke(unittest.TestCase):
    def run_cli(self, * args, ok = True):
        completed = subprocess.run([sys.executable, str(SCRIPT), * map(str, args)],
                                   text = True, capture_output = True, timeout = 20, check = False)
        self.assertEqual(completed.returncode, 0 if ok else 1, completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def test_end_to_end_preflight_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'sample-skill'
            target.mkdir()
            (target / 'SKILL.md').write_text('---\nname: sample\ndescription: audit fixture\n---\n# Example\n', encoding = 'utf8')
            report = target / 'audit'
            manifest = self.run_cli('init', '--target', target, '--type', 'skill', '--report-dir', report)
            self.assertEqual(self.run_cli('resume', '--report-dir', report)['next_stage'], 'PREFLIGHT')
            payload = root / 'preflight.json'
            data = {
                'schema_version': '1.0', 'run_id': manifest['run_id'], 'stage': 'PREFLIGHT',
                'status': 'COMPLETE', 'method': 'LOCAL_ANALYSIS', 'evidence': ['SKILL.md:1'],
                'output_files': [], 'invocations': [],
                'data': {'host_profile': {'platform': 'other'}}, 'limitations': []
            }
            payload.write_text(json.dumps(data), encoding = 'utf8')
            self.assertEqual(self.run_cli('record', '--report-dir', report, '--payload', payload)['status'], 'RECORDED')
            self.assertEqual(self.run_cli('resume', '--report-dir', report)['next_stage'], 'AUDIT')
            self.assertEqual(self.run_cli('finalize', '--report-dir', report)['status'], 'PARTIAL')

    def test_invalid_result_fails_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'sample'
            target.mkdir()
            (target / 'SKILL.md').write_text('# Example', encoding = 'utf8')
            report = target / 'audit'
            self.run_cli('init', '--target', target, '--type', 'skill', '--report-dir', report)
            payload = root / 'invalid.json'
            payload.write_text('{nope}', encoding = 'utf8')
            result = self.run_cli('record', '--report-dir', report, '--payload', payload, ok = False)
            self.assertEqual(result['status'], 'ERROR')
            self.assertIn('invalid payload JSON', result['message'])

if __name__ == '__main__':
    unittest.main()
