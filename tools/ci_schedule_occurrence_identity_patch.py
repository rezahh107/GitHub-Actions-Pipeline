"""Harden schedule overlap detection with complete-cycle occurrence masks."""
from __future__ import annotations

from tools import ci_schedule_resource_patch as _resource
from tools import ci_schedule_semantics as _semantics
from tools.ci_calendar_bitsets import matching_dates

CONTRACT_VERSION = "1.6.0"
OCCURRENCE_IDENTITY_WORK_UNITS = 1


def _complete_occurrence_date_mask(
    item: _resource._CanonicalSchedule,
    workflow: _resource._Ledger,
    repository: _resource._Ledger,
) -> int:
    """Compute one complete Gregorian-cycle date mask for a schedule entry."""
    for ledger in (workflow, repository):
        ledger.charge(
            OCCURRENCE_IDENTITY_WORK_UNITS,
            "constructing a complete-cycle schedule occurrence mask",
        )
    return matching_dates(item.predicate)


def _require_distinct_schedule_events(
    schedules: list[_resource._CanonicalSchedule],
    workflow: _resource._Ledger,
    repository: _resource._Ledger,
) -> None:
    """Reject any entries whose represented local occurrences intersect."""
    accumulated_masks: dict[int, int] = {}
    for item in schedules:
        date_mask = _complete_occurrence_date_mask(item, workflow, repository)

        # Charge and complete every overlap check before mutating accumulated state.
        # This keeps rejection deterministic and prevents a partially added entry.
        for minute in item.times:
            for ledger in (workflow, repository):
                ledger.charge(
                    1,
                    "checking a complete-cycle local-minute occurrence overlap",
                )
            if accumulated_masks.get(minute, 0) & date_mask:
                raise _semantics.ScheduleSemanticError(
                    "WORKFLOW_SCHEDULE_DUPLICATE_EVENT_UNSUPPORTED",
                    "Multiple schedule entries overlap at the same represented local "
                    "minute and active date, but GitHub Actions simultaneous-event "
                    "delivery multiplicity is not represented.",
                )

        for minute in item.times:
            accumulated_masks[minute] = accumulated_masks.get(minute, 0) | date_mask


def install_schedule_occurrence_identity_hardening() -> None:
    """Install complete occurrence-overlap rejection after resource hardening."""
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
