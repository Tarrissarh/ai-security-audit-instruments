"""Local, read-only checks of validators and bundled skill conventions."""
from pathlib import Path
import sys, tempfile, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_skills import validate, read_frontmatter, NAME_RE, EXPECTED

ROOT = Path(__file__).resolve().parents[1]

class TestBundle(unittest.TestCase):
    def test_expected_count(self):
        found, errors, _ = validate(ROOT)
        self.assertEqual(set(found), EXPECTED)
        self.assertFalse(errors, '\n'.join(errors))
    def test_generator_manual_only(self):
        f, _ = read_frontmatter(ROOT / 'skills' / 'ai-tool-generator' / 'SKILL.md')
        self.assertEqual(f.get('disable-model-invocation'), 'true')
        self.assertIn('явн', (ROOT / 'skills' / 'ai-tool-generator' / 'SKILL.md').read_text().lower())
    def test_deepseek_conditional(self):
        p = (ROOT / 'skills/audit-workflow/references/platform-deepseek-harness.md').read_text()
        self.assertIn('dsh-skill-filesystem', p)
        self.assertIn('dsh-tool-skill', p)
    def test_references_present(self):
        self.assertTrue((ROOT / 'skills/audit-workflow/references/handoff-contract.md').is_file())
        self.assertTrue((ROOT / 'skills/audit-docs/references/report-template.md').is_file())
    def test_name_regex(self):
        self.assertTrue(NAME_RE.fullmatch('audit-workflow'))
        self.assertFalse(NAME_RE.fullmatch('Audit_Workflow'))
    def test_frontmatter_bad_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'SKILL.md'
            p.write_text('not yaml\n')
            _, errs = read_frontmatter(p)
            self.assertTrue(errs)
    def test_workflow_no_automatic_generator(self):
        s = (ROOT / 'skills/audit-workflow/SKILL.md').read_text().lower()
        self.assertIn('не вызывай', s)
        self.assertIn('ai-tool-generator', s)

if __name__ == '__main__':
    unittest.main()
