"""Юнит-тесты для локального менеджера состояния audit-workflow.

Запуск (из корня репозитория):
    python -m unittest discover -s tests -v

Требует jsonschema; тесты, которым нужен markdown-it-py (валидация отчёта через
verify_report), автоматически пропускаются, если эта библиотека не установлена.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WF_PATH = REPO / 'skills' / 'audit-workflow' / 'scripts' / 'workflow_state.py'

try:
    import markdown_it  # noqa: F401
    HAS_MARKDOWN_IT = True
except ImportError:
    HAS_MARKDOWN_IT = False


def _load_module():
    spec = importlib.util.spec_from_file_location('workflow_state', WF_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wf = _load_module()
WorkflowError = wf.WorkflowError


class WorkflowStateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.target = self.base / 'target'
        self.target.mkdir()
        (self.target / 'SKILL.md').write_text('# test target\n', encoding='utf-8')
        self.report = self.target / 'audit'

    def tearDown(self):
        self._tmp.cleanup()

    # --- вспомогательные -------------------------------------------------

    def _record(self, run_id, stage, *, status='COMPLETE', method='LOCAL_ANALYSIS',
                output_files=None, invocations=None, data=None, evidence=None):
        obj = {
            'schema_version': '1.0',
            'run_id': run_id,
            'stage': stage,
            'status': status,
            'method': method,
            'evidence': evidence if evidence is not None else ['evidence'],
            'output_files': output_files or [],
            'invocations': invocations or [],
            'data': data or {},
            'limitations': [],
        }
        payload = self.base / f'{stage}.json'
        payload.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        return wf.record(self.report, payload)

    def _manifest(self):
        return json.loads((self.report / 'state' / 'manifest.json').read_text(encoding='utf-8'))

    # --- init ------------------------------------------------------------

    def test_init_creates_running_manifest(self):
        manifest = wf.init(self.target, 'skill', self.report)
        self.assertEqual(manifest['state'], 'RUNNING')
        self.assertEqual(manifest['target']['type'], 'skill')
        self.assertEqual(len(manifest['target']['sha256']), 64)
        self.assertEqual(self._manifest()['run_id'], manifest['run_id'])

    def test_init_accepts_rules_type(self):
        manifest = wf.init(self.target, 'rules', self.report)
        self.assertEqual(manifest['target']['type'], 'rules')

    def test_init_rejects_invalid_type(self):
        with self.assertRaises(WorkflowError):
            wf.init(self.target, 'foo', self.report)

    def test_init_rejects_report_dir_equals_target(self):
        with self.assertRaises(WorkflowError):
            wf.init(self.target, 'skill', self.target)

    def test_init_refuses_existing_run(self):
        wf.init(self.target, 'skill', self.report)
        with self.assertRaises(WorkflowError):
            wf.init(self.target, 'skill', self.report)

    def test_init_rejects_symlink_target(self):
        link = self.base / 'link'
        try:
            link.symlink_to(self.target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('не удалось создать symlink (нужны права/режим разработчика)')
        with self.assertRaises(WorkflowError):
            wf.init(link, 'skill', self.base / 'audit')

    # --- порядок этапов --------------------------------------------------

    def test_record_requires_preflight_first(self):
        manifest = wf.init(self.target, 'skill', self.report)
        with self.assertRaises(WorkflowError):
            self._record(manifest['run_id'], 'AUDIT',
                         data={'checked_files': ['SKILL.md'], 'findings': []})

    def test_record_rejects_skipped_mandatory(self):
        manifest = wf.init(self.target, 'skill', self.report)
        with self.assertRaises(WorkflowError):
            self._record(manifest['run_id'], 'PREFLIGHT', status='SKIPPED', method='NOT_RUN',
                         data={'host_profile': {'host': 'test'}})

    # --- правила метода и вызовов ---------------------------------------

    def test_skill_call_requires_invocations(self):
        manifest = wf.init(self.target, 'skill', self.report)
        with self.assertRaises(WorkflowError):
            self._record(manifest['run_id'], 'PREFLIGHT', method='SKILL_CALL',
                         data={'host_profile': {'host': 'test'}})

    def test_invocations_only_for_skill_call(self):
        manifest = wf.init(self.target, 'skill', self.report)
        with self.assertRaises(WorkflowError):
            self._record(manifest['run_id'], 'PREFLIGHT', method='LOCAL_ANALYSIS',
                         invocations=[{'caller': 'audit-workflow', 'callee': 'audit-skill'}],
                         data={'host_profile': {'host': 'test'}})

    def test_rejects_recursive_audit_workflow(self):
        manifest = wf.init(self.target, 'skill', self.report)
        self._record(manifest['run_id'], 'PREFLIGHT', data={'host_profile': {'host': 'test'}})
        with self.assertRaises(WorkflowError):
            self._record(manifest['run_id'], 'AUDIT', method='SKILL_CALL',
                         invocations=[{'caller': 'audit-workflow', 'callee': 'audit-workflow'}],
                         data={'checked_files': ['SKILL.md'], 'findings': []})

    def test_rejects_ai_tool_generator_callee(self):
        manifest = wf.init(self.target, 'skill', self.report)
        self._record(manifest['run_id'], 'PREFLIGHT', data={'host_profile': {'host': 'test'}})
        with self.assertRaises(WorkflowError):
            self._record(manifest['run_id'], 'AUDIT', method='SKILL_CALL',
                         invocations=[{'caller': 'audit-workflow', 'callee': 'ai-tool-generator'}],
                         data={'checked_files': ['SKILL.md'], 'findings': []})

    def test_rejects_duplicate_skill_call(self):
        manifest = wf.init(self.target, 'skill', self.report)
        self._record(manifest['run_id'], 'PREFLIGHT', data={'host_profile': {'host': 'test'}})
        invocations = [
            {'caller': 'audit-workflow', 'callee': 'audit-skill'},
            {'caller': 'audit-workflow', 'callee': 'audit-skill'},
        ]
        with self.assertRaises(WorkflowError):
            self._record(manifest['run_id'], 'AUDIT', method='SKILL_CALL',
                         invocations=invocations,
                         data={'checked_files': ['SKILL.md'], 'findings': []})

    # --- STALE_INPUT -----------------------------------------------------

    def test_stale_input_blocks_record(self):
        manifest = wf.init(self.target, 'skill', self.report)
        (self.target / 'SKILL.md').write_text('# changed\n', encoding='utf-8')
        with self.assertRaises(WorkflowError) as ctx:
            self._record(manifest['run_id'], 'PREFLIGHT', data={'host_profile': {'host': 'test'}})
        self.assertIn('STALE_INPUT', str(ctx.exception))

    def test_resume_after_init_returns_preflight(self):
        wf.init(self.target, 'skill', self.report)
        res = wf.resume(self.report)
        self.assertEqual(res['status'], 'RUNNING')
        self.assertEqual(res['next_stage'], 'PREFLIGHT')

    # --- finalize --------------------------------------------------------

    def test_finalize_partial_without_audit(self):
        manifest = wf.init(self.target, 'skill', self.report)
        self._record(manifest['run_id'], 'PREFLIGHT', data={'host_profile': {'host': 'test'}})
        self.assertEqual(wf.finalize(self.report)['status'], 'PARTIAL')

    def test_finalize_blocked_on_mandatory(self):
        manifest = wf.init(self.target, 'skill', self.report)
        self._record(manifest['run_id'], 'PREFLIGHT', data={'host_profile': {'host': 'test'}})
        self._record(manifest['run_id'], 'AUDIT', status='BLOCKED',
                     data={'checked_files': [], 'findings': []})
        self.assertEqual(wf.finalize(self.report)['status'], 'BLOCKED')

    @unittest.skipUnless(HAS_MARKDOWN_IT, 'требуется markdown-it-py для валидации отчёта')
    def test_full_pipeline_complete(self):
        manifest = wf.init(self.target, 'skill', self.report)
        run_id = manifest['run_id']

        self._record(run_id, 'PREFLIGHT', data={'host_profile': {'host': 'test'}})
        self._record(run_id, 'AUDIT', method='SKILL_CALL',
                     invocations=[{'caller': 'audit-workflow', 'callee': 'audit-skill'}],
                     data={'checked_files': ['SKILL.md'], 'findings': []})
        self._record(run_id, 'IMPROVE', status='SKIPPED', method='NOT_RUN', data={'proposals': []})
        self._record(run_id, 'MODERNIZE', status='SKIPPED', method='NOT_RUN', data={'proposals': []})

        (self.report / 'README.md').write_text('# Audit\n\nОтчёт.\n', encoding='utf-8')
        (self.report / 'docs').mkdir()
        (self.report / 'docs' / 'workflow-status.md').write_text('# Статус\n\nOK.\n', encoding='utf-8')
        self._record(run_id, 'DOCS', method='LOCAL_ANALYSIS',
                     output_files=['README.md', 'docs/workflow-status.md'])

        self._record(run_id, 'VALIDATE', data={'checks': [{'name': 'links', 'status': 'PASSED'}]})

        self.assertEqual(wf.finalize(self.report)['status'], 'COMPLETE')
        self.assertEqual(wf.resume(self.report)['status'], 'COMPLETE')


if __name__ == '__main__':
    unittest.main()
