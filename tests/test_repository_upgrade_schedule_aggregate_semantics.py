from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import ci_calendar_bitsets as calendar
from tools import ci_schedule_resource_patch as resource
from tools import ci_schedule_semantics as semantics
from tools.ci_repository_model import build_repository_model


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def capability(model: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(item for item in model["capabilities"] if item["capability_id"] == capability_id)


def workflow(entries: list[tuple[str, str | None]]) -> str:
    schedule = []
    for cron, timezone in entries:
        schedule.append(f"    - cron: '{cron}'\n")
        if timezone is not None:
            schedule.append(f"      timezone: {timezone}\n")
    return (
        "name: aggregate schedule fixture\non:\n  pull_request:\n  schedule:\n"
        + "".join(schedule)
        + "permissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
          "    steps:\n      - run: python -m unittest discover -s tests\n"
    )


class AggregateScheduleEvidenceBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        calendar.calendar_masks.cache_clear()
        calendar.matching_dates.cache_clear()
        calendar.consecutive_dates.cache_clear()
        calendar._cached_parse.cache_clear()
        resource._STATE.set(None)

    def model(self, entries: list[tuple[str, str | None]]) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        write_files(
            root,
            {
                "tests/test_x.py": "import unittest\n",
                ".github/workflows/ci.yml": workflow(entries),
            },
        )
        return build_repository_model(root)

    def assert_invalid(self, entries: list[tuple[str, str | None]], code: str) -> None:
        model = self.model(entries)
        parsed = model["workflows"][0]
        self.assertEqual(parsed["parse_status"], "invalid_shape")
        self.assertEqual(parsed["triggers"], [])
        self.assertEqual(parsed["jobs"], [])
        self.assertEqual(parsed["commands"], [])
        self.assertEqual(parsed["command_evidence"], [])
        self.assertNotEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )
        self.assertIn(code, {item["code"] for item in model["unresolved_evidence"]})

    def test_union_of_hourly_utc_entries_one_minute_apart_fails_closed(self):
        self.assert_invalid(
            [("0 * * * *", "UTC"), ("1 * * * *", "UTC")],
            "WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT",
        )

    def test_cross_midnight_union_on_consecutive_dates_fails_closed(self):
        self.assert_invalid(
            [("59 23 * * *", "UTC"), ("0 0 * * *", "UTC")],
            "WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT",
        )

    def test_gregorian_cycle_boundary_is_cyclically_adjacent(self):
        last_day = 1 << (calendar._CYCLE_DAYS - 1)
        first_day = 1
        self.assertTrue(calendar.adjacent_date_masks(last_day, first_day))
        self.assertFalse(calendar.adjacent_date_masks(first_day, last_day))

    def test_duplicate_entries_are_semantically_deduplicated(self):
        model = self.model([
            ("0 * * * *", "UTC"),
            ("0 * * * *", "UTC"),
        ])
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )

    def test_multiple_timezones_fail_closed_until_normalization_is_represented(self):
        self.assert_invalid(
            [("0 * * * *", "UTC"), ("5 * * * *", "Asia/Baku")],
            "WORKFLOW_SCHEDULE_TIMEZONE_SET_UNSUPPORTED",
        )

    def test_aggregate_charging_is_independent_of_cache_warmth(self):
        schedules = [
            resource._canonical_schedule(semantics.parse_cron_expression("0 * * * *"), "UTC"),
            resource._canonical_schedule(semantics.parse_cron_expression("5 * * * *"), "UTC"),
        ]
        observed: list[tuple[int, int]] = []
        for _ in range(2):
            workflow_ledger = resource._Ledger("workflow", 4096)
            repository_ledger = resource._Ledger("repository", 8192)
            self.assertIsNone(
                resource._aggregate_interval(schedules, workflow_ledger, repository_ledger)
            )
            observed.append((workflow_ledger.used, repository_ledger.used))
        self.assertEqual(observed[0], observed[1])

    def test_aggregate_workflow_budget_exhaustion_fails_closed(self):
        with patch.object(resource, "WORKFLOW_LIMIT", 40):
            self.assert_invalid(
                [("0 * * * *", "UTC")],
                "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED",
            )

    def test_aggregate_repository_budget_spans_workflow_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_files(
                root,
                {
                    "tests/test_x.py": "import unittest\n",
                    ".github/workflows/a.yml": workflow([("0 * 1 JAN *", "UTC")]),
                    ".github/workflows/b.yml": workflow([("0 * 2 FEB *", "UTC")]),
                },
            )
            with patch.object(resource, "REPOSITORY_LIMIT", 100):
                model = build_repository_model(root)
        workflows = {item["path"]: item for item in model["workflows"]}
        self.assertEqual(workflows[".github/workflows/a.yml"]["parse_status"], "parsed")
        rejected = workflows[".github/workflows/b.yml"]
        self.assertEqual(rejected["parse_status"], "invalid_shape")
        self.assertEqual(rejected["jobs"], [])
        self.assertEqual(rejected["commands"], [])
        self.assertEqual(rejected["command_evidence"], [])
        self.assertIn(
            "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED",
            {item["code"] for item in model["unresolved_evidence"]},
        )

    def test_valid_multi_entry_union_at_five_minutes_remains_operational(self):
        model = self.model([
            ("0 * * * *", "UTC"),
            ("5 * * * *", "UTC"),
            ("55 23 * * *", "UTC"),
        ])
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )


if __name__ == "__main__":
    unittest.main()
