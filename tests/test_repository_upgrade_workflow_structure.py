import tempfile
import unittest
from pathlib import Path

from tools.ci_repository_model import build_repository_model
from tools.ci_workflow_structure import (
    NORMAL_JOB_ALLOWED_PROPERTIES,
    REUSABLE_JOB_ALLOWED_PROPERTIES,
    STEP_ALLOWED_PROPERTIES,
    WORKFLOW_ROOT_ALLOWED_PROPERTIES,
    WORKFLOW_STRUCTURE_CONTRACT_VERSION,
    validate_workflow_structure,
)


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def capability(model: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(
        item
        for item in model["capabilities"]
        if item["capability_id"] == capability_id
    )


VALID_TEST_JOB = """  test:
    runs-on: ubuntu-latest
    steps:
      - run: python -m unittest discover -s tests
"""


class WorkflowStructureEvidenceBoundaryTests(unittest.TestCase):
    def model_for(self, workflow: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        write_files(
            root,
            {
                "tests/test_x.py": "import unittest\n",
                ".github/workflows/ci.yml": workflow,
            },
        )
        return build_repository_model(root)

    def assert_invalid_without_test_evidence(
        self,
        model: dict[str, object],
        diagnostic_code: str,
    ) -> None:
        workflow = model["workflows"][0]
        self.assertEqual(workflow["parse_status"], "invalid_shape")
        self.assertEqual(workflow["jobs"], [])
        self.assertEqual(workflow["commands"], [])
        self.assertEqual(workflow["command_evidence"], [])
        self.assertNotEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )
        self.assertIn(
            diagnostic_code,
            {item["code"] for item in model["unresolved_evidence"]},
        )
        self.assertFalse(
            any(
                record.get("status") == "resolved"
                and "test" in record.get("families", [])
                for item in model["workflows"]
                for record in item.get("command_evidence", [])
            )
        )

    def test_unknown_workflow_root_property_blocks_valid_test_job(self):
        model = self.model_for(
            "name: invalid root\n"
            "on: [pull_request]\n"
            "permissions: {}\n"
            "unexpected-root: true\n"
            "jobs:\n"
            + VALID_TEST_JOB
        )
        self.assert_invalid_without_test_evidence(
            model,
            "WORKFLOW_ROOT_PROPERTY_UNSUPPORTED",
        )

    def test_unknown_normal_job_property_blocks_valid_test_job(self):
        model = self.model_for(
            "on: [pull_request]\n"
            "permissions: {}\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    unexpected-job: true\n"
            "    steps:\n"
            "      - run: python -m unittest discover -s tests\n"
        )
        self.assert_invalid_without_test_evidence(
            model,
            "WORKFLOW_NORMAL_JOB_PROPERTY_UNSUPPORTED",
        )

    def test_unknown_reusable_job_property_invalidates_entire_workflow(self):
        model = self.model_for(
            "on: [pull_request]\n"
            "permissions: {}\n"
            "jobs:\n"
            "  call:\n"
            "    uses: ./.github/workflows/reusable.yml\n"
            "    unexpected-reusable: true\n"
            + VALID_TEST_JOB
        )
        self.assert_invalid_without_test_evidence(
            model,
            "WORKFLOW_REUSABLE_JOB_PROPERTY_UNSUPPORTED",
        )

    def test_unknown_step_property_blocks_valid_test_command(self):
        model = self.model_for(
            "on: [pull_request]\n"
            "permissions: {}\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: python -m unittest discover -s tests\n"
            "        unexpected-step: true\n"
        )
        self.assert_invalid_without_test_evidence(
            model,
            "WORKFLOW_STEP_PROPERTY_UNSUPPORTED",
        )

    def test_incompatible_step_execution_forms_fail_closed(self):
        invalid_steps = (
            "      - run: python -m unittest discover -s tests\n"
            "        uses: actions/checkout@v6\n",
            "      - uses: actions/checkout@v6\n"
            "        working-directory: tests\n",
            "      - run: python -m unittest discover -s tests\n"
            "        with:\n"
            "          arg: value\n",
            "      - wait: server\n"
            "        if: always()\n",
            "      - wait-all: server\n",
            "      - parallel:\n"
            "          - wait: server\n",
        )
        for step in invalid_steps:
            with self.subTest(step=step):
                model = self.model_for(
                    "on: [pull_request]\n"
                    "permissions: {}\n"
                    "jobs:\n"
                    "  test:\n"
                    "    runs-on: ubuntu-latest\n"
                    "    steps:\n"
                    + step
                )
                self.assert_invalid_without_test_evidence(
                    model,
                    "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
                )

    def test_yaml_merge_key_is_rejected_before_command_parsing(self):
        model = self.model_for(
            "on: [pull_request]\n"
            "permissions: {}\n"
            "jobs:\n"
            "  template: &test-job\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: python -m unittest discover -s tests\n"
            "  test:\n"
            "    <<: *test-job\n"
        )
        self.assert_invalid_without_test_evidence(
            model,
            "WORKFLOW_YAML_MERGE_KEY_UNSUPPORTED",
        )

    def test_positive_normal_job_remains_operational(self):
        model = self.model_for(
            "name: valid\n"
            "run-name: valid run\n"
            "on: [pull_request]\n"
            "permissions: {}\n"
            "env:\n"
            "  EXAMPLE: value\n"
            "defaults:\n"
            "  run:\n"
            "    shell: bash\n"
            "concurrency: fixture\n"
            "jobs:\n"
            + VALID_TEST_JOB
        )
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )

    def test_supported_property_sets_are_versioned_and_accepted(self):
        self.assertEqual(WORKFLOW_STRUCTURE_CONTRACT_VERSION, "1.0.0")
        self.assertEqual(
            WORKFLOW_ROOT_ALLOWED_PROPERTIES,
            frozenset({
                "name", "run-name", "on", "permissions", "env",
                "defaults", "concurrency", "jobs",
            }),
        )
        self.assertEqual(
            NORMAL_JOB_ALLOWED_PROPERTIES,
            frozenset({
                "name", "permissions", "needs", "if", "runs-on", "snapshot",
                "environment", "concurrency", "outputs", "env", "defaults",
                "steps", "timeout-minutes", "strategy", "continue-on-error",
                "container", "services",
            }),
        )
        self.assertEqual(
            REUSABLE_JOB_ALLOWED_PROPERTIES,
            frozenset({
                "name", "permissions", "needs", "if", "strategy",
                "concurrency", "uses", "with", "secrets",
            }),
        )
        self.assertEqual(
            STEP_ALLOWED_PROPERTIES,
            frozenset({
                "id", "if", "name", "uses", "run", "working-directory",
                "shell", "with", "env", "continue-on-error",
                "timeout-minutes", "background", "wait", "wait-all",
                "cancel", "parallel",
            }),
        )

        data = {
            "name": "all root properties",
            "run-name": "fixture",
            "on": ["pull_request"],
            "permissions": {},
            "env": {"ROOT": "1"},
            "defaults": {"run": {"shell": "bash"}},
            "concurrency": "fixture",
            "jobs": {
                "normal": {
                    "name": "normal",
                    "permissions": {},
                    "needs": "prepare",
                    "if": True,
                    "runs-on": "ubuntu-latest",
                    "snapshot": "fixture",
                    "environment": "test",
                    "concurrency": "normal",
                    "outputs": {"value": "fixture"},
                    "env": {"JOB": "1"},
                    "defaults": {"run": {"shell": "bash"}},
                    "steps": [
                        {
                            "id": "run-step",
                            "if": True,
                            "name": "run",
                            "run": "echo ok",
                            "working-directory": ".",
                            "shell": "bash",
                            "env": {"STEP": "1"},
                            "continue-on-error": False,
                            "timeout-minutes": 1,
                            "background": True,
                        },
                        {
                            "id": "action-step",
                            "if": True,
                            "name": "action",
                            "uses": "actions/checkout@v6",
                            "with": {"fetch-depth": 0},
                            "env": {"STEP": "2"},
                            "continue-on-error": False,
                            "timeout-minutes": 1,
                            "background": True,
                        },
                        {"name": "wait", "wait": "run-step"},
                        {"name": "wait all", "wait-all": None},
                        {"name": "cancel", "cancel": "action-step"},
                        {
                            "name": "parallel",
                            "parallel": [
                                {"name": "one", "run": "echo one"},
                                {"name": "two", "uses": "actions/checkout@v6"},
                            ],
                        },
                    ],
                    "timeout-minutes": 10,
                    "strategy": {"fail-fast": False},
                    "continue-on-error": False,
                    "container": "python:3.13",
                    "services": {},
                },
                "reusable": {
                    "name": "reusable",
                    "permissions": {},
                    "needs": "normal",
                    "if": True,
                    "strategy": {"matrix": {"value": [1]}},
                    "concurrency": "reusable",
                    "uses": "./.github/workflows/reusable.yml",
                    "with": {"input": "value"},
                    "secrets": "inherit",
                },
            },
        }
        self.assertEqual(
            validate_workflow_structure(data, reference="ci.yml"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
