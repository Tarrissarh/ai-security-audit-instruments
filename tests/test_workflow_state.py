"""Offline workflow-state regression tests. Never execute code from audited targets."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from tests.symlink_support import symlink_or_skip

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills' / 'audit-workflow' / 'scripts'))
from workflow_state import (WorkflowError, init, record, resume, finalize,
                            load_manifest, source_fingerprint, schema, validate_schema)

class StageStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / 'tool'
        self.target.mkdir()
        (self.target / 'SKILL.md').write_text('---\nname: example\n---\n# Tool\n', encoding = 'utf8')
        self.report = self.target / 'audit'
        self.manifest = init(self.target, 'skill', self.report)
        self.runid = self.manifest['run_id']
        self.counter = 0

    def payload(self, stage, status = 'COMPLETE', method = 'LOCAL_ANALYSIS', **kw):
        data = {
            'PREFLIGHT': {'host_profile': {'platform': 'other', 'available': []}},
            'AUDIT': {'checked_files': ['SKILL.md'], 'findings': []},
            'IMPROVE': {'proposals': []},
            'MODERNIZE': {'proposals': []},
            'DOCS': {},
            'VALIDATE': {'checks': [{'name': 'links', 'status': 'PASSED'}]},
        }[stage]
        obj = {'schema_version': '1.0', 'run_id': self.runid, 'stage': stage,
               'status': status, 'method': method, 'evidence': ['SKILL.md:1'],
               'output_files': [], 'invocations': [], 'data': data, 'limitations': []}
        obj.update(kw)
        self.counter += 1
        path = self.root / f'payload-{self.counter}.json'
        path.write_text(json.dumps(obj, ensure_ascii = False), encoding = 'utf8')
        return path

    def apply(self, stage, status = 'COMPLETE', **kw):
        return record(self.report, self.payload(stage, status, **kw))

    def prepare_docs(self):
        (self.report / 'docs').mkdir(parents = True, exist_ok = True)
        (self.report / 'README.md').write_text('# Итог\n\n[Подробнее](docs/audit.md)\n', encoding = 'utf8')
        (self.report / 'docs' / 'audit.md').write_text('# Audit\n\nТекст.\n', encoding = 'utf8')
        (self.report / 'docs' / 'workflow-status.md').write_text('# Workflow status\n\nVALIDATE: PENDING at publication\n', encoding = 'utf8')
        return ['README.md', 'docs/audit.md', 'docs/workflow-status.md']

    def first_four(self):
        self.apply('PREFLIGHT')
        self.apply('AUDIT')
        self.apply('IMPROVE')
        self.apply('MODERNIZE')

    def complete_all(self):
        self.first_four()
        paths = self.prepare_docs()
        self.apply('DOCS', output_files = paths)
        self.apply('VALIDATE')

    def test_start_and_resume(self):
        self.assertEqual(resume(self.report)['next_stage'], 'PREFLIGHT')
        self.apply('PREFLIGHT')
        self.assertEqual(resume(self.report)['next_stage'], 'AUDIT')

    def test_completed_workflow(self):
        self.complete_all()
        self.assertEqual(finalize(self.report)['status'], 'COMPLETE')
        self.assertIsNone(resume(self.report)['next_stage'])

    def test_missing_required_stages_cannot_complete(self):
        self.apply('PREFLIGHT')
        self.assertEqual(finalize(self.report)['status'], 'PARTIAL')
        self.assertEqual(resume(self.report)['next_stage'], 'AUDIT')

    def test_skip_optional_allowed(self):
        self.apply('PREFLIGHT')
        self.apply('AUDIT')
        self.apply('IMPROVE', status = 'SKIPPED', method = 'NOT_RUN', data = {'proposals': []})
        self.apply('MODERNIZE', status = 'SKIPPED', method = 'NOT_RUN', data = {'proposals': []})
        self.apply('DOCS', output_files = self.prepare_docs())
        self.apply('VALIDATE')
        self.assertEqual(finalize(self.report)['status'], 'COMPLETE')

    def test_stage_order(self):
        with self.assertRaisesRegex(WorkflowError, 'before'):
            self.apply('AUDIT')

    def test_invalid_json(self):
        p = self.root / 'bad.json'
        p.write_text('{BROKEN', encoding = 'utf8')
        with self.assertRaisesRegex(WorkflowError, 'invalid payload JSON'):
            record(self.report, p)

    def test_schema_rejects_incomplete_contract(self):
        p = self.payload('PREFLIGHT')
        data = json.loads(p.read_text(encoding = 'utf8'))
        data.pop('evidence')
        p.write_text(json.dumps(data), encoding = 'utf8')
        with self.assertRaisesRegex(WorkflowError, 'evidence'):
            record(self.report, p)

    def test_cross_run_payload(self):
        p = self.payload('PREFLIGHT', run_id = 'a' * 32)
        with self.assertRaisesRegex(WorkflowError, 'run_id'):
            record(self.report, p)

    def test_idempotent_record(self):
        p = self.payload('PREFLIGHT')
        self.assertEqual(record(self.report, p)['status'], 'RECORDED')
        self.assertEqual(record(self.report, p)['status'], 'UNCHANGED')
        self.assertEqual(load_manifest(self.report)['stages']['PREFLIGHT']['attempts'], 1)

    def test_conflicting_completed_stage(self):
        self.apply('PREFLIGHT')
        with self.assertRaisesRegex(WorkflowError, 'already resolved'):
            self.apply('PREFLIGHT', evidence = ['new assertion'])

    def test_failed_stage_retries_once(self):
        self.apply('PREFLIGHT', status = 'FAILED', limitations = ['temporary failure'])
        self.assertEqual(resume(self.report)['next_stage'], 'PREFLIGHT')
        self.apply('PREFLIGHT')
        self.assertEqual(load_manifest(self.report)['stages']['PREFLIGHT']['attempts'], 2)
        self.assertEqual(resume(self.report)['next_stage'], 'AUDIT')

    def test_failed_stage_max_attempts(self):
        self.apply('PREFLIGHT', status = 'FAILED')
        self.apply('PREFLIGHT', status = 'FAILED', limitations = ['different failure'])
        with self.assertRaisesRegex(WorkflowError, 'retry limit'):
            self.apply('PREFLIGHT', status = 'COMPLETE')
        self.assertIsNone(resume(self.report)['next_stage'])
        self.assertEqual(finalize(self.report)['status'], 'FAILED')

    def test_input_change_blocks_resume(self):
        self.apply('PREFLIGHT')
        (self.target / 'SKILL.md').write_text('changed source', encoding = 'utf8')
        with self.assertRaisesRegex(WorkflowError, 'STALE_INPUT'):
            resume(self.report)

    def test_report_changes_excluded_from_source_hash(self):
        before = source_fingerprint(self.target, self.report)
        self.prepare_docs()
        self.assertEqual(before, source_fingerprint(self.target, self.report))

    def test_document_paths_escape_rejected(self):
        self.first_four()
        with self.assertRaisesRegex(WorkflowError, 'unsafe output path'):
            self.apply('DOCS', output_files = ['README.md', 'docs/workflow-status.md', '../SKILL.md'])

    def test_document_missing_rejected(self):
        self.first_four()
        with self.assertRaisesRegex(WorkflowError, 'missing or empty'):
            self.apply('DOCS', output_files = ['README.md', 'docs/workflow-status.md'])

    def test_report_broken_link_rejected(self):
        self.first_four()
        files = self.prepare_docs()
        self.apply('DOCS', output_files = files)
        (self.report / 'README.md').write_text('# Title\n[Broken](docs/not-here.md)', encoding = 'utf8')
        with self.assertRaisesRegex(WorkflowError, 'document changed'):
            self.apply('VALIDATE')

    def test_unmodified_broken_link_rejected(self):
        self.first_four()
        files = self.prepare_docs()
        (self.report / 'README.md').write_text('# Title\n[Broken](docs/not-here.md)', encoding = 'utf8')
        self.apply('DOCS', output_files = files)
        with self.assertRaisesRegex(WorkflowError, 'link validation'):
            self.apply('VALIDATE')

    def test_artifact_tamper_refused(self):
        self.apply('PREFLIGHT')
        info = load_manifest(self.report)['stages']['PREFLIGHT']
        path = self.report / 'state' / info['artifact']
        path.write_text(path.read_text('utf8').replace('host_profile', 'host_Xrofile'), encoding = 'utf8')
        with self.assertRaisesRegex(WorkflowError, 'checksum mismatch'):
            self.apply('AUDIT')

    def test_docs_integrity_checked_even_after_complete(self):
        self.complete_all()
        self.assertEqual(finalize(self.report)['status'], 'COMPLETE')
        (self.report / 'README.md').write_text('# Changed\n', encoding = 'utf8')
        with self.assertRaisesRegex(WorkflowError, 'document changed'):
            resume(self.report)

    def test_cannot_skip_required_stage(self):
        with self.assertRaisesRegex(WorkflowError, 'cannot be SKIPPED'):
            self.apply('PREFLIGHT', status = 'SKIPPED', method = 'NOT_RUN')

    def test_generator_never_called(self):
        with self.assertRaisesRegex(WorkflowError, 'ai-tool-generator'):
            self.apply('PREFLIGHT', method = 'SKILL_CALL', invocations = [{'caller': 'audit-workflow', 'callee': 'ai-tool-generator'}])

    def test_recursive_call_forbidden(self):
        with self.assertRaisesRegex(WorkflowError, 'recursive'):
            self.apply('PREFLIGHT', method = 'SKILL_CALL', invocations = [{'caller': 'audit-docs', 'callee': 'audit-workflow'}])

    def test_cycle_rejected(self):
        with self.assertRaisesRegex(WorkflowError, 'cyclic'):
            self.apply('PREFLIGHT', method = 'SKILL_CALL', invocations = [{'caller': 'A', 'callee': 'B'}, {'caller': 'B', 'callee': 'A'}])

    def test_duplicate_call_rejected(self):
        self.apply('PREFLIGHT', method = 'SKILL_CALL', invocations = [{'caller': 'audit-workflow', 'callee': 'audit-skill'}])
        with self.assertRaisesRegex(WorkflowError, 'duplicate programmatic'):
            self.apply('AUDIT', method = 'SKILL_CALL', invocations = [{'caller': 'audit-workflow', 'callee': 'audit-skill'}])

    def test_declared_skill_call_requires_invocation(self):
        with self.assertRaisesRegex(WorkflowError, 'requires documented'):
            self.apply('PREFLIGHT', method = 'SKILL_CALL')

    def test_read_instructions_has_no_invocations(self):
        with self.assertRaisesRegex(WorkflowError, 'must be empty'):
            self.apply('PREFLIGHT', method = 'READ_INSTRUCTIONS', invocations = [{'caller': 'a', 'callee': 'b'}])

    def test_validated_doc_damaged_after_validation_blocks_finalize(self):
        self.complete_all()
        (self.report / 'docs' / 'audit.md').unlink()
        with self.assertRaisesRegex(WorkflowError, 'missing or empty'):
            finalize(self.report)

    def test_staging_is_not_permitted_inside_output_files(self):
        self.first_four()
        with self.assertRaisesRegex(WorkflowError, 'not a report Markdown'):
            self.apply('DOCS', output_files = ['README.md', 'docs/workflow-status.md', 'state/manifest.json'])

    def test_unverifiable_required_validation(self):
        self.first_four()
        self.apply('DOCS', output_files = self.prepare_docs())
        with self.assertRaisesRegex(WorkflowError, 'requires explicit checks'):
            self.apply('VALIDATE', data = {'checks': []})

    def test_symlink_source_refused(self):
        symlink_or_skip(self, self.target / 'link.md', self.target / 'SKILL.md')
        with self.assertRaisesRegex(WorkflowError, 'symlink'):
            resume(self.report)

    def test_payload_is_not_saved_when_validation_fails(self):
        with self.assertRaises(WorkflowError):
            self.apply('PREFLIGHT', method = 'SKILL_CALL')
        self.assertEqual(load_manifest(self.report)['stages']['PREFLIGHT']['attempts'], 0)

    def test_manifest_schema(self):
        validate_schema(load_manifest(self.report), 'manifest')

if __name__ == '__main__':
    unittest.main()
