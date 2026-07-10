import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-07-10T00:00:00Z"

from tools.ci_history_analysis import collect_structural_history
from tools.ci_profiles import compose_profile_contributions, detect_profiles, load_profiles
from tools.ci_recommendations import generate_recommendations
from tools.ci_repository_model import build_repository_model
from tools.ci_telemetry import collect_github_telemetry, unavailable_telemetry
from tools.ci_upgrade_engine import build_upgrade_report, compute_upgrade_sha256
from tools.ci_upgrade_models import (
    DEEP_REPOSITORY_UPGRADE,
    MINIMAL_SAFE_CI,
    UpgradeContractError,
    ranking_total,
)


def load_scenarios():
    data = json.loads(
        (ROOT / "fixtures" / "repository-upgrade" / "scenarios.v1.json").read_text(
            encoding="utf-8"
        )
    )
    return {item["scenario_id"]: item for item in data["scenarios"]}


def materialize(root: Path, scenario_id: str) -> None:
    scenario = load_scenarios()[scenario_id]
    for relative, content in scenario["files"].items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class RepositoryUpgradeTests(unittest.TestCase):
    def test_modes_are_explicit_and_output_contracts_are_separate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            materialize(repo, "cold-start-python-cli")

            minimal = build_upgrade_report(
                repo,
                mode=MINIMAL_SAFE_CI,
                generated_at=FIXED_TIME,
            )
            deep = build_upgrade_report(
                repo,
                mode=DEEP_REPOSITORY_UPGRADE,
                generated_at=FIXED_TIME,
            )

            self.assertEqual(minimal["operating_mode"], MINIMAL_SAFE_CI)
            self.assertIn("minimal_gate_plan", minimal)
            self.assertNotIn("deep_audit", minimal)
            self.assertFalse(minimal["mode_policy"]["collect_history_structure"])

            self.assertEqual(deep["operating_mode"], DEEP_REPOSITORY_UPGRADE)
            self.assertIn("deep_audit", deep)
            self.assertIn("staged_upgrade", deep)
            self.assertNotIn("minimal_gate_plan", deep)
            self.assertTrue(deep["mode_policy"]["collect_history_structure"])

    def test_cold_start_keeps_structural_and_baseline_channels_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            materialize(repo, "cold-start-python-cli")
            report = build_upgrade_report(
                repo,
                mode=DEEP_REPOSITORY_UPGRADE,
                generated_at=FIXED_TIME,
            )

            self.assertEqual(report["cold_start"]["status"], "limited_history")
            self.assertTrue(
                report["cold_start"]["not_yet_observed_is_not_not_needed"]
            )
            self.assertEqual(
                report["recommendations"]["observed_failures"], []
            )
            self.assertTrue(report["recommendations"]["structural_invariants"])
            self.assertTrue(report["recommendations"]["baseline_capabilities"])

    def test_repository_model_distinguishes_nominal_from_operational(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nominal = root / "nominal"
            operational = root / "operational"
            nominal.mkdir()
            operational.mkdir()
            materialize(nominal, "cold-start-python-cli")
            materialize(operational, "operational-python-package")

            nominal_model = build_repository_model(nominal)
            operational_model = build_repository_model(operational)
            nominal_states = {
                item["capability_id"]: item["state"]
                for item in nominal_model["capabilities"]
            }
            operational_states = {
                item["capability_id"]: item["state"]
                for item in operational_model["capabilities"]
            }

            self.assertNotEqual(
                nominal_states["tests_run_on_pull_requests"], "operational"
            )
            self.assertEqual(
                operational_states["tests_run_on_pull_requests"], "operational"
            )
            self.assertEqual(
                operational_states["build_verified"], "operational"
            )
            self.assertEqual(
                operational_states["reproducible_dependency_install"],
                "operational",
            )

    def test_composable_profiles_match_multiple_repository_characteristics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            materialize(repo, "cold-start-python-cli")
            model = build_repository_model(repo)
            catalog = load_profiles()
            matches = detect_profiles(model, catalog)
            composition = compose_profile_contributions(matches, catalog)

            self.assertIn("python-library-package", composition["selected_profiles"])
            self.assertIn("python-cli", composition["selected_profiles"])
            self.assertIn(
                "tests_run_on_pull_requests",
                composition["expected_capabilities"],
            )

    def test_contract_repository_gets_schema_invariant_without_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            materialize(repo, "contract-repository")
            report = build_upgrade_report(
                repo,
                mode=DEEP_REPOSITORY_UPGRADE,
                generated_at=FIXED_TIME,
            )
            ids = {
                item["recommendation_id"]
                for item in report["recommendations"]["structural_invariants"]
            }
            self.assertIn("INV-SCHEMA-PRODUCER-COMPATIBILITY", ids)

    def test_ranking_is_bounded_deterministic_and_rejects_missing_factors(self):
        factors = {
            "risk_reduction": 3,
            "invariant_criticality": 3,
            "regression_detection": 2,
            "silent_failure_exposure": 2,
            "evidence_strength": 3,
            "maintainability": 2,
            "reversibility": 3,
            "implementation_complexity": 1,
            "execution_time": 1,
            "noise_risk": 1,
            "maintenance_cost": 1,
            "control_overlap": 0,
        }
        self.assertEqual(ranking_total(factors), ranking_total(dict(reversed(list(factors.items())))))
        with self.assertRaises(UpgradeContractError) as raised:
            ranking_total({"risk_reduction": 3})
        self.assertEqual(raised.exception.code, "INVALID_RANKING_FACTORS")

    def test_unavailable_telemetry_is_explicit_and_actionable(self):
        telemetry = unavailable_telemetry()
        self.assertEqual(telemetry["status"], "unavailable")
        self.assertEqual(telemetry["runs"], [])
        self.assertTrue(telemetry["diagnostics"][0]["repair_hint"])

    def test_fake_github_telemetry_detects_recurring_failures(self):
        def transport(url, headers):
            self.assertIn("/actions/runs", url)
            self.assertEqual(headers["X-GitHub-Api-Version"], "2022-11-28")
            return {
                "workflow_runs": [
                    {
                        "id": 2,
                        "name": "Validate",
                        "event": "pull_request",
                        "status": "completed",
                        "conclusion": "failure",
                        "head_sha": "a" * 40,
                        "head_branch": "feature",
                        "created_at": "2026-07-10T00:00:00Z",
                        "updated_at": "2026-07-10T00:02:00Z",
                    },
                    {
                        "id": 1,
                        "name": "Validate",
                        "event": "pull_request",
                        "status": "completed",
                        "conclusion": "failure",
                        "head_sha": "b" * 40,
                        "head_branch": "feature",
                        "created_at": "2026-07-09T00:00:00Z",
                        "updated_at": "2026-07-09T00:01:00Z",
                    },
                ]
            }

        telemetry = collect_github_telemetry(
            "owner/repo", token="test-token", transport=transport
        )
        self.assertEqual(telemetry["status"], "collected")
        self.assertEqual(
            telemetry["recurring_failures"],
            [{"workflow": "Validate", "failure_count": 2}],
        )
        self.assertEqual(telemetry["average_duration_seconds"], 90)

    def test_reports_are_deterministic_with_fixed_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            materialize(repo, "cold-start-python-cli")
            first = build_upgrade_report(
                repo,
                mode=DEEP_REPOSITORY_UPGRADE,
                generated_at=FIXED_TIME,
            )
            second = build_upgrade_report(
                repo,
                mode=DEEP_REPOSITORY_UPGRADE,
                generated_at=FIXED_TIME,
            )
            self.assertEqual(first, second)
            self.assertEqual(
                first["evidence_sha256"], compute_upgrade_sha256(first)
            )

    def test_diagnostics_are_repair_oriented(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            materialize(repo, "cold-start-python-cli")
            report = build_upgrade_report(
                repo,
                mode=DEEP_REPOSITORY_UPGRADE,
                generated_at=FIXED_TIME,
            )
            for item in report["diagnostics"]:
                self.assertTrue(item["message"])
                self.assertTrue(item["affected_area"])
                self.assertTrue(item["repair_hint"])

    def test_invalid_mode_is_rejected_with_stable_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            with self.assertRaises(UpgradeContractError) as raised:
                build_upgrade_report(
                    repo,
                    mode="unknown",
                    generated_at=FIXED_TIME,
                )
            self.assertEqual(raised.exception.code, "INVALID_OPERATING_MODE")

    @unittest.skipUnless(shutil.which("git"), "git is required for structural history validation")
    def test_structural_history_detects_reverts_cochange_and_repeated_fixes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)

            def commit(subject, source, config):
                (repo / "src").mkdir(exist_ok=True)
                (repo / "src" / "parser.py").write_text(source, encoding="utf-8")
                (repo / "pipeline.yml").write_text(config, encoding="utf-8")
                subprocess.run(["git", "add", "."], cwd=repo, check=True)
                subprocess.run(["git", "commit", "-q", "-m", subject], cwd=repo, check=True)

            commit("initial parser", "VALUE = 1\n", "version: 1\n")
            commit("fix parser boundary", "VALUE = 2\n", "version: 2\n")
            commit("fix parser diagnostics", "VALUE = 3\n", "version: 3\n")
            commit('Revert "fix parser diagnostics"', "VALUE = 2\n", "version: 2\n")

            history = collect_structural_history(repo)
            self.assertEqual(history["status"], "collected")
            self.assertTrue(history["revert_chains"])
            self.assertTrue(history["co_change_pairs"])
            self.assertTrue(history["production_without_test_changes"])
            self.assertIn("src", {item["subsystem"] for item in history["repeated_fix_subsystems"]})

    def test_operational_capability_does_not_generate_duplicate_gap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            materialize(repo, "operational-python-package")
            report = build_upgrade_report(
                repo,
                mode=DEEP_REPOSITORY_UPGRADE,
                generated_at=FIXED_TIME,
            )
            test_gap_ids = {
                item["recommendation_id"]
                for item in report["recommendations"]["ranked"]
                if item["affected_capability"] == "tests_run_on_pull_requests"
            }
            self.assertNotIn("INV-TESTS-EXECUTED-ON-PR", test_gap_ids)
            self.assertNotIn("BASE-TESTS-RUN-ON-PULL-REQUESTS", test_gap_ids)


if __name__ == "__main__":
    unittest.main()
