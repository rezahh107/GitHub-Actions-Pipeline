import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ScopeClaimAuditExampleTests(unittest.TestCase):
    def load(self, name: str):
        return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))

    def test_positive_underreported_example_is_advisory_and_non_blocking(self):
        data = self.load("scope_claim_audit.example.json")
        self.assertIn(data["scope_claim_result"], {"scope_underreported", "mismatch"})
        self.assertEqual("advisory", data["enforcement_mode"])
        self.assertIsNone(data["wired_enforcement_gate"])
        self.assertFalse(data["blocking"])
        self.assertIn("schemas/ci_gate_map.schema.json", data["sensitive_surfaces"]["schema"])
        self.assertIn(".github/workflows/validate.yml", data["sensitive_surfaces"]["workflow"])

    def test_true_negative_is_not_flagged_as_mismatch(self):
        data = self.load("scope_claim_audit.true-negative.example.json")
        self.assertIn(data["scope_claim_result"], {"scope_expanded_but_declared", "congruent"})
        self.assertNotEqual("mismatch", data["scope_claim_result"])
        self.assertEqual("advisory", data["enforcement_mode"])
        self.assertFalse(data["blocking"])

    def test_ambiguous_example_is_not_assessable(self):
        data = self.load("scope_claim_audit.ambiguous.example.json")
        self.assertEqual("not_assessable", data["scope_claim_result"])
        self.assertEqual("advisory", data["enforcement_mode"])
        self.assertFalse(data["blocking"])
        self.assertEqual("ambiguous", data["claim_classification"]["inferred_claim_type"])

    def test_examples_contain_required_semantic_children(self):
        for name in [
            "scope_claim_audit.example.json",
            "scope_claim_audit.true-negative.example.json",
            "scope_claim_audit.ambiguous.example.json",
        ]:
            with self.subTest(name=name):
                data = self.load(name)
                self.assertIn("claim_sources", data)
                self.assertIn("deterministic_diff_facts", data)
                self.assertIn("sensitive_surfaces", data)
                self.assertIn("claim_classification", data)
                self.assertIn("enforcement_mode", data)
                self.assertIn("wired_enforcement_gate", data)
                self.assertIn("recommended_action", data)
