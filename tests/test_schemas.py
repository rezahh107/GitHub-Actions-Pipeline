import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft7Validator, ValidationError

from tools.ci_detective import compute_evidence_sha256

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-07-05T00:00:00Z"
EXPECTED_RISK_PATTERN_FILES = {
    "browser-extension-mv3.yaml",
    "contract-schema-repo.yaml",
    "docs-only-repo.yaml",
    "multi-repo-adapter.yaml",
    "python-desktop.yaml",
    "python-package.yaml",
    "wordpress-plugin.yaml",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class SchemaValidationTests(unittest.TestCase):
    def test_schema_files_are_valid_json_schema(self):
        for path in sorted((ROOT / "schemas").glob("*.schema.json")):
            with self.subTest(path=path.name):
                schema = load_json(path)
                Draft7Validator.check_schema(schema)

    def test_ci_detective_example_validates_and_hash_matches(self):
        schema = load_json(ROOT / "schemas" / "ci_detective_report.schema.json")
        instance = load_json(ROOT / "examples" / "ci_detective_report.example.json")
        Draft7Validator(schema).validate(instance)
        self.assertEqual(instance["evidence_sha256"], compute_evidence_sha256(instance))

    def test_gate_map_json_example_validates_against_schema(self):
        schema = load_json(ROOT / "schemas" / "ci_gate_map.schema.json")
        instance = load_json(ROOT / "examples" / "ci_gate_map.example.json")
        Draft7Validator(schema).validate(instance)

    def test_risk_pattern_yaml_files_validate_against_schema(self):
        schema = load_json(ROOT / "schemas" / "risk_pattern.schema.json")
        validator = Draft7Validator(schema)
        pattern_paths = sorted((ROOT / "risk-patterns").glob("*.yaml"))

        self.assertEqual({path.name for path in pattern_paths}, EXPECTED_RISK_PATTERN_FILES)

        for path in pattern_paths:
            with self.subTest(path=path.name):
                validator.validate(load_yaml(path))

    def test_generated_ci_detective_report_validates_against_schema(self):
        schema = load_json(ROOT / "schemas" / "ci_detective_report.schema.json")
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "ci_detective_report.json"
            subprocess.run(
                [
                    sys.executable,
                    "tools/ci_detective.py",
                    "--repo-root",
                    ".",
                    "--out",
                    str(output),
                    "--generated-at",
                    FIXED_TIME,
                ],
                cwd=ROOT,
                check=True,
            )
            instance = load_json(output)
            Draft7Validator(schema).validate(instance)
            self.assertEqual(instance["evidence_sha256"], compute_evidence_sha256(instance))

    def test_gate_map_schema_rejects_missing_deferred_gates(self):
        schema = load_json(ROOT / "schemas" / "ci_gate_map.schema.json")
        instance = load_json(ROOT / "examples" / "ci_gate_map.example.json")
        instance.pop("deferred_gates")
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_risk_pattern_schema_rejects_malformed_data(self):
        schema = load_json(ROOT / "schemas" / "risk_pattern.schema.json")
        instance = {
            "project_type": "",
            "detection_signals": [{}],
            "risk_patterns": [
                {
                    "id": "bad-pattern",
                    "description": "",
                    "typical_trigger": "missing strict fields",
                    "detectability": "unknown",
                    "suggested_gate": "",
                }
            ],
            "unexpected": True,
        }
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_detective_schema_rejects_unexpected_hotspot_shape(self):
        schema = load_json(ROOT / "schemas" / "ci_detective_report.schema.json")
        instance = load_json(ROOT / "examples" / "ci_detective_report.example.json")
        instance["hotspots"][0] = {
            "path": "schemas/review.schema.json",
            "reason": "legacy loose example",
        }
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_detective_schema_rejects_invalid_sha(self):
        schema = load_json(ROOT / "schemas" / "ci_detective_report.schema.json")
        instance = load_json(ROOT / "examples" / "ci_detective_report.example.json")
        instance["run_context"]["tested_sha"] = "not-a-sha"
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_gate_map_schema_rejects_reject_priority_for_proposed_gate(self):
        schema = load_json(ROOT / "schemas" / "ci_gate_map.schema.json")
        instance = load_json(ROOT / "examples" / "ci_gate_map.example.json")
        instance["proposed_gates"][0]["risk_assessment"]["priority"] = "reject"
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)
