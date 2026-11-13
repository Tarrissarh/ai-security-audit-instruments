# Описывает назначение блока в многострочной строке документации.
"""Offline workflow-state regression tests. Never execute code from audited targets."""
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
import tempfile
# Импортирует модуль или имена, используемые в этом файле.
import unittest

# Сохраняет или обновляет вычисленное значение для последующих операций.
ROOT = Path(__file__).resolve().parents[1]
# Формирует часть выражения или передаёт аргумент в текущую операцию.
sys.path.insert(0, str(ROOT / 'skills' / 'audit-workflow' / 'scripts'))
# Импортирует модуль или имена, используемые в этом файле.
from workflow_state import (WorkflowError, init, record, resume, finalize,
                            # Формирует часть выражения или передаёт аргумент в текущую операцию.
                            load_manifest, source_fingerprint, schema, validate_schema)


# Определяет класс и его интерфейс.
class StageStateTests(unittest.TestCase):
    # Объявляет функцию setUp и её параметры.
    def setUp(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.tmp = tempfile.TemporaryDirectory()
        # Вызывает проверку или метод текущего объекта.
        self.addCleanup(self.tmp.cleanup)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.root = Path(self.tmp.name)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.target = self.root / 'tool'
        # Вызывает проверку или метод текущего объекта.
        self.target.mkdir()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.target / 'SKILL.md').write_text('---\nname: example\n---\n# Tool\n', encoding = 'utf8')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.report = self.target / 'audit'
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.manifest = init(self.target, 'skill', self.report)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.runid = self.manifest['run_id']
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        self.counter = 0

    # Объявляет функцию payload и её параметры.
    def payload(self, stage, status = 'COMPLETE', method = 'LOCAL_ANALYSIS', **kw):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        data = {
            # Устанавливает поле PREFLIGHT в словаре или описании.
            'PREFLIGHT': {'host_profile': {'platform': 'other', 'available': []}},
            # Устанавливает поле AUDIT в словаре или описании.
            'AUDIT': {'checked_files': ['SKILL.md'], 'findings': []},
            # Устанавливает поле IMPROVE в словаре или описании.
            'IMPROVE': {'proposals': []},
            # Устанавливает поле MODERNIZE в словаре или описании.
            'MODERNIZE': {'proposals': []},
            # Устанавливает поле DOCS в словаре или описании.
            'DOCS': {},
            # Устанавливает поле VALIDATE в словаре или описании.
            'VALIDATE': {'checks': [{'name': 'links', 'status': 'PASSED'}]},
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        }[stage]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        obj = {'schema_version': '1.0', 'run_id': self.runid, 'stage': stage,
               # Устанавливает поле status в словаре или описании.
               'status': status, 'method': method, 'evidence': ['SKILL.md:1'],
               # Устанавливает поле output_files в словаре или описании.
               'output_files': [], 'invocations': [], 'data': data, 'limitations': []}
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        obj.update(kw)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        self.counter += 1
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        path = self.root / f'payload-{self.counter}.json'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        path.write_text(json.dumps(obj, ensure_ascii = False), encoding = 'utf8')
        # Возвращает вычисленный результат вызывающему коду.
        return path

    # Объявляет функцию apply и её параметры.
    def apply(self, stage, status = 'COMPLETE', **kw):
        # Возвращает вычисленный результат вызывающему коду.
        return record(self.report, self.payload(stage, status, **kw))

    # Объявляет функцию prepare_docs и её параметры.
    def prepare_docs(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.report / 'docs').mkdir(parents = True, exist_ok = True)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.report / 'README.md').write_text('# Итог\n\n[Подробнее](docs/audit.md)\n', encoding = 'utf8')
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.report / 'docs' / 'audit.md').write_text('# Audit\n\nТекст.\n', encoding = 'utf8')
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.report / 'docs' / 'workflow-status.md').write_text('# Workflow status\n\nVALIDATE: PENDING at publication\n', encoding = 'utf8')
        # Возвращает вычисленный результат вызывающему коду.
        return ['README.md', 'docs/audit.md', 'docs/workflow-status.md']

    # Объявляет функцию first_four и её параметры.
    def first_four(self):
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT')
        # Вызывает проверку или метод текущего объекта.
        self.apply('AUDIT')
        # Вызывает проверку или метод текущего объекта.
        self.apply('IMPROVE')
        # Вызывает проверку или метод текущего объекта.
        self.apply('MODERNIZE')

    # Объявляет функцию complete_all и её параметры.
    def complete_all(self):
        # Вызывает проверку или метод текущего объекта.
        self.first_four()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        paths = self.prepare_docs()
        # Вызывает проверку или метод текущего объекта.
        self.apply('DOCS', output_files = paths)
        # Вызывает проверку или метод текущего объекта.
        self.apply('VALIDATE')

    # Объявляет функцию test_start_and_resume и её параметры.
    def test_start_and_resume(self):
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(resume(self.report)['next_stage'], 'PREFLIGHT')
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(resume(self.report)['next_stage'], 'AUDIT')

    # Объявляет функцию test_completed_workflow и её параметры.
    def test_completed_workflow(self):
        # Вызывает проверку или метод текущего объекта.
        self.complete_all()
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(finalize(self.report)['status'], 'COMPLETE')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIsNone(resume(self.report)['next_stage'])

    # Объявляет функцию test_missing_required_stages_cannot_complete и её параметры.
    def test_missing_required_stages_cannot_complete(self):
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(finalize(self.report)['status'], 'PARTIAL')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(resume(self.report)['next_stage'], 'AUDIT')

    # Объявляет функцию test_skip_optional_allowed и её параметры.
    def test_skip_optional_allowed(self):
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT')
        # Вызывает проверку или метод текущего объекта.
        self.apply('AUDIT')
        # Вызывает проверку или метод текущего объекта.
        self.apply('IMPROVE', status = 'SKIPPED', method = 'NOT_RUN', data = {'proposals': []})
        # Вызывает проверку или метод текущего объекта.
        self.apply('MODERNIZE', status = 'SKIPPED', method = 'NOT_RUN', data = {'proposals': []})
        # Вызывает проверку или метод текущего объекта.
        self.apply('DOCS', output_files = self.prepare_docs())
        # Вызывает проверку или метод текущего объекта.
        self.apply('VALIDATE')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(finalize(self.report)['status'], 'COMPLETE')

    # Объявляет функцию test_stage_order и её параметры.
    def test_stage_order(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'before'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('AUDIT')

    # Объявляет функцию test_invalid_json и её параметры.
    def test_invalid_json(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.root / 'bad.json'
        # Настраивает аргументы, параметры или состояние объекта.
        p.write_text('{BROKEN', encoding = 'utf8')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'invalid payload JSON'):
            # Вызывает функцию для выполнения операции.
            record(self.report, p)

    # Объявляет функцию test_schema_rejects_incomplete_contract и её параметры.
    def test_schema_rejects_incomplete_contract(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.payload('PREFLIGHT')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        data = json.loads(p.read_text(encoding = 'utf8'))
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        data.pop('evidence')
        # Настраивает аргументы, параметры или состояние объекта.
        p.write_text(json.dumps(data), encoding = 'utf8')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'evidence'):
            # Вызывает функцию для выполнения операции.
            record(self.report, p)

    # Объявляет функцию test_cross_run_payload и её параметры.
    def test_cross_run_payload(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.payload('PREFLIGHT', run_id = 'a' * 32)
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'run_id'):
            # Вызывает функцию для выполнения операции.
            record(self.report, p)

    # Объявляет функцию test_idempotent_record и её параметры.
    def test_idempotent_record(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        p = self.payload('PREFLIGHT')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(record(self.report, p)['status'], 'RECORDED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(record(self.report, p)['status'], 'UNCHANGED')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(load_manifest(self.report)['stages']['PREFLIGHT']['attempts'], 1)

    # Объявляет функцию test_conflicting_completed_stage и её параметры.
    def test_conflicting_completed_stage(self):
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'already resolved'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('PREFLIGHT', evidence = ['new assertion'])

    # Объявляет функцию test_failed_stage_retries_once и её параметры.
    def test_failed_stage_retries_once(self):
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT', status = 'FAILED', limitations = ['temporary failure'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(resume(self.report)['next_stage'], 'PREFLIGHT')
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(load_manifest(self.report)['stages']['PREFLIGHT']['attempts'], 2)
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(resume(self.report)['next_stage'], 'AUDIT')

    # Объявляет функцию test_failed_stage_max_attempts и её параметры.
    def test_failed_stage_max_attempts(self):
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT', status = 'FAILED')
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT', status = 'FAILED', limitations = ['different failure'])
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'retry limit'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('PREFLIGHT', status = 'COMPLETE')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertIsNone(resume(self.report)['next_stage'])
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(finalize(self.report)['status'], 'FAILED')

    # Объявляет функцию test_input_change_blocks_resume и её параметры.
    def test_input_change_blocks_resume(self):
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT')
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.target / 'SKILL.md').write_text('changed source', encoding = 'utf8')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'STALE_INPUT'):
            # Вызывает функцию для выполнения операции.
            resume(self.report)

    # Объявляет функцию test_report_changes_excluded_from_source_hash и её параметры.
    def test_report_changes_excluded_from_source_hash(self):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        before = source_fingerprint(self.target, self.report)
        # Вызывает проверку или метод текущего объекта.
        self.prepare_docs()
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(before, source_fingerprint(self.target, self.report))

    # Объявляет функцию test_document_paths_escape_rejected и её параметры.
    def test_document_paths_escape_rejected(self):
        # Вызывает проверку или метод текущего объекта.
        self.first_four()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'unsafe output path'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('DOCS', output_files = ['README.md', 'docs/workflow-status.md', '../SKILL.md'])

    # Объявляет функцию test_document_missing_rejected и её параметры.
    def test_document_missing_rejected(self):
        # Вызывает проверку или метод текущего объекта.
        self.first_four()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'missing or empty'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('DOCS', output_files = ['README.md', 'docs/workflow-status.md'])

    # Объявляет функцию test_report_broken_link_rejected и её параметры.
    def test_report_broken_link_rejected(self):
        # Вызывает проверку или метод текущего объекта.
        self.first_four()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        files = self.prepare_docs()
        # Вызывает проверку или метод текущего объекта.
        self.apply('DOCS', output_files = files)
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.report / 'README.md').write_text('# Title\n[Broken](docs/not-here.md)', encoding = 'utf8')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'document changed'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('VALIDATE')

    # Объявляет функцию test_unmodified_broken_link_rejected и её параметры.
    def test_unmodified_broken_link_rejected(self):
        # Вызывает проверку или метод текущего объекта.
        self.first_four()
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        files = self.prepare_docs()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.report / 'README.md').write_text('# Title\n[Broken](docs/not-here.md)', encoding = 'utf8')
        # Вызывает проверку или метод текущего объекта.
        self.apply('DOCS', output_files = files)
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'link validation'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('VALIDATE')

    # Объявляет функцию test_artifact_tamper_refused и её параметры.
    def test_artifact_tamper_refused(self):
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        info = load_manifest(self.report)['stages']['PREFLIGHT']
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        path = self.report / 'state' / info['artifact']
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        path.write_text(path.read_text('utf8').replace('host_profile', 'host_Xrofile'), encoding = 'utf8')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'checksum mismatch'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('AUDIT')

    # Объявляет функцию test_docs_integrity_checked_even_after_complete и её параметры.
    def test_docs_integrity_checked_even_after_complete(self):
        # Вызывает проверку или метод текущего объекта.
        self.complete_all()
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(finalize(self.report)['status'], 'COMPLETE')
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.report / 'README.md').write_text('# Changed\n', encoding = 'utf8')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'document changed'):
            # Вызывает функцию для выполнения операции.
            resume(self.report)

    # Объявляет функцию test_cannot_skip_required_stage и её параметры.
    def test_cannot_skip_required_stage(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'cannot be SKIPPED'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('PREFLIGHT', status = 'SKIPPED', method = 'NOT_RUN')

    # Объявляет функцию test_generator_never_called и её параметры.
    def test_generator_never_called(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'ai-tool-generator'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('PREFLIGHT', method = 'SKILL_CALL', invocations = [{'caller': 'audit-workflow', 'callee': 'ai-tool-generator'}])

    # Объявляет функцию test_recursive_call_forbidden и её параметры.
    def test_recursive_call_forbidden(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'recursive'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('PREFLIGHT', method = 'SKILL_CALL', invocations = [{'caller': 'audit-docs', 'callee': 'audit-workflow'}])

    # Объявляет функцию test_cycle_rejected и её параметры.
    def test_cycle_rejected(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'cyclic'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('PREFLIGHT', method = 'SKILL_CALL', invocations = [{'caller': 'A', 'callee': 'B'}, {'caller': 'B', 'callee': 'A'}])

    # Объявляет функцию test_duplicate_call_rejected и её параметры.
    def test_duplicate_call_rejected(self):
        # Вызывает проверку или метод текущего объекта.
        self.apply('PREFLIGHT', method = 'SKILL_CALL', invocations = [{'caller': 'audit-workflow', 'callee': 'audit-skill'}])
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'duplicate programmatic'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('AUDIT', method = 'SKILL_CALL', invocations = [{'caller': 'audit-workflow', 'callee': 'audit-skill'}])

    # Объявляет функцию test_declared_skill_call_requires_invocation и её параметры.
    def test_declared_skill_call_requires_invocation(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'requires documented'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('PREFLIGHT', method = 'SKILL_CALL')

    # Объявляет функцию test_read_instructions_has_no_invocations и её параметры.
    def test_read_instructions_has_no_invocations(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'must be empty'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('PREFLIGHT', method = 'READ_INSTRUCTIONS', invocations = [{'caller': 'a', 'callee': 'b'}])

    # Объявляет функцию test_validated_doc_damaged_after_validation_blocks_finalize и её параметры.
    def test_validated_doc_damaged_after_validation_blocks_finalize(self):
        # Вызывает проверку или метод текущего объекта.
        self.complete_all()
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.report / 'docs' / 'audit.md').unlink()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'missing or empty'):
            # Вызывает функцию для выполнения операции.
            finalize(self.report)

    # Объявляет функцию test_staging_is_not_permitted_inside_output_files и её параметры.
    def test_staging_is_not_permitted_inside_output_files(self):
        # Вызывает проверку или метод текущего объекта.
        self.first_four()
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'not a report Markdown'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('DOCS', output_files = ['README.md', 'docs/workflow-status.md', 'state/manifest.json'])

    # Объявляет функцию test_unverifiable_required_validation и её параметры.
    def test_unverifiable_required_validation(self):
        # Вызывает проверку или метод текущего объекта.
        self.first_four()
        # Вызывает проверку или метод текущего объекта.
        self.apply('DOCS', output_files = self.prepare_docs())
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'requires explicit checks'):
            # Вызывает проверку или метод текущего объекта.
            self.apply('VALIDATE', data = {'checks': []})

    # Объявляет функцию test_symlink_source_refused и её параметры.
    def test_symlink_source_refused(self):
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        (self.target / 'link.md').symlink_to(self.target / 'SKILL.md')
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaisesRegex(WorkflowError, 'symlink'):
            # Вызывает функцию для выполнения операции.
            resume(self.report)

    # Объявляет функцию test_payload_is_not_saved_when_validation_fails и её параметры.
    def test_payload_is_not_saved_when_validation_fails(self):
        # Открывает управляемый контекст и гарантирует его корректное завершение.
        with self.assertRaises(WorkflowError):
            # Вызывает проверку или метод текущего объекта.
            self.apply('PREFLIGHT', method = 'SKILL_CALL')
        # Проверяет ожидаемое поведение средствами unittest.
        self.assertEqual(load_manifest(self.report)['stages']['PREFLIGHT']['attempts'], 0)

    # Объявляет функцию test_manifest_schema и её параметры.
    def test_manifest_schema(self):
        # Вызывает функцию для выполнения операции.
        validate_schema(load_manifest(self.report), 'manifest')


# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    unittest.main()
