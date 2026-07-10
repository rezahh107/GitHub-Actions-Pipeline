import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError

from tools.repository_upgrade import build_upgrade_report

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-07-10T00:00:00Z"


class UpgradeSchemaTests(unittest.TestCase):
    def load(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_new_schemas_are_valid(self):
        for name in ("capability_profile.schema.json", "repository_upgrade_report.schema.json"):
            Draft7Validator.check_schema(self.load(ROOT / "schemas" / name))

    def test_profiles_validate_and_ids_are_unique(self):
        schema = self.load(ROOT / "schemas" / "capability_profile.schema.json")
        validator = Draft7Validator(schema)
        profile_ids = set()
        for path in sorted((ROOT / "profiles").glob("*.json")):
            value = self.load(path)
            validator.validate(value)
            self.assertNotIn(value["profile_id"], profile_ids)
            profile_ids.add(value["profile_id"])

    def test_committed_upgrade_examples_validate_and_hash_match(self):
        from tools.repository_upgrade import report_sha256

        schema = self.load(ROOT / "schemas" / "repository_upgrade_report.schema.json")
        validator = Draft7Validator(schema)
        for name in (
            "repository_upgrade.minimal.example.json",
            "repository_upgrade.deep.example.json",
        ):
            report = self.load(ROOT / "examples" / name)
            validator.validate(report)
            self.assertEqual(report["report_sha256"], report_sha256(report))

    def test_generated_reports_validate_in_both_modes(self):
        schema = self.load(ROOT / "schemas" / "repository_upgrade_report.schema.json")
        validator = Draft7Validator(schema)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "schemas").mkdir()
            (repo / "schemas" / "example.schema.json").write_text(
                '{"$schema":"http://json-schema.org/draft-07/schema#","type":"object"}\n'
            )
            (repo / "tests").mkdir()
            (repo / "tests" / "test_invalid_fixture.py").write_text(
                "def test_invalid_fixture():\n    assert True\n"
            )
            for mode in ("minimal-safe-ci", "deep-repository-upgrade"):
                report = build_upgrade_report(
                    repo,
                    mode=mode,
                    generated_at=FIXED_TIME,
                    profile_root=ROOT / "profiles",
                )
                validator.validate(report)

    def test_minimal_schema_rejects_phase_two(self):
        schema = self.load(ROOT / "schemas" / "repository_upgrade_report.schema.json")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "README.md").write_text("docs\n")
            report = build_upgrade_report(
                repo,
                mode="minimal-safe-ci",
                generated_at=FIXED_TIME,
                profile_root=ROOT / "profiles",
            )
            report["staged_upgrade_plan"]["phase_2"] = [{
                "recommendation_id": "REC-999",
                "objective": "bad",
                "reconsider_when": "never",
            }]
            with self.assertRaises(ValidationError):
                Draft7Validator(schema).validate(report)


if __name__ == "__main__":
    unittest.main()
