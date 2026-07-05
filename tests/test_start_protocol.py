import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "protocol" / "start.yaml"
SCHEMA_PATH = ROOT / "schemas" / "start.schema.json"
EXPECTED_RESPONSE = "آماده‌ام. آدرس ریپو را برای بررسی بفرست."
REQUIRED_TRIGGERS = {"شروع", "شروع کن", "start"}


def load_protocol():
    return yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))


class StartProtocolTests(unittest.TestCase):
    def test_protocol_validates_against_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        Draft7Validator(schema).validate(load_protocol())

    def test_response_is_exactly_one_line_and_stops(self):
        response = load_protocol()["response"]
        self.assertEqual(EXPECTED_RESPONSE, response["exact_text"])
        self.assertNotIn("\n", response["exact_text"])
        self.assertEqual(1, response["max_lines"])
        self.assertTrue(response["exact_match_required"])
        self.assertTrue(response["stop_after_response"])

    def test_required_start_triggers_exist(self):
        protocol = load_protocol()
        triggers = set(protocol["triggers"]["exact"])
        self.assertTrue(REQUIRED_TRIGGERS.issubset(triggers))
        self.assertTrue(protocol["triggers"]["matching"]["trim_whitespace"])
        self.assertFalse(protocol["triggers"]["matching"]["case_sensitive"])
        self.assertTrue(
            protocol["triggers"]["matching"]["requires_missing_target_repository"]
        )

    def test_start_state_transitions_to_target_intake(self):
        protocol = load_protocol()
        self.assertEqual("boot", protocol["state_transition"]["from"])
        self.assertEqual(
            "awaiting_target_repository",
            protocol["state_transition"]["to"],
        )
        self.assertEqual("audit_only", protocol["target_repository_input"]["next_state"])

    def test_pipeline_repository_requires_explicit_target_selection(self):
        guard = load_protocol()["self_repository_guard"]
        self.assertEqual(
            "rezahh107/GitHub-Actions-Pipeline",
            guard["repository"],
        )
        self.assertTrue(guard["audit_only_when_explicitly_requested"])

    def test_user_facing_documents_share_the_canonical_response(self):
        paths = [
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "prompts" / "00-start.md",
        ]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn(EXPECTED_RESPONSE, text)

    def test_agents_start_rule_precedes_normal_operating_rules(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertLess(
            text.index("## Immediate Start Rule"),
            text.index("## Repository Mission"),
        )

    def test_legacy_english_start_response_is_removed(self):
        text = (ROOT / "prompts" / "00-start.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "Pipeline loaded. I am ready. Send the target repository.",
            text,
        )
