import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"


class WorkflowContractTests(unittest.TestCase):
    def test_validation_workflow_checks_out_and_verifies_exact_source_head(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ref: ${{ github.event.pull_request.head.sha || github.sha }}", text)
        self.assertIn("Verify exact source-head checkout", text)
        self.assertIn('tested_sha="$(git rev-parse HEAD)"', text)
        self.assertIn('if [[ "$tested_sha" != "$EXPECTED_SOURCE_HEAD_SHA" ]]', text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("fetch-depth: 0", text)

    def test_summary_uses_verified_environment_identity_not_event_sha_as_tested_sha(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        summary_section = text.split("- name: Write run summary and identity", 1)[1]
        self.assertNotIn("TESTED_SHA: ${{ github.sha }}", summary_section)
        self.assertNotIn("SOURCE_HEAD_SHA: ${{", summary_section)
        self.assertIn("RUN_IDENTITY_OUT:", summary_section)

    def test_validation_workflow_preserves_read_only_permissions(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)

    def test_validation_workflow_has_bounded_runtime_and_artifact_retention(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-24.04", text)
        self.assertIn("timeout-minutes: 10", text)
        self.assertIn("retention-days: 14", text)

    def test_product_markdown_is_not_excluded_from_validation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("paths-ignore", text)


if __name__ == "__main__":
    unittest.main()
