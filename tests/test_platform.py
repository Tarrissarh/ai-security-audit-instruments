"""offline integration tests; no AI client is executed."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('platform_compat', ROOT / 'scripts/platform_compat.py')
platform_compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(platform_compat)

class TestPlatformCompatibility(unittest.TestCase):
    def test_all_five_native_staging_smokes(self):
        for platform in platform_compat.PLATFORMS:
            with self.subTest(platform = platform):
                result = platform_compat.smoke(platform)
                self.assertEqual(result['install'], 'LOCAL_INSTALL_PASS')
                self.assertEqual(result['local_discovery'], 'PASS')
                self.assertEqual(result['skill_count'], 11)
                for k in ('real_client_discovery', 'real_client_activation', 'real_client_orchestration', 'real_client_safety'):
                    self.assertEqual(result[k], 'NOT_TESTED')

    def test_shared_four_and_claude_reject(self):
        for platform in ('opencode', 'deepseek-harness', 'codex', 'cursor'):
            with tempfile.TemporaryDirectory() as d:
                project = Path(d)
                result = platform_compat.stage(platform, project, 'shared', True)
                self.assertEqual(result['status'], 'LOCAL_INSTALL_PASS')
                self.assertEqual(platform_compat.inspect(platform, project)['local_discovery_static'], 'PASS')
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                platform_compat.stage('claude-code', Path(d), 'shared', True)

    def test_dry_run_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            result = platform_compat.stage('codex', p, 'native', False)
            self.assertEqual(result['status'], 'READY')
            self.assertFalse((p / '.agents').exists())

    def test_staging_refuses_existing_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            existing = p / '.agents/skills/audit-docs'
            existing.mkdir(parents = True)
            sentinel = existing / 'SKILL.md'
            sentinel.write_text('original')
            plan = platform_compat.stage('codex', p)
            self.assertEqual(plan['status'], 'BLOCKED')
            self.assertTrue(any('audit-docs' in e for e in plan['errors']))
            applied = platform_compat.stage('codex', p, apply = True)
            self.assertEqual(applied['status'], 'BLOCKED')
            self.assertEqual(sentinel.read_text(), 'original')
            self.assertFalse((p / '.agents/skills/audit-workflow').exists())

    def test_deduplicate_across_scanned_roots(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / '.claude/skills/audit-skill').mkdir(parents = True)
            (p / '.claude/skills/audit-skill/SKILL.md').write_text('anything')
            result = platform_compat.stage('cursor', p, apply = True)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertFalse((p / '.cursor/skills').exists())

    def test_refuse_symlink_target(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            p = Path(d)
            (p / '.agents').symlink_to(outside, target_is_directory = True)
            with self.assertRaises(ValueError):
                platform_compat.stage('codex', p, apply = True)
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_only_skill_dirs_and_no_benchmark_gold_are_installed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            platform_compat.stage('opencode', p, apply = True)
            root = p / '.opencode/skills'
            self.assertEqual(set(n.name for n in root.iterdir()), set(platform_compat.IDS))
            self.assertFalse(any(f.name == 'cases.json' for f in root.rglob('*')))
            self.assertTrue((root / 'audit-workflow/references/preflight.md').is_file())
            self.assertTrue((root / 'audit-docs/references/report-template.md').is_file())

    def test_generator_must_retain_manual_only_guard(self):
        f = platform_compat._read_frontmatter(ROOT / 'skills/ai-tool-generator/SKILL.md')
        self.assertEqual(f['disable-model-invocation'], 'true')
        self.assertEqual(platform_compat.validate_bundle(), [])

    def test_fake_malformed_skill_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d)
            for name in platform_compat.IDS:
                t = b / name
                t.mkdir()
                (t / 'SKILL.md').write_text((ROOT / 'skills' / name / 'SKILL.md').read_text(encoding = 'utf-8'), encoding = 'utf-8')
            (b / 'audit-skill/SKILL.md').write_text('---\nname: audit-skill\ndescription: [bad\n---\n')
            result = platform_compat.stage('codex', Path(d), bundle = b)
            self.assertEqual(result['status'], 'BLOCKED')

    def test_discovery_requires_all_skills_and_reports_not_tested(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            result = platform_compat.inspect('claude-code', p)
            self.assertEqual(len(result['missing']), 11)
            self.assertEqual(result['local_discovery_static'], 'FAIL')
            self.assertEqual(result['client_runtime'], 'NOT_TESTED')

    def test_staged_source_bundle_unchanged(self):
        import hashlib
        p = ROOT / 'skills/ai-tool-generator/SKILL.md'
        original = hashlib.sha256(p.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            platform_compat.stage('cursor', Path(d), apply = True)
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), original)

if __name__ == '__main__':
    unittest.main()
