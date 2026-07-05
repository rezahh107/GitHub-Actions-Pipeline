import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class SchemaValidationTests(unittest.TestCase):
    def test_schema_files_are_valid_json_schema(self):
        for path in sorted((ROOT / "schemas").glob("*.schema.json")):
            with self.subTest(path=path.name):
                schema = load_json(path)
                Draft7Validator.check_schema(schema)

    def test_ci_detective_example_validates_against_schema(self):
        schema = load_json(ROOT / "schemas" / "ci_detective_report.schema.json")
        instance = load_json(ROOT / "examples" / "ci_detective_report.example.json")
        Draft7Validator(schema).validate(instance)

    def test_gate_map_json_example_validates_against_schema(self):
        schema = load_json(ROOT / "schemas" / "ci_gate_map.schema.json")
        instance = load_json(ROOT / "examples" / "ci_gate_map.example.json")
        Draft7Validator(schema).validate(instance)

    def test_generated_ci_detective_report_validates_against_schema(self):
        schema = load_json(ROOT / "schemas" / "ci_detective_report.schema.json")
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "ci_detective_report.json"
            subprocess.run(
                [sys.executable, "tools/ci_detective.py", "--repo-root", ".", "--out", str(output)],
                cwd=ROOT,
                check=True,
            )
            Draft7Validator(schema).validate(load_json(output))

    def test_schema_rejects_missing_required_field(self):
        schema = load_json(ROOT / "schemas" / "ci_gate_map.schema.json")
        instance = load_json(ROOT / "examples" / "ci_gate_map.example.json")
        instance.pop("target_repository")
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_schema_rejects_unexpected_top_level_property(self):
        schema = load_json(ROOT / "schemas" / "ci_detective_report.schema.json")
        instance = load_json(ROOT / "examples" / "ci_detective_report.example.json")
        instance["unexpected"] = True
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_schema_rejects_invalid_enum_value(self):
        schema = load_json(ROOT / "schemas" / "ci_gate_map.schema.json")
        instance = load_json(ROOT / "examples" / "ci_gate_map.example.json")
        instance["proposed_gates"][0]["priority"] = "urgent"
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)
