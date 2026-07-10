import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[1]

from tools.ci_command_evidence import parse_run_block
from tools.ci_implementation_engine import apply_implementation_package
from tools.ci_outcome_registry import build_profile_evolution_proposals, validate_outcome_registry
from tools.ci_recommendations import generate_recommendations
from tools.ci_repository_model import build_repository_model
from tools.ci_transaction import execute_recoverable_implementation
from tools.ci_upgrade_models import DEEP_REPOSITORY_UPGRADE, UpgradeContractError


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def capability(model: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(item for item in model["capabilities"] if item["capability_id"] == capability_id)


def init_git(root: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=root, check=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def package_for(path: str = ".github/workflows/generated.yml") -> dict[str, object]:
    content = "name: generated\n"
    return {
        "implementation_contract_version": "1.0.0",
        "mutation_default": "dry_run",
        "repository": "fixture/repo",
        "analysis_basis_sha256": "a" * 64,
        "actions": [{
            "action_id": "action:test",
            "recipe_id": "test-recipe",
            "recommendation_id": "TEST",
            "status": "applicable",
            "operation": "create_file",
            "path": path,
            "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "proposed_content": content,
            "preconditions": [],
            "validation_commands": [],
            "diagnostics": [],
            "evidence": {"state": "derived", "references": ["TEST"], "rationale": "fixture", "confidence": "high"},
        }],
        "summary": {"applicable": 1, "blocked": 0, "unsupported": 0},
        "security_boundary": "fixture",
    }


def valid_outcome(index: int) -> dict[str, object]:
    sha = f"{index:x}" * 40
    return {
        "outcome_id": f"outcome-{index}",
        "repository_fingerprint": hashlib.sha256(f"repo-{index}".encode()).hexdigest(),
        "profile_ids": ["python-cli"],
        "recommendation_id": "INV-TESTS-EXECUTED-ON-PR",
        "capability_id": "tests_run_on_pull_requests",
        "pre_capability_state": "absent",
        "implementation_status": "applied",
        "post_capability_state": "operational",
        "validation": {"exact_head_sha": sha, "workflow_head_sha": sha, "workflow_conclusion": "success"},
    }


class CommandEvidenceTests(unittest.TestCase):
    def test_comments_and_inert_text_never_become_command_evidence(self):
        records = parse_run_block("# python -m unittest discover -s tests\necho no-tests-executed\n")
        self.assertEqual([item["status"] for item in records], ["comment", "inert"])
        self.assertFalse(any("test" in item["families"] for item in records))

    def test_inline_comment_and_redirection_preserve_real_invocation(self):
        records = parse_run_block('python -m unittest discover -s tests > "$RUNNER_TEMP/tests.log" 2>&1 # actual test')
        self.assertEqual(records[0]["status"], "resolved")
        self.assertEqual(records[0]["families"], ["test"])
        self.assertEqual(records[0]["argv"][:3], ["python", "-m", "unittest"])

    def test_control_flow_and_substitution_are_unsupported(self):
        for run in ("if true; then\n python -m pytest\nfi", "echo $(python -m pytest)", "bash -c 'python -m pytest'", "python -m pytest | tee log"):
            with self.subTest(run=run):
                records = parse_run_block(run)
                self.assertFalse(any(item["status"] == "resolved" and "test" in item["families"] for item in records))

    def test_package_script_working_directory_is_preserved(self):
        records = parse_run_block("npm test", working_directory="packages/api")
        self.assertEqual(records[0]["working_directory"], "packages/api")
        self.assertEqual(records[0]["families"], ["test"])

    def test_comment_only_workflow_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_files(root, {
                "tests/test_x.py": "import unittest\n",
                ".github/workflows/ci.yml": "on: [pull_request]\npermissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n          # python -m unittest discover -s tests\n          echo no-tests\n",
            })
            model = build_repository_model(root)
            self.assertNotEqual(capability(model, "tests_run_on_pull_requests")["state"], "operational")

    def test_real_test_workflow_is_operational(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_files(root, {
                "tests/test_x.py": "import unittest\n",
                ".github/workflows/ci.yml": "on: [pull_request]\npermissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m unittest discover -s tests\n",
            })
            model = build_repository_model(root)
            self.assertEqual(capability(model, "tests_run_on_pull_requests")["state"], "operational")


class PermissionModelTests(unittest.TestCase):
    def model(self, permission_yaml: str, job_permissions: str = "") -> dict[str, object]:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = f"on: [pull_request]\n{permission_yaml}jobs:\n  one:\n    runs-on: ubuntu-latest\n{job_permissions}    steps:\n      - run: echo ok\n"
            write_files(root, {".github/workflows/ci.yml": workflow})
            return build_repository_model(root)

    def test_missing_and_explicit_empty_are_distinct(self):
        missing = self.model("")
        empty = self.model("permissions: {}\n")
        self.assertEqual(capability(missing, "least_privilege_workflow_permissions")["state"], "unknown")
        self.assertEqual(capability(empty, "least_privilege_workflow_permissions")["state"], "operational")
        self.assertEqual(missing["workflows"][0]["permission_declaration"]["presence"], "missing")
        self.assertEqual(empty["workflows"][0]["permission_declaration"]["form"], "empty")

    def test_read_all_and_contents_read_are_operational(self):
        for declaration in ("permissions: read-all\n", "permissions:\n  contents: read\n"):
            with self.subTest(declaration=declaration):
                self.assertEqual(capability(self.model(declaration), "least_privilege_workflow_permissions")["state"], "operational")

    def test_workflow_write_all_can_be_narrowed_by_job(self):
        model = self.model("permissions: write-all\n", "    permissions:\n      contents: read\n")
        self.assertEqual(capability(model, "least_privilege_workflow_permissions")["state"], "operational")
        self.assertEqual(model["workflows"][0]["jobs"][0]["effective_permissions"]["source_scope"], "job")

    def test_job_write_override_is_weak_and_evidence_identifies_scope(self):
        model = self.model("permissions:\n  contents: read\n", "    permissions: write-all\n")
        item = capability(model, "least_privilege_workflow_permissions")
        self.assertEqual(item["state"], "operational_but_weak")
        self.assertIn("#jobs.one.permissions", item["evidence"]["references"][0])

    def test_mixed_jobs_and_malformed_values_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_files(root, {".github/workflows/ci.yml": "on: [pull_request]\npermissions:\n  contents: read\njobs:\n  safe:\n    runs-on: ubuntu-latest\n    steps: []\n  unsafe:\n    permissions:\n      contents: write\n    runs-on: ubuntu-latest\n    steps: []\n"})
            self.assertEqual(capability(build_repository_model(root), "least_privilege_workflow_permissions")["state"], "operational_but_weak")
        malformed = self.model("permissions:\n  contents: banana\n")
        self.assertEqual(capability(malformed, "least_privilege_workflow_permissions")["state"], "unknown")


class OutcomeTrustBoundaryTests(unittest.TestCase):
    def test_valid_registry_proposes_deterministically(self):
        registry = {"outcome_contract_version": "1.0.0", "outcomes": [valid_outcome(index) for index in range(1, 4)]}
        first = build_profile_evolution_proposals(registry)
        self.assertEqual(first, build_profile_evolution_proposals(copy.deepcopy(registry)))
        self.assertEqual(len(first["proposals"]), 1)

    def test_invalid_sha_forms_are_rejected_before_aggregation(self):
        values = [None, "a" * 39, "g" * 40, "A" * 40]
        for value in values:
            with self.subTest(value=value):
                item = valid_outcome(1)
                item["validation"]["exact_head_sha"] = value
                with self.assertRaises(UpgradeContractError) as raised:
                    validate_outcome_registry({"outcome_contract_version": "1.0.0", "outcomes": [item]})
                self.assertEqual(raised.exception.code, "OUTCOME_REGISTRY_SCHEMA_INVALID")

    def test_duplicate_and_conflicting_identity_are_rejected(self):
        item = valid_outcome(1)
        duplicate = copy.deepcopy(item)
        with self.assertRaises(UpgradeContractError) as raised:
            validate_outcome_registry({"outcome_contract_version": "1.0.0", "outcomes": [item, duplicate]})
        self.assertIn(raised.exception.code, {"OUTCOME_REGISTRY_SCHEMA_INVALID", "OUTCOME_ID_DUPLICATE"})
        conflict = copy.deepcopy(item)
        conflict["validation"]["workflow_conclusion"] = "failure"
        with self.assertRaises(UpgradeContractError) as raised:
            validate_outcome_registry({"outcome_contract_version": "1.0.0", "outcomes": [item, conflict]})
        self.assertEqual(raised.exception.code, "OUTCOME_ID_CONFLICT")

    def test_success_must_be_tied_to_exact_head(self):
        items = [valid_outcome(index) for index in range(1, 4)]
        items[0]["validation"]["workflow_head_sha"] = "f" * 40
        result = build_profile_evolution_proposals({"outcome_contract_version": "1.0.0", "outcomes": items})
        self.assertEqual(result["excluded_outcomes"][0]["reason"], "workflow_head_does_not_match_exact_head")
        self.assertEqual(result["proposals"], [])


class RecommendationQualityTests(unittest.TestCase):
    def model(self, state: str) -> dict[str, object]:
        return {"capabilities": [{"capability_id": "tests_run_on_pull_requests", "state": state, "evidence": {"references": [], "state": "unavailable", "rationale": "fixture"}}], "test_suites": {"files": []}, "workflows": [], "manifests": [], "lockfiles": [], "schemas": [], "examples": [], "validators": []}

    def test_correlation_only_and_generic_subsystems_do_not_reach_phase_1(self):
        history = {"revert_chains": [], "repeated_fix_subsystems": [{"subsystem": "tests", "fix_commit_count": 5}, {"subsystem": "src", "fix_commit_count": 4}], "diagnostics": []}
        result = generate_recommendations(self.model("absent"), history, {"recurring_failures": []}, {"selected_profiles": [], "expected_capabilities": [], "profile_conflicts": []}, mode=DEEP_REPOSITORY_UPGRADE, max_phase_1_items=5)
        observed = result["observed_failures"]
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]["decision"], "deferred")
        self.assertFalse(observed[0]["phase_1_eligible"])

    def test_operational_capability_suppresses_generic_duplicate_control(self):
        history = {"revert_chains": [], "repeated_fix_subsystems": [{"subsystem": "src", "fix_commit_count": 4}], "diagnostics": []}
        result = generate_recommendations(self.model("operational"), history, {"recurring_failures": []}, {"selected_profiles": [], "expected_capabilities": [], "profile_conflicts": []}, mode=DEEP_REPOSITORY_UPGRADE, max_phase_1_items=5)
        self.assertFalse(any(item["recommendation_id"].startswith("OBS-REPEATED-FIX") for item in result["ranked"]))

    def test_behavior_specific_missing_oracle_can_be_eligible(self):
        history = {"revert_chains": [], "repeated_fix_subsystems": [{"subsystem": "src", "fix_commit_count": 4, "affected_paths": ["src/parser.py"], "failure_mode": "Malformed input was accepted.", "missing_assertion": "Reject malformed input.", "existing_control_limitation": "Current PR test covers only valid input.", "validation_plan": ["Add invalid fixture.", "Assert stable rejection."]}], "diagnostics": []}
        result = generate_recommendations(self.model("absent"), history, {"recurring_failures": []}, {"selected_profiles": [], "expected_capabilities": [], "profile_conflicts": []}, mode=DEEP_REPOSITORY_UPGRADE, max_phase_1_items=5)
        item = next(value for value in result["ranked"] if value["recommendation_id"].startswith("OBS-REPEATED-FIX"))
        self.assertTrue(item["phase_1_eligible"])
        self.assertNotEqual(item["decision"], "deferred")


@unittest.skipUnless(shutil.which("git"), "git required")
class RecoverableMutationTests(unittest.TestCase):
    def run_failure(self, checkpoint: str, *, rollback_failure: bool = False) -> tuple[Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        repo = base / "repo"
        repo.mkdir()
        write_files(repo, {"README.md": "fixture\n"})
        head = init_git(repo)
        output = base / "evidence"
        package = package_for()
        def inject(current: str) -> None:
            if rollback_failure and current == "during_report_write":
                raise OSError("injected persistence failure")
            if rollback_failure and current == "during_rollback":
                raise OSError("injected rollback failure")
            if not rollback_failure and current == checkpoint:
                raise OSError(f"injected {checkpoint}")
        with self.assertRaises(UpgradeContractError):
            execute_recoverable_implementation(repo, {"report": "fixture"}, package, allowed_recipe_ids={"test-recipe"}, expected_head_sha=head, report_out=output / "report.json", package_out=output / "package.json", result_out=output / "result.json", journal_out=output / "journal.json", failure_injector=inject)
        return repo, output, output / "journal.json"

    def test_failures_before_and_after_each_boundary_roll_back(self):
        for checkpoint in ("before_mutation", "before_target_creation", "after_target_creation", "during_report_write", "during_package_write", "during_result_write"):
            with self.subTest(checkpoint=checkpoint):
                repo, output, journal = self.run_failure(checkpoint)
                self.assertFalse((repo / ".github/workflows/generated.yml").exists())
                self.assertTrue(journal.exists())
                data = json.loads(journal.read_text())
                self.assertEqual(data["status"], "rolled_back")
                self.assertFalse((output / "report.json").exists())
                self.assertFalse((output / "package.json").exists())
                self.assertFalse((output / "result.json").exists())

    def test_rollback_failure_leaves_recovery_required_record(self):
        repo, _, journal = self.run_failure("during_report_write", rollback_failure=True)
        self.assertTrue((repo / ".github/workflows/generated.yml").exists())
        self.assertEqual(json.loads(journal.read_text())["status"], "recovery_required")

    def test_success_persists_all_outputs_and_valid_journal(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            repo.mkdir()
            write_files(repo, {"README.md": "fixture\n"})
            head = init_git(repo)
            output = base / "evidence"
            result = execute_recoverable_implementation(repo, {"report": "fixture"}, package_for(), allowed_recipe_ids={"test-recipe"}, expected_head_sha=head, report_out=output / "report.json", package_out=output / "package.json", result_out=output / "result.json", journal_out=output / "journal.json")
            self.assertEqual(result["transaction_status"], "committed")
            for name in ("report.json", "package.json", "result.json", "journal.json"):
                self.assertTrue((output / name).is_file())
            schema = json.loads((ROOT / "schemas/implementation_recovery_journal.v1.schema.json").read_text())
            Draft7Validator(schema).validate(json.loads((output / "journal.json").read_text()))

    def test_path_guards_and_exact_head_are_strict(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            write_files(repo, {"README.md": "fixture\n"})
            head = init_git(repo)
            with self.assertRaises(UpgradeContractError) as raised:
                apply_implementation_package(repo, package_for("../escape"), allowed_recipe_ids={"test-recipe"}, expected_head_sha=head)
            self.assertIn(raised.exception.code, {"IMPLEMENTATION_PATH_INVALID", "IMPLEMENTATION_PATH_ESCAPE"})
            with self.assertRaises(UpgradeContractError) as raised:
                apply_implementation_package(repo, package_for(), allowed_recipe_ids={"test-recipe"}, expected_head_sha=head.upper())
            self.assertEqual(raised.exception.code, "IMPLEMENTATION_EXPECTED_HEAD_INVALID")
            (repo / "dirty.txt").write_text("dirty")
            with self.assertRaises(UpgradeContractError) as raised:
                apply_implementation_package(repo, package_for(), allowed_recipe_ids={"test-recipe"}, expected_head_sha=head)
            self.assertEqual(raised.exception.code, "IMPLEMENTATION_WORKTREE_DIRTY")


class WorkflowSummaryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_summary_renders_literal_exact_shas_without_stderr(self):
        with tempfile.TemporaryDirectory() as td:
            summary = Path(td) / "summary.md"
            identity = Path(td) / "identity.json"
            env = os.environ.copy()
            env.update({"GITHUB_STEP_SUMMARY": str(summary), "TESTED_SHA": "a" * 40, "SOURCE_HEAD_SHA": "b" * 40, "RUN_IDENTITY_OUT": str(identity)})
            result = subprocess.run(["bash", str(ROOT / "tools/render_workflow_summary.sh")], text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            text = summary.read_text()
            self.assertIn(f"`{'a' * 40}`", text)
            self.assertIn(f"`{'b' * 40}`", text)
            self.assertEqual(json.loads(identity.read_text()), {"source_head_sha": "b" * 40, "tested_sha": "a" * 40})

    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_summary_fails_when_sha_is_missing(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env.update({"GITHUB_STEP_SUMMARY": str(Path(td) / "summary.md"), "TESTED_SHA": "a" * 40})
            env.pop("SOURCE_HEAD_SHA", None)
            result = subprocess.run(["bash", str(ROOT / "tools/render_workflow_summary.sh")], text=True, capture_output=True, env=env)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
