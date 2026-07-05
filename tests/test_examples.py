import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExampleTests(unittest.TestCase):
    def test_ci_detective_example_loads(self):
        data = json.loads(
            (ROOT / "examples" / "ci_detective_report.example.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["report_version"], "0.1.1")
        self.assertEqual(data["canonicalization_version"], "1")
        self.assertIn("run_context", data)
        self.assertIn("evidence_sha256", data)

    def test_gate_map_json_example_loads(self):
        data = json.loads(
            (ROOT / "examples" / "ci_gate_map.example.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["gate_map_version"], "0.1.1")
        self.assertIn("proposed_gates", data)
        self.assertIn("rejected_gates", data)
        self.assertIn("deferred_gates", data)
        self.assertIn("risk_assessment", data["proposed_gates"][0])
