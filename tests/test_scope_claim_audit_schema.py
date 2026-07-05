import json
import unittest
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "scope_claim_audit.schema.json"
EXAMPLE_PATHS = [
    ROOT / "examples" / "scope_claim_audit.example.json",
    ROOT / "examples" / "scope_claim_audit.true-negative.example.json",
    ROOT / "examples" / "scope_claim_audit.ambiguous.example.json",
]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class ScopeClaimAuditSchemaTests(unittest.TestCase):
    def test_scope_claim_audit_schema_is_valid_json_schema(self):
        Draft7Validator.check_schema(load_json(SCHEMA_PATH))

    def test_scope_claim_audit_examples_validate_against_schema(self):
        schema = load_json(SCHEMA_PATH)
        validator = Draft7Validator(schema)
        for path in EXAMPLE_PATHS:
            with self.subTest(path=path.name):
                validator.validate(load_json(path))

    def test_scope_claim_audit_schema_rejects_missing_required_field(self):
        schema = load_json(SCHEMA_PATH)
        instance = load_json(EXAMPLE_PATHS[0])
        instance.pop("target_repository")
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_scope_claim_audit_schema_rejects_unexpected_top_level_property(self):
        schema = load_json(SCHEMA_PATH)
        instance = load_json(EXAMPLE_PATHS[0])
        instance["unexpected"] = True
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_scope_claim_audit_schema_rejects_invalid_result_enum(self):
        schema = load_json(SCHEMA_PATH)
        instance = load_json(EXAMPLE_PATHS[0])
        instance["scope_claim_result"] = "blocked"
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_reviewed_head_sha_must_be_full_lowercase_hex(self):
        schema = load_json(SCHEMA_PATH)
        validator = Draft7Validator(schema)
        for invalid_sha in ["1234567", "g" * 40, "ABCDEF1234567890ABCDEF1234567890ABCDEF12"]:
            with self.subTest(invalid_sha=invalid_sha):
                instance = load_json(EXAMPLE_PATHS[0])
                instance["reviewed_head_sha"] = invalid_sha
                with self.assertRaises(ValidationError):
                    validator.validate(instance)

    def test_blocking_true_requires_enforced_mode_and_wired_gate(self):
        schema = load_json(SCHEMA_PATH)
        instance = load_json(EXAMPLE_PATHS[0])
        instance["blocking"] = True
        with self.assertRaises(ValidationError):
            Draft7Validator(schema).validate(instance)

    def test_blocking_true_with_enforcement_metadata_validates(self):
        schema = load_json(SCHEMA_PATH)
        instance = load_json(EXAMPLE_PATHS[0])
        instance["enforcement_mode"] = "enforced"
        instance["blocking"] = True
        instance["wired_enforcement_gate"] = {
            "target_repository": "rezahh107/example-contract-repo",
            "gate_name": "Scope Claim Audit enforcement",
            "workflow_path": ".github/workflows/scope-claim-audit.yml",
            "check_name": "scope-claim-audit / enforce",
            "enforcement_evidence": "required status check is configured for this workflow",
            "policy_reference": "repository branch protection policy",
        }
        Draft7Validator(schema).validate(instance)
