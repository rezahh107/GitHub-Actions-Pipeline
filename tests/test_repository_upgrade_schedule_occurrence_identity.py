from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import ci_calendar_bitsets as calendar
from tools import ci_pinned_timezone as pinned
from tools import ci_schedule_occurrence_identity_patch as occurrence
from tools import ci_schedule_resource_patch as resource
from tools import ci_schedule_semantics as semantics
from tools.ci_repository_model import build_repository_model


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def capability(model: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(
        item
        for item in model["capabilities"]
        if item["capability_id"] == capability_id
    )


def workflow(entries: list[tuple[str, str | None]]) -> str:
    schedule = []
    for cron, timezone in entries:
        schedule.append(f"    - cron: '{cron}'\n")
        if timezone is not None:
            schedule.append(f"      timezone: {timezone}\n")
    return (
        "name: occurrence identity fixture\non:\n  pull_request:\n  schedule:\n"
        + "".join(schedule)
        + "permissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
          "    steps:\n      - run: python -m unittest discover -s tests\n"
    )


class CompleteOccurrenceIdentityTests(unittest.TestCase):
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

    def test_full_domain_day_of_month_alias_fails_closed(self):
        self.assert_invalid(
            [("0 0 * * *", "UTC"), ("0 0 1-31 * *", "UTC")],
            "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
        )

    def test_full_domain_day_of_week_alias_fails_closed(self):
        self.assert_invalid(
            [("0 0 * * *", "UTC"), ("0 0 * * 0-6", "UTC")],
            "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
        )

    def test_duplicate_rejection_precedes_transition_proof(self):
        self.assert_invalid(
            [
                ("0,5 * * * *", "America/New_York"),
                ("0,5 1-31 * *", "America/New_York"),
            ],
            "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
        )

    def test_semantically_distinct_date_predicate_remains_operational(self):
        model = self.model(
            [("0 0 * * *", "UTC"), ("0 0 1-30 * *", "UTC")]
        )
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )

    def test_occurrence_identity_charging_is_cache_warmth_independent(self):
        schedules = [
            resource._canonical_schedule(
                semantics.parse_cron_expression("0 0 * * *"), "UTC"
            ),
            resource._canonical_schedule(
                semantics.parse_cron_expression("0 0 1-31 * *"), "UTC"
            ),
        ]
        observed: list[tuple[int, int]] = []
        for _ in range(2):
            workflow_ledger = resource._Ledger("workflow", 4096)
            repository_ledger = resource._Ledger("repository", 8192)
            with self.assertRaises(semantics.ScheduleSemanticError) as caught:
                resource._aggregate_interval(
                    schedules,
                    workflow_ledger,
                    repository_ledger,
                )
            self.assertEqual(
                caught.exception.code,
                "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
            )
            observed.append((workflow_ledger.used, repository_ledger.used))
        self.assertEqual(observed[0], observed[1])
        expected = 2 * (occurrence.OCCURRENCE_IDENTITY_WORK_UNITS + 1)
        self.assertEqual(observed[0], (expected, expected))

    def test_occurrence_identity_workflow_and_repository_budgets_are_deterministic(self):
        schedules = [
            resource._canonical_schedule(
                semantics.parse_cron_expression(f"0 0 {day} JAN *"), "UTC"
            )
            for day in range(1, 5)
        ]
        for scope, workflow_limit, repository_limit in (
            ("workflow", 32, 4096),
            ("repository", 4096, 32),
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


if __name__ == "__main__":
    unittest.main()
