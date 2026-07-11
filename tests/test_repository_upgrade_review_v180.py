import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from tools.ci_command_evidence import parse_run_block
from tools.ci_history_analysis import collect_structural_history
from tools.ci_profiles import detect_profiles, load_profiles, profile_candidate_diagnostics
from tools.ci_repository_model import build_repository_model
from tools.ci_upgrade_engine import build_upgrade_report
from tools.ci_upgrade_models import DEEP_REPOSITORY_UPGRADE, MINIMAL_SAFE_CI


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def capability(model: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(item for item in model["capabilities"] if item["capability_id"] == capability_id)


class RepositoryContainmentTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_symlink_files_and_symlinked_parents_are_excluded_without_external_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            external = base / "external"
            repo = base / "repo"
            external.mkdir()
            repo.mkdir()
            marker = "EXTERNAL_MARKER_DO_NOT_SERIALIZE"
            write_files(external, {"pyproject.toml": f"[project]\nname='{marker}'\nversion='0.1'\n", "tests/test_escape.py": f"VALUE = '{marker}'\n"})
            os.symlink(external / "pyproject.toml", repo / "pyproject.toml")
            os.symlink(external, repo / "linked-parent")
            write_files(repo, {"README.md": "safe\n"})
            for mode in (MINIMAL_SAFE_CI, DEEP_REPOSITORY_UPGRADE):
                with self.subTest(mode=mode):
                    report = build_upgrade_report(repo, mode=mode, generated_at="2026-07-10T00:00:00Z")
                    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
                    self.assertNotIn(marker, serialized)
                    self.assertNotIn("pyproject.toml", report["repository_model"]["manifests"])
                    codes = {item["code"] for item in report["repository_model"]["unresolved_evidence"]}
                    self.assertIn("REPOSITORY_PATH_SYMLINK_REJECTED", codes)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_workspace_parent_absolute_and_symlink_matches_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            external = base / "outside-package"
            repo = base / "repo"
            external.mkdir()
            repo.mkdir()
            marker = "WORKSPACE_EXTERNAL_MARKER"
            write_files(external, {"package.json": json.dumps({"name": marker})})
            (repo / "packages").mkdir()
            os.symlink(external, repo / "packages" / "linked")
            write_files(repo, {"package.json": json.dumps({"name": "root", "workspaces": ["../*", str(external), "packages/*"]})})
            model = build_repository_model(repo)
            serialized = json.dumps(model, ensure_ascii=False, sort_keys=True)
            self.assertNotIn(marker, serialized)
            codes = {item["code"] for item in model["unresolved_evidence"]}
            self.assertIn("WORKSPACE_PATTERN_REJECTED", codes)
            self.assertTrue({"WORKSPACE_PATH_REJECTED", "REPOSITORY_PATH_SYMLINK_REJECTED"} & codes)
            self.assertFalse(any(component["root"].startswith("..") for component in model["components"]))


class OperationalCommandEvidenceTests(unittest.TestCase):
    def test_help_collect_only_list_dry_run_and_no_run_are_not_behavioral_tests(self):
        commands = ("pytest --help", "pytest --collect-only", "python -m pytest --co", "python -m unittest --help", "cargo test --no-run", "cargo test -- --list", "go test -list . ./...", "mvn test -DskipTests", "./gradlew test --dry-run", "npm test -- --help")
        for command in commands:
            with self.subTest(command=command):
                records = parse_run_block(command)
                self.assertFalse(any(item.get("status") == "resolved" and "test" in item.get("families", []) for item in records))
                self.assertTrue(any(item.get("status") == "inert" for item in records))

    def test_zero_test_repository_and_missing_runs_on_do_not_become_operational(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_files(root, {".github/workflows/no-target.yml": "on: [pull_request]\npermissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n", ".github/workflows/not-runnable.yml": "on: [pull_request]\npermissions: {}\njobs:\n  test:\n    steps:\n      - run: python -m unittest discover -s tests\n"})
            model = build_repository_model(root)
            self.assertNotEqual(capability(model, "tests_run_on_pull_requests")["state"], "operational")
            codes = {item["code"] for item in model["unresolved_evidence"]}
            self.assertIn("WORKFLOW_JOB_NOT_RUNNABLE", codes)
            self.assertIn("WORKFLOW_TEST_TARGET_UNRESOLVED", codes)

    def test_reusable_job_is_unresolved_but_malformed_sibling_invalidates_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_files(root, {"tests/test_x.py": "def test_x(): assert True\n", ".github/workflows/ci.yml": """on: [pull_request]
permissions: {}
jobs:
  reusable:
    uses: owner/repo/.github/workflows/tests.yml@0123456789012345678901234567890123456789
  malformed:
    runs-on: 7
    steps:
      - run: pytest
  valid:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/test_x.py
"""})
            model = build_repository_model(root)
            self.assertNotEqual(
                capability(model, "tests_run_on_pull_requests")["state"],
                "operational",
            )
            workflow = model["workflows"][0]
            self.assertEqual(workflow["parse_status"], "invalid_shape")
            self.assertEqual(workflow["jobs"], [])
            self.assertEqual(workflow["commands"], [])
            self.assertEqual(workflow["command_evidence"], [])
            codes = {item["code"] for item in model["unresolved_evidence"]}
            self.assertIn("WORKFLOW_RUNS_ON_STRUCTURE_INVALID", codes)
            self.assertEqual(model["test_suites"]["commands_observed_in_ci"], [])

    def test_supported_behavioral_controls_remain_operational(self):
        cases = (("pytest tests/test_x.py", "tests/test_x.py"), ("python -m unittest discover -s tests", "tests/test_x.py"), ("npm test", "tests/app.test.js"), ("cargo test", "tests/core.rs"), ("go test ./...", "pkg/core_test.go"), ("mvn test", "src/test/java/AppTest.java"), ("./gradlew test", "src/test/java/AppTest.java"))
        for command, test_path in cases:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                write_files(root, {test_path: "fixture\n", ".github/workflows/ci.yml": f"on: [pull_request]\npermissions: {{}}\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: {command}\n"})
                self.assertEqual(capability(build_repository_model(root), "tests_run_on_pull_requests")["state"], "operational")


class ProfileAuthorityTests(unittest.TestCase):
    def selected(self, root: Path) -> tuple[set[str], list[dict[str, object]]]:
        model = build_repository_model(root)
        catalog = load_profiles()
        matches = detect_profiles(model, catalog)
        return {item["profile_id"] for item in matches}, profile_candidate_diagnostics(model, catalog, matches)

    def test_docs_only_pipeline_and_filename_only_adapter_are_candidates_not_profiles(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_files(root, {"pipeline/guide.md": "documentation only\n", "docs/integration-adapter-review.md": "not an adapter implementation\n"})
            selected, diagnostics = self.selected(root)
            self.assertNotIn("python-data-pipeline", selected)
            self.assertNotIn("multi-repository-adapter", selected)
            candidate_messages = "\n".join(item["message"] for item in diagnostics)
            self.assertIn("python-data-pipeline", candidate_messages)
            self.assertIn("multi-repository-adapter", candidate_messages)

    def test_python_pipeline_and_manifest_backed_adapter_have_authoritative_support(self):
        with tempfile.TemporaryDirectory() as td:
            pipeline = Path(td) / "pipeline-repo"
            pipeline.mkdir()
            write_files(pipeline, {"pyproject.toml": "[project]\nname='etl'\nversion='0.1'\n", "pipeline/transform.py": "def transform(value): return value\n"})
            selected, _ = self.selected(pipeline)
            self.assertIn("python-data-pipeline", selected)
            adapter = Path(td) / "adapter-repo"
            adapter.mkdir()
            write_files(adapter, {"pyproject.toml": "[project]\nname='adapter'\nversion='0.1'\n", "adapters/github.py": "def adapt(value): return value\n"})
            selected, _ = self.selected(adapter)
            self.assertIn("multi-repository-adapter", selected)


@unittest.skipUnless(shutil.which("git"), "git required")
class StructuralHistoryFramingTests(unittest.TestCase):
    def test_untrusted_filenames_cannot_collide_with_commit_framing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
            filenames = ["@@@evil.py", "tab\tname.py", "space name.py", "یونیکد.py"]
            for name in filenames:
                (root / name).write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "fix adversarial paths"], cwd=root, check=True)
            first = collect_structural_history(root)
            second = collect_structural_history(root)
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "collected")
            self.assertEqual(first["commit_count_analyzed"], 1)
            self.assertEqual(first["production_without_test_changes"][0]["paths"], sorted(filenames))
            self.assertEqual(first["diagnostics"], [])


class ExactSourceHeadIdentityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_exact_mode_requires_equal_identity_and_writes_structured_record(self):
        with tempfile.TemporaryDirectory() as td:
            summary = Path(td) / "summary.md"
            identity = Path(td) / "identity.json"
            env = os.environ.copy()
            env.update({"GITHUB_STEP_SUMMARY": str(summary), "TESTED_SHA": "a" * 40, "SOURCE_HEAD_SHA": "a" * 40, "EVENT_SHA": "b" * 40, "EXACT_SOURCE_HEAD_REQUIRED": "1", "RUN_IDENTITY_OUT": str(identity)})
            result = subprocess.run(["bash", str(ROOT / "tools/render_workflow_summary.sh")], capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(identity.read_text(encoding="utf-8"))
            self.assertTrue(data["exact_source_head_verified"])
            self.assertEqual(data["tested_sha"], data["source_head_sha"])
            self.assertEqual(data["event_sha"], "b" * 40)
            self.assertIn(f"`{'a' * 40}`", summary.read_text(encoding="utf-8"))
            env["TESTED_SHA"] = "d" * 40
            failed = subprocess.run(["bash", str(ROOT / "tools/render_workflow_summary.sh")], capture_output=True, text=True, env=env)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("requires TESTED_SHA to equal SOURCE_HEAD_SHA", failed.stderr)


if __name__ == "__main__":
    unittest.main()
