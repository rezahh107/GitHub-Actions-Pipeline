from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import ci_calendar_bitsets as calendar
from tools import ci_pinned_timezone as pinned
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
        pinned.pinned_identifier_state.cache_clear()
        pinned.pinned_fixed_offset_state.cache_clear()
        resource._STATE.set(None)

    def tearDown(self) -> None:
        pinned.pinned_identifier_state.cache_clear()
        pinned.pinned_fixed_offset_state.cache_clear()

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

    def test_identical_cron_and_timezone_duplicate_fails_closed(self):
        self.assert_invalid(
            [("0 * * * *", "UTC"), ("0 * * * *", "UTC")],
            "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
        )

    def test_omitted_timezone_and_explicit_utc_duplicate_fails_closed(self):
        self.assert_invalid(
            [("0 0 * * *", None), ("0 0 * * *", "UTC")],
            "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
        )

    def test_syntactically_distinct_semantic_duplicate_fails_closed(self):
        self.assert_invalid(
            [("0 0 * * SUN", "UTC"), ("0 0 * * 0", "UTC")],
            "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
        )

    def test_duplicate_active_date_predicates_fail_closed(self):
        self.assert_invalid(
            [("0 0 1 JAN MON", "UTC"), ("0 0 1 1 1", "UTC")],
            "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
        )

    def test_large_duplicate_set_fails_closed_deterministically(self):
        self.assert_invalid(
            [("0 0 * * *", "UTC")] * 256,
            "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
        )

    def test_duplicate_scan_workflow_and_repository_budget_are_deterministic(self):
        schedules: list[resource._CanonicalSchedule] = []
        for month in range(1, 4):
            for day in range(1, 32):
                schedules.append(
                    resource._canonical_schedule(
                        semantics.parse_cron_expression(f"0 0 {day} {month} *"),
                        "UTC",
                    )
                )
                if len(schedules) == 70:
                    break
            if len(schedules) == 70:
                break
        schedules.append(schedules[-1])

        for scope, workflow_limit, repository_limit in (
            ("workflow", 64, 4096),
            ("repository", 4096, 64),
        ):
            observed: list[tuple[int, int, str]] = []
            for _ in range(2):
                workflow_ledger = resource._Ledger("workflow", workflow_limit)
                repository_ledger = resource._Ledger("repository", repository_limit)
                with self.assertRaises(semantics.ScheduleSemanticError) as caught:
                    resource._aggregate_interval(
                        schedules,
                        workflow_ledger,
                        repository_ledger,
                    )
                self.assertEqual(
                    caught.exception.code,
                    "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED",
                )
                observed.append(
                    (
                        workflow_ledger.used,
                        repository_ledger.used,
                        caught.exception.message,
                    )
                )
            self.assertEqual(observed[0], observed[1])
            self.assertIn(scope, observed[0][2])

    def test_multiple_timezones_fail_closed_until_normalization_is_represented(self):
        self.assert_invalid(
            [("0 * * * *", "UTC"), ("5 * * * *", "Asia/Baku")],
            "WORKFLOW_SCHEDULE_TIMEZONE_SET_UNSUPPORTED",
        )

    def test_spring_forward_timezone_set_fails_closed_before_local_mask_comparison(self):
        self.assert_invalid(
            [
                ("30 2 * * *", "America/New_York"),
                ("4 3 * * *", "America/New_York"),
            ],
            "WORKFLOW_SCHEDULE_TIMEZONE_TRANSITIONS_UNSUPPORTED",
        )

    def test_single_entry_expanding_to_multiple_local_times_requires_transition_proof(self):
        self.assert_invalid(
            [("4,30 2,3 * * *", "America/New_York")],
            "WORKFLOW_SCHEDULE_TIMEZONE_TRANSITIONS_UNSUPPORTED",
        )

    def test_fall_back_repeated_hour_is_explicitly_unsupported_for_multi_entry_sets(self):
        self.assert_invalid(
            [
                ("30 1 * * *", "America/New_York"),
                ("30 2 * * *", "America/New_York"),
            ],
            "WORKFLOW_SCHEDULE_TIMEZONE_TRANSITIONS_UNSUPPORTED",
        )

    def test_single_entry_transition_timezone_remains_supported(self):
        model = self.model([("30 2 * * *", "America/New_York")])
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )

    def test_positive_fixed_offset_multi_entry_control(self):
        model = self.model([
            ("0 * * * *", "Etc/GMT+5"),
            ("5 * * * *", "Etc/GMT+5"),
        ])
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )

    def test_transition_identity_mismatch_fails_closed(self):
        identifiers, error = pinned.pinned_identifier_state()
        self.assertIsNone(error)
        self.assertIn("UTC", identifiers)
        with patch.dict(
            pinned.PINNED_FIXED_OFFSET_TZIF_SHA256,
            {"UTC": "0" * 64},
            clear=False,
        ):
            pinned.pinned_fixed_offset_state.cache_clear()
            self.assert_invalid(
                [("0,5 * * * *", "UTC")],
                "WORKFLOW_SCHEDULE_TIMEZONE_TRANSITION_UNVERIFIABLE",
            )

    def test_transition_data_unavailable_fails_closed(self):
        identifiers, error = pinned.pinned_identifier_state()
        self.assertIsNone(error)
        self.assertIn("UTC", identifiers)
        pinned.pinned_fixed_offset_state.cache_clear()
        with patch.object(
            pinned,
            "_safe_file",
            side_effect=OSError("transition file unavailable"),
        ):
            self.assert_invalid(
                [("0,5 * * * *", "UTC")],
                "WORKFLOW_SCHEDULE_TIMEZONE_TRANSITION_UNVERIFIABLE",
            )

    def test_transition_charging_is_independent_of_cache_warmth(self):
        schedules = [
            resource._canonical_schedule(semantics.parse_cron_expression("0,5 * * * *"), "UTC"),
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
        self.assertGreaterEqual(observed[0][0], resource.TRANSITION_PROOF_WORK_UNITS)

    def test_transition_proof_workflow_budget_exhaustion_fails_closed(self):
        with patch.object(resource, "WORKFLOW_LIMIT", 80):
            self.assert_invalid(
                [("0,5 * * * *", "UTC")],
                "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED",
            )

    def test_transition_proof_repository_budget_spans_workflow_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_files(
                root,
                {
                    "tests/test_x.py": "import unittest\n",
                    ".github/workflows/a.yml": workflow([
                        ("0,5 * 1 JAN *", "UTC"),
                    ]),
                    ".github/workflows/b.yml": workflow([
                        ("0,5 * 2 FEB *", "Etc/GMT+5"),
                    ]),
                },
            )
            with patch.object(resource, "REPOSITORY_LIMIT", 300):
                model = build_repository_model(root)
        workflows = {item["path"]: item for item in model["workflows"]}
        self.assertEqual(workflows[".github/workflows/a.yml"]["parse_status"], "parsed")
        rejected = workflows[".github/workflows/b.yml"]
        self.assertEqual(rejected["parse_status"], "invalid_shape")
        self.assertEqual(rejected["triggers"], [])
        self.assertEqual(rejected["jobs"], [])
        self.assertEqual(rejected["commands"], [])
        self.assertEqual(rejected["command_evidence"], [])
        self.assertIn(
            "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED",
            {item["code"] for item in model["unresolved_evidence"]},
        )

    def test_distinct_utc_events_exactly_five_minutes_apart_remain_operational(self):
        model = self.model([
            ("0 * * * *", "UTC"),
            ("5 * * * *", "UTC"),
        ])
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
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
