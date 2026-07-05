import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"


class WorkflowContractTests(unittest.TestCase):
    def test_validation_workflow_preserves_full_history_and_read_only_checkout(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("permissions:\n  contents: read", text)

    def test_validation_workflow_has_bounded_runtime_and_artifact_retention(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-24.04", text)
        self.assertIn("timeout-minutes: 10", text)
        self.assertIn("retention-days: 14", text)

    def test_product_markdown_is_not_excluded_from_validation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("paths-ignore", text)
