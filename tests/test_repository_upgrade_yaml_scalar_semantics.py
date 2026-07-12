import tempfile
import unittest
from pathlib import Path

import yaml

from tools.ci_repository_collectors import GitHubWorkflowLoader
from tools.ci_repository_model import build_repository_model


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


def workflow_for(raw_condition: str | None, scope: str) -> str:
    job_condition = (
        f"    if: {raw_condition}\n"
        if scope == "job" and raw_condition is not None
        else ""
    )
    step_condition = (
        f"      - if: {raw_condition}\n"
        if scope == "step" and raw_condition is not None
        else "      - "
    )
    run_indent = "        " if scope == "step" and raw_condition is not None else "run: "
    if scope == "step" and raw_condition is not None:
        step = f"{step_condition}{run_indent}run: pytest tests/test_x.py\n"
    else:
        step = f"{step_condition}{run_indent}pytest tests/test_x.py\n"
    return (
        "name: scalar semantics\n"
        "on: [pull_request]\n"
        "permissions: {}\n"
        "jobs:\n"
        "  test:\n"
        f"{job_condition}"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"{step}"
    )


class GitHubWorkflowYamlScalarSemanticsTests(unittest.TestCase):
    def model_for(self, raw_condition: str | None, scope: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        write_files(
            root,
            {
                "tests/test_x.py": "def test_x(): assert True\n",
                ".github/workflows/ci.yml": workflow_for(raw_condition, scope),
            },
        )
        return build_repository_model(root)

    def assert_no_resolved_test_evidence(self, model: dict[str, object]) -> None:
        records = model["workflows"][0]["command_evidence"]
        self.assertFalse(
            any(
                record.get("status") == "resolved"
                and "test" in record.get("families", [])
                for record in records
            )
        )
        self.assertNotEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )

    def test_yaml_11_words_remain_text_for_job_and_step_conditions(self):
        text_scalars = (
            "yes", "no", "on", "off", "y", "n",
            '"yes"', '"no"', '"on"', '"off"', '"y"', '"n"',
            "'yes'", "'no'", "'on'", "'off'", "'y'", "'n'",
        )
        for scope in ("job", "step"):
            expected_code = f"WORKFLOW_{scope.upper()}_CONDITION_UNRESOLVED"
            for raw_condition in text_scalars:
                with self.subTest(scope=scope, condition=raw_condition):
                    model = self.model_for(raw_condition, scope)
                    self.assert_no_resolved_test_evidence(model)
                    self.assertIn(
                        expected_code,
                        {item["code"] for item in model["unresolved_evidence"]},
                    )
                    self.assertEqual(
                        model["workflows"][0]["triggers"],
                        ["pull_request"],
                    )

    def test_yaml_12_true_variants_and_absent_condition_remain_positive(self):
        positive_conditions = (
            None,
            "true",
            "True",
            "TRUE",
            '"true"',
            "'True'",
            "${{ true }}",
        )
        for scope in ("job", "step"):
            for raw_condition in positive_conditions:
                with self.subTest(scope=scope, condition=raw_condition):
                    model = self.model_for(raw_condition, scope)
                    self.assertEqual(
                        capability(model, "tests_run_on_pull_requests")["state"],
                        "operational",
                    )
                    self.assertTrue(
                        any(
                            record.get("status") == "resolved"
                            and "test" in record.get("families", [])
                            for record in model["workflows"][0]["command_evidence"]
                        )
                    )
                    self.assertEqual(
                        capability(
                            model,
                            "least_privilege_workflow_permissions",
                        )["state"],
                        "operational",
                    )

    def test_yaml_12_false_variants_disable_job_and_step_evidence(self):
        false_conditions = (
            "false",
            "False",
            "FALSE",
            '"false"',
            "'False'",
            "${{ false }}",
        )
        for scope in ("job", "step"):
            expected_code = f"WORKFLOW_{scope.upper()}_CONDITION_DISABLED"
            for raw_condition in false_conditions:
                with self.subTest(scope=scope, condition=raw_condition):
                    model = self.model_for(raw_condition, scope)
                    self.assert_no_resolved_test_evidence(model)
                    self.assertIn(
                        expected_code,
                        {item["code"] for item in model["unresolved_evidence"]},
                    )

    def test_explicit_supported_bool_tags_follow_true_false_semantics(self):
        for scope in ("job", "step"):
            with self.subTest(scope=scope, condition="!!bool true"):
                enabled = self.model_for("!!bool true", scope)
                self.assertEqual(
                    capability(enabled, "tests_run_on_pull_requests")["state"],
                    "operational",
                )
            with self.subTest(scope=scope, condition="!!bool False"):
                disabled = self.model_for("!!bool False", scope)
                self.assert_no_resolved_test_evidence(disabled)
                self.assertIn(
                    f"WORKFLOW_{scope.upper()}_CONDITION_DISABLED",
                    {item["code"] for item in disabled["unresolved_evidence"]},
                )

    def test_explicit_unsupported_bool_tags_fail_closed(self):
        for scope in ("job", "step"):
            for scalar in ("yes", "no", "on", "off", "y", "n"):
                raw_condition = f"!!bool {scalar}"
                with self.subTest(scope=scope, condition=raw_condition):
                    model = self.model_for(raw_condition, scope)
                    self.assert_no_resolved_test_evidence(model)
                    self.assertEqual(
                        model["workflows"][0]["parse_status"],
                        "ConstructorError",
                    )
                    self.assertIn(
                        "WORKFLOW_PARSE_FAILED",
                        {item["code"] for item in model["unresolved_evidence"]},
                    )

    def test_dedicated_loader_does_not_mutate_pyyaml_safe_loader(self):
        self.assertIs(yaml.safe_load("value: yes\n")["value"], True)
        self.assertEqual(
            yaml.load("value: yes\n", Loader=GitHubWorkflowLoader)["value"],
            "yes",
        )
        self.assertEqual(
            yaml.load("value: on\n", Loader=GitHubWorkflowLoader)["value"],
            "on",
        )


if __name__ == "__main__":
    unittest.main()
