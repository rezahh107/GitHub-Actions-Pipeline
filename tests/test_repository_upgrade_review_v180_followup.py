import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.ci_history_analysis import _parse_paths, collect_structural_history
from tools.ci_repository_model import build_repository_model


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def capability(model: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(item for item in model["capabilities"] if item["capability_id"] == capability_id)


def workflow_for(*, job_if: str | None = None, step_if: str | None = None, mix_run_uses: bool = False) -> str:
    job_condition = f"    if: {job_if}\n" if job_if is not None else ""
    step_condition = f"        if: {step_if}\n" if step_if is not None else ""
    uses = "        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683\n" if mix_run_uses else ""
    return (
        "on: [pull_request]\n"
        "permissions: {}\n"
        "jobs:\n"
        "  test:\n"
        f"{job_condition}"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: execute tests\n"
        f"{step_condition}"
        f"{uses}"
        "        run: python -m unittest discover -s tests\n"
    )


class WorkflowExecutionEligibilityFollowupTests(unittest.TestCase):
    def model(self, workflow: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        write_files(
            root,
            {
                "tests/test_example.py": "import unittest\n\nclass Example(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
                ".github/workflows/ci.yml": workflow,
            },
        )
        return build_repository_model(root)

    def assert_not_operational(self, workflow: str, expected_code: str) -> None:
        model = self.model(workflow)
        self.assertNotEqual(capability(model, "tests_run_on_pull_requests")["state"], "operational")
        self.assertEqual(model["test_suites"]["commands_observed_in_ci"], [])
        codes = {item["code"] for item in model["unresolved_evidence"]}
        self.assertIn(expected_code, codes)
        records = model["workflows"][0]["command_evidence"]
        self.assertFalse(any(record.get("status") == "resolved" and "test" in record.get("families", []) for record in records))

    def test_literal_false_job_cannot_promote_execution(self):
        self.assert_not_operational(workflow_for(job_if="false"), "WORKFLOW_JOB_CONDITION_DISABLED")

    def test_literal_false_step_cannot_promote_execution(self):
        self.assert_not_operational(workflow_for(step_if="false"), "WORKFLOW_STEP_CONDITION_DISABLED")

    def test_run_plus_uses_step_is_structurally_invalid(self):
        self.assert_not_operational(workflow_for(mix_run_uses=True), "WORKFLOW_STEP_EXECUTION_FORM_INVALID")

    def test_dynamic_job_and_step_conditions_remain_unresolved(self):
        self.assert_not_operational(
            workflow_for(job_if="\"${{ github.ref == 'refs/heads/main' }}\""),
            "WORKFLOW_JOB_CONDITION_UNRESOLVED",
        )
        self.assert_not_operational(
            workflow_for(step_if="\"${{ github.actor != '' }}\""),
            "WORKFLOW_STEP_CONDITION_UNRESOLVED",
        )

    def test_absent_and_literal_true_conditions_are_positive_controls(self):
        for workflow in (
            workflow_for(),
            workflow_for(job_if="true", step_if="true"),
            workflow_for(job_if='"${{ true }}"', step_if='"${{ true }}"'),
        ):
            with self.subTest(workflow=workflow):
                model = self.model(workflow)
                self.assertEqual(capability(model, "tests_run_on_pull_requests")["state"], "operational")
                self.assertEqual(model["test_suites"]["commands_observed_in_ci"], ["python -m unittest discover -s tests"])


@unittest.skipUnless(shutil.which("git"), "git required")
class BytePreservingStructuralHistoryFollowupTests(unittest.TestCase):
    def test_parser_preserves_whitespace_and_rejects_non_utf8(self):
        expected = [" leading.py", "trailing.py ", "\tleading-tab.py", "\nleading-newline.py", "@@@evil.py", "یونیکد.py"]
        payload = b"\0".join(item.encode("utf-8") for item in expected) + b"\0"
        parsed, error = _parse_paths(payload)
        self.assertIsNone(error)
        self.assertEqual(parsed, sorted(expected))

        malformed, malformed_error = _parse_paths(b"\xff\0")
        self.assertIsNone(malformed)
        self.assertIn("non-UTF-8", malformed_error or "")

    def test_git_round_trip_preserves_exact_adversarial_filenames_deterministically(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
            filenames = [
                " leading.py",
                "trailing.py ",
                "\tleading-tab.py",
                "\nleading-newline.py",
                "@@@evil.py",
                "space name.py",
                "یونیکد.py",
            ]
            for name in filenames:
                (root / name).write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "fix exact filename evidence"], cwd=root, check=True)

            first = collect_structural_history(root)
            second = collect_structural_history(root)
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "collected")
            self.assertEqual(first["diagnostics"], [])
            self.assertEqual(first["production_without_test_changes"][0]["paths"], sorted(filenames))


if __name__ == "__main__":
    unittest.main()
