from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.ci_repository_model import build_repository_model
from tools.ci_workflow_trigger_patch import (
    EVENT_TRIGGER_SCHEMA_REGISTRY,
    WORKFLOW_TRIGGER_SCHEMA_CONTRACT_VERSION,
    _TRIGGER_FORM_HANDLERS,
    validate_trigger_structure,
)


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def capability(model: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(item for item in model["capabilities"] if item["capability_id"] == capability_id)


def workflow(events: str) -> str:
    return (
        "name: trigger fixture\non:\n"
        + textwrap.indent(textwrap.dedent(events).strip() + "\n", "  ")
        + "permissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
          "    steps:\n      - run: python -m unittest discover -s tests\n"
    )


class EventSpecificTriggerEvidenceBoundaryTests(unittest.TestCase):
    def model(self, source: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        write_files(root, {
            "tests/test_x.py": "import unittest\n",
            ".github/workflows/ci.yml": source,
        })
        return build_repository_model(root)

    def assert_invalid(self, events: str, code: str) -> None:
        model = self.model(workflow(events))
        parsed = model["workflows"][0]
        self.assertEqual(parsed["parse_status"], "invalid_shape")
        self.assertEqual(parsed["jobs"], [])
        self.assertEqual(parsed["commands"], [])
        self.assertEqual(parsed["command_evidence"], [])
        self.assertNotEqual(capability(model, "tests_run_on_pull_requests")["state"], "operational")
        self.assertIn(code, {item["code"] for item in model["unresolved_evidence"]})
        self.assertFalse(any(
            record.get("status") == "resolved" and record.get("families")
            for item in model["workflows"]
            for record in item.get("command_evidence", [])
        ))

    def test_event_property_and_activity_mismatches_fail_closed(self):
        cases = (
            ("pull_request:\npush:\n  workflows: [CI]", "WORKFLOW_TRIGGER_PROPERTY_UNSUPPORTED"),
            ("pull_request:\npush:\n  types: [opened]", "WORKFLOW_TRIGGER_PROPERTY_UNSUPPORTED"),
            ("pull_request:\nworkflow_run:\n  workflows: [CI]\n  paths: [src/**]", "WORKFLOW_TRIGGER_PROPERTY_UNSUPPORTED"),
            ("pull_request:\nworkflow_run:\n  workflows: [CI]\n  types: [opened]", "WORKFLOW_TRIGGER_ACTIVITY_INVALID"),
            ("pull_request:\nworkflow_run:\n  types: [completed]", "WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID"),
            ("pull_request:\nworkflow_dispatch:\n  outputs: {}", "WORKFLOW_TRIGGER_PROPERTY_UNSUPPORTED"),
            ("pull_request:\nworkflow_dispatch:\n  secrets: {}", "WORKFLOW_TRIGGER_PROPERTY_UNSUPPORTED"),
            ("pull_request:\nrepository_dispatch:\n  paths: [src/**]", "WORKFLOW_TRIGGER_PROPERTY_UNSUPPORTED"),
            ("pull_request:\n  types: [not_real]", "WORKFLOW_TRIGGER_ACTIVITY_INVALID"),
            ("pull_request:\nbranch_protection_rule:\n  types: [opened]", "WORKFLOW_TRIGGER_ACTIVITY_INVALID"),
            ("pull_request:\nwatch:\n  types: [stopped]", "WORKFLOW_TRIGGER_ACTIVITY_INVALID"),
            ("pull_request:\nfork:\n  types: [created]", "WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID"),
            ("pull_request:\nunknown_event:", "WORKFLOW_TRIGGER_EVENT_UNSUPPORTED"),
        )
        for events, code in cases:
            with self.subTest(events=events):
                self.assert_invalid(events, code)

    def test_dispatch_inputs_fail_closed(self):
        configs = (
            "inputs: [bad]",
            "inputs:\n  target: text",
            "inputs:\n  target:\n    unexpected: true",
            "inputs:\n  target:\n    type: unsupported",
            "inputs:\n  target:\n    type: choice",
            "inputs:\n  target:\n    type: choice\n    options: [dev, dev]",
            "inputs:\n  target:\n    type: choice\n    options: [dev, prod]\n    default: staging",
            "inputs:\n  target:\n    type: boolean\n    options: [yes, no]",
            "inputs:\n  target:\n    type: boolean\n    default: false-text",
            "inputs:\n  target:\n    type: number\n    default: true",
            "inputs:\n  target:\n    required: yes-text",
        )
        for config in configs:
            with self.subTest(config=config):
                self.assert_invalid(
                    "pull_request:\nworkflow_dispatch:\n" + textwrap.indent(config, "  "),
                    "WORKFLOW_DISPATCH_INPUT_INVALID",
                )

    def test_workflow_call_uses_distinct_nested_schemas(self):
        cases = (
            ("inputs:\n  target:\n    description: missing-type", "WORKFLOW_CALL_INPUT_INVALID"),
            ("inputs:\n  target:\n    type: choice", "WORKFLOW_CALL_INPUT_INVALID"),
            ("inputs:\n  target:\n    type: boolean\n    default: text", "WORKFLOW_CALL_INPUT_INVALID"),
            ("secrets:\n  token:\n    type: string", "WORKFLOW_CALL_SECRET_INVALID"),
            ("secrets:\n  token:\n    required: yes-text", "WORKFLOW_CALL_SECRET_INVALID"),
            ("outputs:\n  result:\n    description: missing-value", "WORKFLOW_CALL_OUTPUT_INVALID"),
            ("outputs:\n  result:\n    value: []", "WORKFLOW_CALL_OUTPUT_INVALID"),
            ("unknown: true", "WORKFLOW_TRIGGER_PROPERTY_UNSUPPORTED"),
        )
        for config, code in cases:
            with self.subTest(config=config):
                self.assert_invalid(
                    "pull_request:\nworkflow_call:\n" + textwrap.indent(config, "  "),
                    code,
                )

    def test_incompatible_filters_and_malformed_schedule_fail_closed(self):
        cases = (
            ("pull_request:\npush:\n  branches: [main]\n  branches-ignore: [dev]", "WORKFLOW_TRIGGER_FILTER_CONFLICT"),
            ("pull_request:\npush:\n  tags: [v*]\n  tags-ignore: [beta*]", "WORKFLOW_TRIGGER_FILTER_CONFLICT"),
            ("pull_request:\npush:\n  paths: [src/**]\n  paths-ignore: [docs/**]", "WORKFLOW_TRIGGER_FILTER_CONFLICT"),
            ("pull_request:\n  branches: [main]\n  branches-ignore: [dev]", "WORKFLOW_TRIGGER_FILTER_CONFLICT"),
            ("pull_request:\n  paths: [src/**]\n  paths-ignore: [docs/**]", "WORKFLOW_TRIGGER_FILTER_CONFLICT"),
            ("pull_request:\nworkflow_run:\n  workflows: [CI]\n  branches: [main]\n  branches-ignore: [dev]", "WORKFLOW_TRIGGER_FILTER_CONFLICT"),
            ("pull_request:\nschedule:\n  - timezone: UTC", "WORKFLOW_SCHEDULE_STRUCTURE_INVALID"),
            ("pull_request:\nschedule:\n  - cron: '0 0 * * *'\n    unexpected: true", "WORKFLOW_SCHEDULE_STRUCTURE_INVALID"),
        )
        for events, code in cases:
            with self.subTest(events=events):
                self.assert_invalid(events, code)
        self.assert_invalid(
            f"pull_request:\nrepository_dispatch:\n  types: [{'x' * 101}]",
            "WORKFLOW_TRIGGER_ACTIVITY_INVALID",
        )

    def test_registry_coverage_is_versioned_machine_checkable_and_enforced(self):
        self.assertEqual(WORKFLOW_TRIGGER_SCHEMA_CONTRACT_VERSION, "1.0.0")
        retained = {
            "push", "pull_request", "pull_request_target", "workflow_run",
            "repository_dispatch", "workflow_dispatch", "workflow_call", "schedule",
            "branch_protection_rule", "watch", "fork", "gollum", "page_build",
            "public", "status",
        }
        self.assertEqual(set(EVENT_TRIGGER_SCHEMA_REGISTRY), retained)
        self.assertLessEqual(
            {schema["form"] for schema in EVENT_TRIGGER_SCHEMA_REGISTRY.values()},
            set(_TRIGGER_FORM_HANDLERS),
        )
        with patch.dict(EVENT_TRIGGER_SCHEMA_REGISTRY, {"broken": {"form": "missing"}}, clear=False):
            diagnostics = validate_trigger_structure({"pull_request": None}, reference="ci.yml.on")
        self.assertEqual({item["code"] for item in diagnostics}, {"WORKFLOW_TRIGGER_SCHEMA_COVERAGE_GAP"})

    def test_positive_controls_cover_every_retained_event_schema(self):
        positive = {
            "push": {"branches": ["main"], "paths": ["src/**"]},
            "pull_request": {"types": ["opened", "synchronize"], "branches": ["main"]},
            "pull_request_target": None,
            "workflow_run": {"workflows": ["CI"], "types": ["completed"], "branches": ["main"]},
            "repository_dispatch": {"types": ["rebuild"]},
            "workflow_dispatch": {"inputs": {
                "dry_run": {"type": "boolean", "required": False, "default": False},
                "target": {"type": "choice", "options": ["dev", "prod"], "default": "dev"},
                "count": {"type": "number", "default": 1},
                "environment": {"type": "environment"},
                "note": {"description": "optional"},
            }},
            "workflow_call": {
                "inputs": {"count": {"type": "number", "default": 1}},
                "secrets": {"token": {"description": "token", "required": True}},
                "outputs": {"result": {"description": "result", "value": "${{ jobs.test.outputs.result }}"}},
            },
            "schedule": [{"cron": "0 0 * * *", "timezone": "UTC"}],
            "branch_protection_rule": {"types": ["created", "edited"]},
            "watch": {"types": ["started"]},
            "fork": None, "gollum": None, "page_build": None, "public": None, "status": None,
        }
        self.assertEqual(set(positive), set(EVENT_TRIGGER_SCHEMA_REGISTRY))
        self.assertEqual(validate_trigger_structure(positive, reference="ci.yml.on"), [])
        self.assertEqual(validate_trigger_structure(["pull_request", "workflow_dispatch"], reference="ci.yml.on"), [])
        self.assertEqual(validate_trigger_structure("push", reference="ci.yml.on"), [])

    def test_valid_pull_request_workflow_remains_operational(self):
        model = self.model(workflow("""
            pull_request:
              types: [opened, synchronize]
              branches: [main]
            workflow_dispatch:
              inputs:
                target:
                  type: choice
                  options: [dev, prod]
                  default: dev
        """))
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(capability(model, "tests_run_on_pull_requests")["state"], "operational")


if __name__ == "__main__":
    unittest.main()
