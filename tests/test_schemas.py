import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def test_ci_detective_schema_loads(self):
        data = json.loads((ROOT / "schemas" / "ci_detective_report.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(data.get("type"), "object")
        self.assertIn("repository", data.get("required", []))

    def test_gate_map_schema_loads(self):
        data = json.loads((ROOT / "schemas" / "ci_gate_map.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(data.get("type"), "object")
        self.assertIn("proposed_gates", data.get("required", []))
