"""Harden duplicate schedule detection with complete-cycle occurrence identity."""
from __future__ import annotations

from tools import ci_schedule_resource_patch as _resource
from tools import ci_schedule_semantics as _semantics
from tools.ci_calendar_bitsets import matching_dates

CONTRACT_VERSION = "1.5.0"
OCCURRENCE_IDENTITY_WORK_UNITS = 1


def _complete_occurrence_identity(
    item: _resource._CanonicalSchedule,
    workflow: _resource._Ledger,
    repository: _resource._Ledger,
) -> tuple[str, tuple[int, ...], int]:
    """Return exact represented occurrence identity over one Gregorian cycle."""
    for ledger in (workflow, repository):
        ledger.charge(
            OCCURRENCE_IDENTITY_WORK_UNITS,
            "constructing a complete-cycle schedule occurrence identity",
        )
    return (item.timezone, item.times, matching_dates(item.predicate))


def _require_distinct_schedule_events(
    schedules: list[_resource._CanonicalSchedule],
    workflow: _resource._Ledger,
    repository: _resource._Ledger,
) -> None:
    """Reject schedules with identical timezone, minute set, and active dates."""
    seen: set[tuple[str, tuple[int, ...], int]] = set()
    for item in schedules:
        identity = _complete_occurrence_identity(item, workflow, repository)
        for ledger in (workflow, repository):
            ledger.charge(
                1,
                "comparing a complete-cycle schedule occurrence identity",
            )
        if identity in seen:
            raise _semantics.ScheduleSemanticError(
                "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
                "Multiple schedule entries resolve to the same complete occurrence "
                "semantics, but GitHub Actions duplicate-event delivery semantics "
                "are not represented.",
            )
        seen.add(identity)


def install_schedule_occurrence_identity_hardening() -> None:
    """Install complete occurrence identity after resource hardening."""
    if (
        getattr(_resource, "__schedule_occurrence_identity_contract__", None)
        == CONTRACT_VERSION
    ):
        return

    _resource.CONTRACT_VERSION = CONTRACT_VERSION
    _resource.OCCURRENCE_IDENTITY_WORK_UNITS = OCCURRENCE_IDENTITY_WORK_UNITS
    _resource._require_distinct_schedule_events = _require_distinct_schedule_events

    # Keep idempotence guards aligned if the resource installer is called again.
    _resource._parse_with_root.__schedule_resource_contract__ = CONTRACT_VERSION
    _resource._build_with_fresh_repository_budget.__schedule_resource_contract__ = (
        CONTRACT_VERSION
    )
    _resource.__schedule_occurrence_identity_contract__ = CONTRACT_VERSION
