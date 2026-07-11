from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.ci_schedule_semantics as schedule_semantics
from tools import ci_pinned_timezone as pinned_timezone
from tools.ci_repository_model import build_repository_model


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def capability(model: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(item for item in model["capabilities"] if item["capability_id"] == capability_id)


def workflow(schedule_entries: str) -> str:
    return (
        "name: schedule fixture\non:\n  pull_request:\n  schedule:\n"
        f"{schedule_entries}"
        "permissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: python -m unittest discover -s tests\n"
    )


class ScheduleSemanticEvidenceBoundaryTests(unittest.TestCase):
    def model(self, source: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        write_files(
            root,
            {
                "tests/test_x.py": "import unittest\n",
                ".github/workflows/ci.yml": source,
            },
        )
        return build_repository_model(root)

    def assert_invalid(self, entries: str, code: str) -> None:
        model = self.model(workflow(entries))
        parsed = model["workflows"][0]
        self.assertEqual(parsed["parse_status"], "invalid_shape")
        self.assertEqual(parsed["jobs"], [])
        self.assertEqual(parsed["commands"], [])
        self.assertEqual(parsed["command_evidence"], [])
        self.assertNotEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )
        self.assertIn(code, {item["code"] for item in model["unresolved_evidence"]})
        self.assertFalse(
            any(
                record.get("status") == "resolved" and record.get("families")
                for item in model["workflows"]
                for record in item.get("command_evidence", [])
            )
        )

    def test_invalid_cron_forms_fail_closed_before_command_evidence(self):
        cases = (
            ("    - cron: '0 0 * *'\n", "WORKFLOW_SCHEDULE_CRON_INVALID"),
            ("    - cron: '@daily'\n", "WORKFLOW_SCHEDULE_CRON_INVALID"),
            ("    - cron: '* * * * *'\n", "WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT"),
            ("    - cron: '0,4 * * * *'\n", "WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT"),
            ("    - cron: '59,0 23,0 * * *'\n", "WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT"),
            ("    - cron: '60 0 * * *'\n", "WORKFLOW_SCHEDULE_CRON_INVALID"),
            ("    - cron: '0 24 * * *'\n", "WORKFLOW_SCHEDULE_CRON_INVALID"),
            ("    - cron: '0 0 0 * *'\n", "WORKFLOW_SCHEDULE_CRON_INVALID"),
            ("    - cron: '0 0 * 13 *'\n", "WORKFLOW_SCHEDULE_CRON_INVALID"),
            ("    - cron: '0 0 * * 7'\n", "WORKFLOW_SCHEDULE_CRON_INVALID"),
            ("    - cron: [0, 5]\n", "WORKFLOW_SCHEDULE_CRON_INVALID"),
        )
        for entries, code in cases:
            with self.subTest(entries=entries):
                self.assert_invalid(entries, code)

    def test_timezone_failures_are_semantic_and_fail_closed(self):
        cases = (
            (
                "    - cron: '0 0 * * *'\n      timezone: Mars/Olympus\n",
                "WORKFLOW_SCHEDULE_TIMEZONE_INVALID",
            ),
            (
                "    - cron: '0 0 * * *'\n      timezone: [Etc/UTC]\n",
                "WORKFLOW_SCHEDULE_TIMEZONE_INVALID",
            ),
        )
        for entries, code in cases:
            with self.subTest(entries=entries):
                self.assert_invalid(entries, code)

    def test_one_invalid_entry_invalidates_the_complete_workflow(self):
        self.assert_invalid(
            "    - cron: '*/5 * * * *'\n"
            "      timezone: Etc/UTC\n"
            "    - cron: '* * * * *'\n",
            "WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT",
        )

    def test_valid_five_minute_or_slower_schedules_remain_evidentiary(self):
        source = workflow(
            "    - cron: '*/5 * * * *'\n"
            "      timezone: Etc/UTC\n"
            "    - cron: '30 5 * * 1-5'\n"
            "      timezone: America/New_York\n"
            "    - cron: '0 0 * JAN MON'\n"
            "      timezone: Asia/Baku\n"
            "    - cron: '59,0 23,0 * * MON'\n"
            "      timezone: UTC\n"
        )
        model = self.model(source)
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )

    def test_timezone_data_source_unavailability_fails_closed(self):
        with patch.object(
            pinned_timezone,
            "pinned_identifier_state",
            return_value=(None, "Pinned timezone data unavailable."),
        ):
            with self.assertRaises(schedule_semantics.ScheduleSemanticError) as caught:
                pinned_timezone.validate_pinned_timezone("Etc/UTC")
        self.assertEqual(
            caught.exception.code,
            "WORKFLOW_SCHEDULE_TIMEZONE_UNVERIFIABLE",
        )


if __name__ == "__main__":
    unittest.main()
