from __future__ import annotations

import os
import tempfile
import unittest
from importlib import metadata
from pathlib import Path
from unittest.mock import patch
import zoneinfo

from tools import ci_calendar_bitsets as calendar
from tools import ci_pinned_timezone as pinned
from tools import ci_schedule_resource_patch as resource
from tools import ci_schedule_semantics as semantics
from tools.ci_repository_model import build_repository_model

WORST_CASE = "0,59 0,23 31 * *"


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
        "name: resource fixture\non:\n  pull_request:\n  schedule:\n"
        + "".join(schedule)
        + "permissions: {}\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
          "    steps:\n      - run: python -m unittest discover -s tests\n"
    )


class PinnedTimezoneIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        pinned.pinned_identifier_state.cache_clear()

    def tearDown(self) -> None:
        pinned.pinned_identifier_state.cache_clear()

    def test_pinned_source_and_positive_identifiers(self):
        identifiers, error = pinned.pinned_identifier_state()
        self.assertIsNone(error)
        self.assertEqual(len(identifiers), pinned.PINNED_ZONE_COUNT)
        for key in ("Etc/UTC", "UTC", "America/New_York", "Asia/Baku"):
            pinned.validate_pinned_timezone(key)

    def test_host_special_and_non_manifest_keys_are_rejected(self):
        for key in (
            "posixrules", "localtime", "right/UTC", "posix/UTC",
            "SystemV/EST5EDT", "Attacker/Injected",
        ):
            with self.subTest(key=key):
                with self.assertRaises(semantics.ScheduleSemanticError) as caught:
                    pinned.validate_pinned_timezone(key)
                self.assertEqual(caught.exception.code, "WORKFLOW_SCHEDULE_TIMEZONE_INVALID")

    def test_attacker_pythontzpath_cannot_expand_pinned_identity(self):
        dist = metadata.distribution("tzdata")
        tzif = Path(dist.locate_file("tzdata/zoneinfo/Etc/UTC")).read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            injected = Path(temporary) / "Attacker" / "Injected"
            injected.parent.mkdir(parents=True)
            injected.write_bytes(tzif)
            previous = os.environ.get("PYTHONTZPATH")
            try:
                os.environ["PYTHONTZPATH"] = temporary
                zoneinfo.reset_tzpath()
                zoneinfo.ZoneInfo.clear_cache()
                self.assertEqual(zoneinfo.ZoneInfo("Attacker/Injected").key, "Attacker/Injected")
                with self.assertRaises(semantics.ScheduleSemanticError) as caught:
                    pinned.validate_pinned_timezone("Attacker/Injected")
                self.assertEqual(caught.exception.code, "WORKFLOW_SCHEDULE_TIMEZONE_INVALID")
            finally:
                if previous is None:
                    os.environ.pop("PYTHONTZPATH", None)
                else:
                    os.environ["PYTHONTZPATH"] = previous
                zoneinfo.reset_tzpath()
                zoneinfo.ZoneInfo.clear_cache()

    def test_missing_system_and_pinned_data_fails_closed(self):
        previous = os.environ.get("PYTHONTZPATH")
        try:
            os.environ["PYTHONTZPATH"] = ""
            zoneinfo.reset_tzpath()
            with patch.object(
                pinned.metadata,
                "distribution",
                side_effect=metadata.PackageNotFoundError("tzdata"),
            ):
                pinned.pinned_identifier_state.cache_clear()
                with self.assertRaises(semantics.ScheduleSemanticError) as caught:
                    pinned.validate_pinned_timezone("Etc/UTC")
            self.assertEqual(caught.exception.code, "WORKFLOW_SCHEDULE_TIMEZONE_UNVERIFIABLE")
        finally:
            if previous is None:
                os.environ.pop("PYTHONTZPATH", None)
            else:
                os.environ["PYTHONTZPATH"] = previous
            zoneinfo.reset_tzpath()


class CumulativeScheduleBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        calendar.calendar_masks.cache_clear()
        calendar.consecutive_dates.cache_clear()
        calendar._cached_parse.cache_clear()
        resource._STATE.set(None)

    def test_worst_case_repeated_to_bound_is_deduplicated(self):
        workflow_ledger = resource._Ledger("workflow", 4096)
        repository_ledger = resource._Ledger("repository", 100_000)
        for _ in range(256):
            resource._charge(WORST_CASE, workflow_ledger, repository_ledger)
            semantics.validate_cron_expression(WORST_CASE)
        self.assertLess(workflow_ledger.used, 512)
        self.assertEqual(calendar.calendar_masks.cache_info().misses, 1)
        self.assertEqual(calendar.consecutive_dates.cache_info().misses, 1)

    def test_distinct_worst_case_predicates_hit_same_deterministic_budget(self):
        expressions = [
            f"0,59 0,23 {day} {month} *"
            for month in range(1, 13)
            for day in range(1, 32)
        ]
        observed = []
        for _ in range(2):
            workflow_ledger = resource._Ledger("workflow", 700)
            repository_ledger = resource._Ledger("repository", 100_000)
            with self.assertRaises(semantics.ScheduleSemanticError) as caught:
                for expression in expressions:
                    resource._charge(expression, workflow_ledger, repository_ledger)
            self.assertEqual(
                caught.exception.code,
                "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED",
            )
            observed.append(workflow_ledger.used)
        self.assertEqual(observed[0], observed[1])
        self.assertLessEqual(observed[0], 700)

    def test_repository_budget_spans_multiple_workflow_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = [(f"0,59 0,23 {day} 1 *", None) for day in range(1, 6)]
            second = [(f"0,59 0,23 {day} 2 *", None) for day in range(6, 11)]
            write_files(root, {
                "tests/test_x.py": "import unittest\n",
                ".github/workflows/a.yml": workflow(first),
                ".github/workflows/b.yml": workflow(second),
            })
            with patch.object(resource, "REPOSITORY_LIMIT", 300):
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


class ResourceBoundaryIntegrationTests(unittest.TestCase):
    def model(self, entries: list[tuple[str, str | None]]) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        write_files(root, {
            "tests/test_x.py": "import unittest\n",
            ".github/workflows/ci.yml": workflow(entries),
        })
        return build_repository_model(root)

    def test_host_special_keys_invalidate_complete_workflow(self):
        for key in ("posixrules", "localtime", "right/UTC", "posix/UTC"):
            with self.subTest(key=key):
                model = self.model([("*/5 * * * *", key)])
                parsed = model["workflows"][0]
                self.assertEqual(parsed["parse_status"], "invalid_shape")
                self.assertEqual(parsed["jobs"], [])
                self.assertEqual(parsed["commands"], [])
                self.assertEqual(parsed["command_evidence"], [])
                self.assertNotEqual(
                    capability(model, "tests_run_on_pull_requests")["state"],
                    "operational",
                )
                self.assertIn(
                    "WORKFLOW_SCHEDULE_TIMEZONE_INVALID",
                    {item["code"] for item in model["unresolved_evidence"]},
                )

    def test_ordinary_and_worst_case_valid_controls_remain_operational(self):
        model = self.model([
            ("*/5 * * * *", "Etc/UTC"),
            (WORST_CASE, "America/New_York"),
            ("30 5 * * MON", "Asia/Baku"),
        ])
        self.assertEqual(model["workflows"][0]["parse_status"], "parsed")
        self.assertEqual(
            capability(model, "tests_run_on_pull_requests")["state"],
            "operational",
        )


if __name__ == "__main__":
    unittest.main()
