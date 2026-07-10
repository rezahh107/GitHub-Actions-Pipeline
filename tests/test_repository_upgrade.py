import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.repository_upgrade import build_upgrade_report, report_sha256
from tools.repository_model import build_repository_model

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-07-10T00:00:00Z"


class RepositoryUpgradeTests(unittest.TestCase):
    def make_python_repo(self, root: Path, *, workflow: bool = False, lock: bool = False):
        (root / "src" / "demo").mkdir(parents=True, exist_ok=True)
        (root / "src" / "demo" / "__init__.py").write_text('__version__ = "0.1.0"\n')
        (root / "tests").mkdir(exist_ok=True)
        (root / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n")
        (root / "pyproject.toml").write_text(
            "[project]\nname='demo'\nversion='0.1.0'\ndependencies=['fastapi']\n"
            "\n[tool.pytest.ini_options]\ntestpaths=['tests']\n",
            encoding="utf-8",
        )
        (root / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        if lock:
            (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
        if workflow:
            path = root / ".github" / "workflows"
            path.mkdir(parents=True)
            (path / "validate.yml").write_text(
                "name: Validate\n"
                "on:\n"
                "  pull_request:\n"
                "permissions:\n"
                "  contents: read\n"
                "jobs:\n"
                "  test:\n"
                "    runs-on: ubuntu-24.04\n"
                "    steps:\n"
                "      - run: python -m pytest\n",
                encoding="utf-8",
            )

    def test_component_and_framework_detection_is_manifest_aware(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_python_repo(repo)
            model = build_repository_model(repo)
            self.assertIn("python-api-service", model["archetypes"])
            self.assertEqual(len(model["components"]), 1)
            component = model["components"][0]
            self.assertIn("fastapi", component["frameworks"])
            self.assertIn("python -m pytest", component["test_commands"])

    def test_tests_are_nominal_until_executed_on_pull_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_python_repo(repo, workflow=False)
            report = build_upgrade_report(
                repo,
                mode="deep-repository-upgrade",
                generated_at=FIXED_TIME,
                profile_root=ROOT / "profiles",
            )
            by_id = {item["capability_id"]: item for item in report["capability_gaps"]}
            self.assertEqual(by_id["tests_on_pull_request"]["state"], "nominal")

            self.make_python_repo(repo, workflow=True)
            report = build_upgrade_report(
                repo,
                mode="deep-repository-upgrade",
                generated_at=FIXED_TIME,
                profile_root=ROOT / "profiles",
            )
            by_id = {item["capability_id"]: item for item in report["capability_gaps"]}
            self.assertEqual(by_id["tests_on_pull_request"]["state"], "operational")

    def test_deep_mode_solves_cold_start_with_baseline_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_python_repo(repo)
            report = build_upgrade_report(
                repo,
                mode="deep-repository-upgrade",
                generated_at=FIXED_TIME,
                profile_root=ROOT / "profiles",
            )
            sources = {item["source"] for item in report["recommendations"]}
            self.assertIn("baseline_capability", sources)
            ids = {item.get("capability_id") for item in report["recommendations"]}
            self.assertIn("tests_on_pull_request", ids)
            self.assertTrue(report["staged_upgrade_plan"]["phase_1"])

    def test_minimal_mode_does_not_emit_baseline_only_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_python_repo(repo)
            report = build_upgrade_report(
                repo,
                mode="minimal-safe-ci",
                generated_at=FIXED_TIME,
                profile_root=ROOT / "profiles",
            )
            self.assertNotIn(
                "baseline_capability",
                {item["source"] for item in report["recommendations"]},
            )
            self.assertEqual(report["staged_upgrade_plan"]["phase_2"], [])

    def test_monorepo_components_are_separated(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            backend = repo / "backend"
            frontend = repo / "frontend"
            backend.mkdir()
            frontend.mkdir()
            (backend / "pyproject.toml").write_text("[project]\nname='api'\nversion='1.0.0'\n")
            (backend / "app.py").write_text("print('api')\n")
            (frontend / "package.json").write_text(
                json.dumps({"name": "ui", "scripts": {"build": "vite build"}, "dependencies": {"react": "1"}})
            )
            (frontend / "package-lock.json").write_text("{}\n")
            model = build_repository_model(repo)
            roots = {item["root"] for item in model["components"]}
            self.assertEqual(roots, {"backend", "frontend"})

    def test_output_is_deterministic_with_fixed_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_python_repo(repo, workflow=True, lock=True)
            first = build_upgrade_report(
                repo,
                mode="deep-repository-upgrade",
                generated_at=FIXED_TIME,
                profile_root=ROOT / "profiles",
            )
            second = build_upgrade_report(
                repo,
                mode="deep-repository-upgrade",
                generated_at=FIXED_TIME,
                profile_root=ROOT / "profiles",
            )
            self.assertEqual(first, second)
            self.assertEqual(first["report_sha256"], report_sha256(first))

    def test_deep_history_detects_source_changes_without_tests(self):
        if shutil.which("git") is None:
            self.skipTest("git unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            self.make_python_repo(repo)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
            for index in range(2):
                (repo / "src" / "demo" / f"module{index}.py").write_text(f"value={index}\n")
                subprocess.run(["git", "add", "."], cwd=repo, check=True)
                subprocess.run(["git", "commit", "-m", f"refactor module {index}"], cwd=repo, check=True, capture_output=True)
            report = build_upgrade_report(
                repo,
                mode="deep-repository-upgrade",
                generated_at=FIXED_TIME,
                profile_root=ROOT / "profiles",
            )
            self.assertGreaterEqual(
                len(report["historical_analysis"]["production_changes_without_tests"]), 2
            )
            self.assertTrue(any(
                item["source"] == "observed_failure"
                for item in report["recommendations"]
            ))


if __name__ == "__main__":
    unittest.main()
