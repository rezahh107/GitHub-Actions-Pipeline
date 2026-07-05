import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExampleTests(unittest.TestCase):
    def test_ci_detective_example_loads(self):
        data = json.loads((ROOT / "examples" / "ci_detective_report.example.json").read_text(encoding="utf-8"))
        self.assertEqual(data["report_version"], "0.1")
        self.assertIn("inventory", data)
        self.assertIn("limitations", data)

    def test_gate_map_example_contains_required_anchors(self):
        text = (ROOT / "examples" / "ci_gate_map.example.yaml").read_text(encoding="utf-8")
        for anchor in ["gate_map_version:", "proposed_gates:", "rejected_gates:", "owner_permission_required:"]:
            self.assertIn(anchor, text)
