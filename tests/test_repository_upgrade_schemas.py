import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-07-10T00:00:00Z"

from tools.ci_upgrade_engine import build_upgrade_report, compute_upgrade_sha256
from tools.ci_upgrade_models import DEEP_REPOSITORY_UPGRADE, MINIMAL_SAFE_CI


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def materialize(root: Path):
    (root / "pyproject.toml").write_text("[project]\nname='schema-test'\nversion='0.1.0'\n[build-system]\nbuild-backend='setuptools.build_meta'\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests/test_sample.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_invalid(self):\n  with self.assertRaises(ValueError): raise ValueError('invalid')\n", encoding="utf-8")


class RepositoryUpgradeSchemaTests(unittest.TestCase):
    def setUp(self):
        self.legacy_schema = load_json(ROOT / "schemas/repository_upgrade_report.v1.schema.json")
        self.report_schema = load_json(ROOT / "schemas/repository_upgrade_report.v1.1.schema.json")
        self.profile_schema = load_json(ROOT / "schemas/capability_profiles.v1.schema.json")
        self.outcome_schema = load_json(ROOT / "schemas/repository_outcomes.v1.schema.json")
        self.recovery_schema = load_json(ROOT / "schemas/implementation_recovery_journal.v1.schema.json")
        for schema in (self.legacy_schema, self.report_schema, self.profile_schema, self.outcome_schema, self.recovery_schema):
            Draft7Validator.check_schema(schema)

    def reports(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name)
        materialize(repo)
        return (
            build_upgrade_report(repo, mode=MINIMAL_SAFE_CI, generated_at=FIXED_TIME),
            build_upgrade_report(repo, mode=DEEP_REPOSITORY_UPGRADE, generated_at=FIXED_TIME),
        )

    def test_profile_catalog_validates(self):
        Draft7Validator(self.profile_schema).validate(load_json(ROOT / "profiles/capability-profiles.v1.json"))

    def test_legacy_static_examples_remain_valid_and_hash_match(self):
        for name in ("repository_upgrade_report.minimal.example.json", "repository_upgrade_report.deep.example.json"):
            with self.subTest(name=name):
                instance = load_json(ROOT / "examples" / name)
                Draft7Validator(self.legacy_schema).validate(instance)
                self.assertEqual(instance["evidence_sha256"], compute_upgrade_sha256(instance))

    def test_generated_v1_1_minimal_and_deep_reports_validate(self):
        for report in self.reports():
            Draft7Validator(self.report_schema).validate(report)

    def test_mode_specific_contracts_are_enforced(self):
        minimal, deep = self.reports()
        broken = copy.deepcopy(minimal)
        broken["deep_audit"] = {}
        with self.assertRaises(ValidationError):
            Draft7Validator(self.report_schema).validate(broken)
        for field in ("staged_upgrade", "implementation_package", "deep_audit"):
            broken = copy.deepcopy(deep)
            broken.pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Draft7Validator(self.report_schema).validate(broken)

    def test_major_contract_objects_reject_unknown_fields(self):
        _, deep = self.reports()
        paths = [
            ("mode_policy",),
            ("repository_model",),
            ("repository_model", "semantic_model"),
            ("profiles",),
            ("profiles", "composition"),
            ("history_analysis",),
            ("workflow_telemetry",),
            ("cold_start",),
            ("recommendations",),
            ("recommendations", "ranked", 0),
            ("recommendations", "ranked", 0, "oracle_gap"),
            ("deep_audit",),
            ("staged_upgrade",),
            ("implementation_package",),
            ("implementation_package", "actions", 0),
        ]
        for path in paths:
            broken = copy.deepcopy(deep)
            mutation = broken
            for part in path:
                mutation = mutation[part]
            mutation["unexpected"] = True
            with self.subTest(path=path), self.assertRaises(ValidationError):
                Draft7Validator(self.report_schema).validate(broken)

    def test_major_contract_objects_reject_missing_required_fields(self):
        _, deep = self.reports()
        mutations = [
            (("mode_policy",), "recommendation_scope"),
            (("repository_model",), "model_version"),
            (("repository_model", "semantic_model"), "nodes"),
            (("profiles", "composition"), "selected_profiles"),
            (("history_analysis",), "status"),
            (("workflow_telemetry",), "runs"),
            (("cold_start",), "status"),
            (("recommendations",), "ranked"),
            (("recommendations", "ranked", 0), "oracle_gap"),
            (("deep_audit",), "executable_architecture"),
            (("staged_upgrade",), "phase_1"),
            (("implementation_package",), "actions"),
            (("implementation_package", "actions", 0), "preconditions"),
        ]
        for path, field in mutations:
            broken = copy.deepcopy(deep)
            target = broken
            for part in path:
                target = target[part]
            target.pop(field)
            with self.subTest(path=path, field=field), self.assertRaises(ValidationError):
                Draft7Validator(self.report_schema).validate(broken)

    def test_invalid_enum_sha_duplicate_and_malformed_nested_data_are_rejected(self):
        _, deep = self.reports()
        mutations = []
        item = copy.deepcopy(deep); item["repository_model"]["capabilities"][0]["state"] = "maybe"; mutations.append(item)
        item = copy.deepcopy(deep); item["analysis_basis_sha256"] = "not-a-sha"; mutations.append(item)
        item = copy.deepcopy(deep); item["repository_model"]["path_index"] = ["x", "x"]; mutations.append(item)
        item = copy.deepcopy(deep); item["recommendations"]["ranked"][0]["decision"] = "promote"; mutations.append(item)
        item = copy.deepcopy(deep); item["repository_model"]["semantic_model"]["edges"] = [{"edge_id": "bad"}]; mutations.append(item)
        item = copy.deepcopy(deep); item["workflow_telemetry"]["runs"] = [{"run_id": 1}]; mutations.append(item)
        item = copy.deepcopy(deep); item["implementation_package"]["actions"][0]["operation"] = "run_shell"; mutations.append(item)
        for index, broken in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ValidationError):
                Draft7Validator(self.report_schema).validate(broken)

    def test_profile_schema_rejects_unknown_fields(self):
        invalid = copy.deepcopy(load_json(ROOT / "profiles/capability-profiles.v1.json"))
        invalid["profiles"][0]["unexpected"] = True
        with self.assertRaises(ValidationError):
            Draft7Validator(self.profile_schema).validate(invalid)


if __name__ == "__main__":
    unittest.main()
