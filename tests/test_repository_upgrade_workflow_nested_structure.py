import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.ci_repository_model import build_repository_model
from tools.ci_workflow_nested_patch import (
    NESTED_SCHEMA_COVERAGE_MAP,
    WORKFLOW_NESTED_SCHEMA_CONTRACT_VERSION,
    _KNOWN_RULES,
    validate_nested_workflow_structure,
)
from tools.ci_workflow_structure import (
    NORMAL_JOB_ALLOWED_PROPERTIES,
    REUSABLE_JOB_ALLOWED_PROPERTIES,
    STEP_ALLOWED_PROPERTIES,
    WORKFLOW_ROOT_ALLOWED_PROPERTIES,
)


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def capability(model: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(item for item in model["capabilities"] if item["capability_id"] == capability_id)


def workflow(extra_job: str = "", extra_step: str = "") -> str:
    return (
        "on: [pull_request]\npermissions: {}\njobs:\n  test:\n"
        "    runs-on: ubuntu-latest\n"
        f"{extra_job}"
        "    steps:\n      - run: python -m unittest discover -s tests\n"
        f"{extra_step}"
    )


class NestedWorkflowStructureTests(unittest.TestCase):
    def model(self, source: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        write_files(root, {
            "tests/test_x.py": "import unittest\n",
            ".github/workflows/ci.yml": source,
        })
        return build_repository_model(root)

    def assert_invalid(self, source: str, code: str | set[str]) -> None:
        model = self.model(source)
        item = model["workflows"][0]
        self.assertEqual(item["parse_status"], "invalid_shape")
        self.assertEqual(item["jobs"], [])
        self.assertEqual(item["commands"], [])
        self.assertEqual(item["command_evidence"], [])
        self.assertNotEqual(capability(model, "tests_run_on_pull_requests")["state"], "operational")
        expected = {code} if isinstance(code, str) else code
        self.assertTrue(expected & {value["code"] for value in model["unresolved_evidence"]})
        self.assertFalse(any(
            record.get("status") == "resolved" and "test" in record.get("families", [])
            for record in item["command_evidence"]
        ))

    def test_strategy_unknown_and_wrong_types_fail_closed(self):
        cases = (
            "    strategy:\n      unexpected: true\n",
            "    strategy:\n      fail-fast: [false]\n",
            "    strategy:\n      max-parallel: many\n",
            "    strategy:\n      matrix: [python]\n",
        )
        for value in cases:
            with self.subTest(value=value):
                self.assert_invalid(workflow(value), "WORKFLOW_STRATEGY_STRUCTURE_INVALID")

    def test_defaults_concurrency_and_environment_fail_closed(self):
        cases = (
            ("    defaults:\n      unexpected: true\n", "WORKFLOW_DEFAULTS_STRUCTURE_INVALID"),
            ("    defaults:\n      run:\n        unexpected: true\n", "WORKFLOW_DEFAULTS_STRUCTURE_INVALID"),
            ("    concurrency:\n      group: ci\n      unexpected: true\n", "WORKFLOW_CONCURRENCY_STRUCTURE_INVALID"),
            ("    concurrency:\n      group: [ci]\n", "WORKFLOW_CONCURRENCY_STRUCTURE_INVALID"),
            ("    concurrency:\n      group: ci\n      queue: invalid\n", "WORKFLOW_CONCURRENCY_STRUCTURE_INVALID"),
            ("    concurrency:\n      group: ci\n      queue: max\n      cancel-in-progress: true\n", "WORKFLOW_CONCURRENCY_STRUCTURE_INVALID"),
            ("    environment:\n      name: test\n      unexpected: true\n", "WORKFLOW_ENVIRONMENT_STRUCTURE_INVALID"),
            ("    environment:\n      name: [test]\n", "WORKFLOW_ENVIRONMENT_STRUCTURE_INVALID"),
        )
        for value, code in cases:
            with self.subTest(value=value):
                self.assert_invalid(workflow(value), code)

    def test_container_services_and_snapshot_fail_closed(self):
        cases = (
            ("    container:\n      image: python:3.12\n      unexpected: true\n", "WORKFLOW_CONTAINER_STRUCTURE_INVALID"),
            ("    container:\n      env: {}\n", "WORKFLOW_CONTAINER_STRUCTURE_INVALID"),
            ("    services:\n      db:\n        image: postgres:16\n        unexpected: true\n", "WORKFLOW_SERVICES_STRUCTURE_INVALID"),
            ("    services:\n      db: postgres:16\n", "WORKFLOW_SERVICES_STRUCTURE_INVALID"),
            ("    snapshot:\n      image-name: fixture\n      unexpected: true\n", "WORKFLOW_SNAPSHOT_STRUCTURE_INVALID"),
            ("    snapshot:\n      version: latest\n", "WORKFLOW_SNAPSHOT_STRUCTURE_INVALID"),
        )
        for value, code in cases:
            with self.subTest(value=value):
                self.assert_invalid(workflow(value), code)

    def test_other_admitted_nested_values_are_not_opaque(self):
        cases = (
            "on:\n  push:\n    unexpected: [main]\npermissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m unittest discover -s tests\n",
            workflow("    permissions:\n      unknown: read\n"),
            workflow("    runs-on:\n      unexpected: runner\n"),
            workflow("    outputs:\n      result: [bad]\n"),
            workflow(extra_step="        with:\n          nested:\n            value: bad\n"),
        )
        for source in cases:
            with self.subTest(source=source):
                self.assert_invalid(source, "WORKFLOW_TRIGGER_STRUCTURE_INVALID" if "unexpected: [main]" in source else next(
                    code for token, code in (
                        ("unknown: read", {"WORKFLOW_PERMISSION_STRUCTURE_INVALID", "WORKFLOW_PERMISSIONS_STRUCTURE_INVALID"}),
                        ("unexpected: runner", "WORKFLOW_RUNS_ON_STRUCTURE_INVALID"),
                        ("result: [bad]", "WORKFLOW_NESTED_VALUE_INVALID"),
                        ("nested:", "WORKFLOW_STEP_EXECUTION_FORM_INVALID"),
                    ) if token in source
                ))

    def test_invalid_reusable_nested_value_invalidates_valid_normal_job(self):
        source = (
            "on: [pull_request]\npermissions: {}\njobs:\n"
            "  call:\n    uses: ./.github/workflows/reusable.yml\n"
            "    strategy:\n      matrix: [bad]\n"
            "  test:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: python -m unittest discover -s tests\n"
        )
        self.assert_invalid(source, "WORKFLOW_STRATEGY_STRUCTURE_INVALID")

    def test_coverage_map_is_complete_versioned_and_runtime_enforced(self):
        self.assertEqual(WORKFLOW_NESTED_SCHEMA_CONTRACT_VERSION, "1.0.0")
        expected = {
            "workflow": WORKFLOW_ROOT_ALLOWED_PROPERTIES,
            "normal_job": NORMAL_JOB_ALLOWED_PROPERTIES,
            "reusable_job": REUSABLE_JOB_ALLOWED_PROPERTIES,
            "step": STEP_ALLOWED_PROPERTIES,
        }
        self.assertEqual(set(NESTED_SCHEMA_COVERAGE_MAP), set(expected))
        for surface, allowed in expected.items():
            configured = NESTED_SCHEMA_COVERAGE_MAP[surface]
            self.assertEqual(set(configured), set(allowed))
            self.assertLessEqual(set(configured.values()), _KNOWN_RULES)
        incomplete = {k: v for k, v in NESTED_SCHEMA_COVERAGE_MAP["normal_job"].items() if k != "strategy"}
        with patch.dict(NESTED_SCHEMA_COVERAGE_MAP["normal_job"], incomplete, clear=True):
            diagnostics = validate_nested_workflow_structure({
                "on": ["pull_request"],
                "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": [{"run": "pytest"}]}},
            }, reference="ci.yml")
        self.assertEqual({item["code"] for item in diagnostics}, {"WORKFLOW_NESTED_SCHEMA_COVERAGE_GAP"})

    def test_positive_controls_cover_retained_nested_forms(self):
        data = {
            "name": "positive", "run-name": "positive run",
            "on": {"push": {"branches": ["main"], "paths": ["**.py"]}, "pull_request": None, "schedule": [{"cron": "0 0 * * *"}]},
            "permissions": {"contents": "read"}, "env": {"ROOT": "1"},
            "defaults": {"run": {"shell": "bash", "working-directory": "."}},
            "concurrency": {"group": "positive", "cancel-in-progress": False, "queue": "single"},
            "jobs": {
                "normal": {
                    "name": "normal", "permissions": {}, "needs": ["prepare"], "if": True,
                    "runs-on": {"group": "runners", "labels": ["linux"]},
                    "snapshot": {"image-name": "fixture", "version": "2.*", "if": True},
                    "environment": {"name": "test", "url": "https://example.test", "deployment": False},
                    "concurrency": "normal", "outputs": {"result": "ok"}, "env": {"JOB": "1"},
                    "defaults": {"run": {"shell": "bash"}},
                    "steps": [
                        {"id": "run", "name": "run", "if": True, "run": "echo ok", "working-directory": ".", "shell": "bash", "env": {"STEP": "1"}, "continue-on-error": False, "timeout-minutes": 1, "background": True},
                        {"uses": "actions/checkout@v6", "with": {"fetch-depth": 0}},
                        {"wait": "run"}, {"wait-all": None}, {"cancel": "run"},
                        {"parallel": [{"run": "echo one"}, {"uses": "actions/checkout@v6"}]},
                    ],
                    "timeout-minutes": 10,
                    "strategy": {"matrix": {"os": ["ubuntu-latest"], "include": [{"os": "macos-latest"}], "exclude": [{"os": "windows-latest"}]}, "fail-fast": False, "max-parallel": 2},
                    "continue-on-error": False,
                    "container": {"image": "python:3.12", "credentials": {"username": "user", "password": "pass"}, "env": {"C": "1"}, "ports": [80], "volumes": ["data:/data"], "options": "--cpus 1"},
                    "services": {"db": {"image": "postgres:16", "env": {"PASSWORD": "pass"}, "ports": [5432], "volumes": ["data:/db"], "options": "--health-cmd ok", "command": "postgres", "entrypoint": "entrypoint"}},
                },
                "reusable": {"name": "reusable", "permissions": {}, "needs": "normal", "if": True, "strategy": {"matrix": {"value": [1]}}, "concurrency": "reusable", "uses": "./.github/workflows/reusable.yml", "with": {"input": "value"}, "secrets": "inherit"},
            },
        }
        self.assertEqual(validate_nested_workflow_structure(data, reference="ci.yml"), [])

    def test_simple_valid_pull_request_workflow_remains_operational(self):
        model = self.model(workflow())
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(capability(model, "tests_run_on_pull_requests")["state"], "operational")


if __name__ == "__main__":
    unittest.main()
