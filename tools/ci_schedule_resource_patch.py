"""Install deterministic timezone identity and cumulative schedule work budgets."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from tools import ci_schedule_semantics as _semantics
from tools import ci_workflow_schedule_patch as _schedule
from tools import ci_workflow_structure as _structure
from tools.ci_calendar_bitsets import (
    adjacent_date_masks,
    install_calendar_bitsets,
    matching_dates,
    predicate_key,
    predicate_work_units,
)
from tools.ci_pinned_timezone import (
    validate_fixed_offset_timezone,
    validate_pinned_timezone,
)

CONTRACT_VERSION = "1.2.0"
WORKFLOW_LIMIT = 4096
REPOSITORY_LIMIT = 8192
TRANSITION_PROOF_WORK_UNITS = 64
_BASE_PARSE: Callable[..., object] | None = None
_BASE_BUILD_REPOSITORY_MODEL: Callable[..., dict[str, object]] | None = None
_CURRENT_ROOT: ContextVar[str | None] = ContextVar("schedule_current_root", default=None)


@dataclass
class _Ledger:
    scope: str
    limit: int
    used: int = 0
    seen: set[tuple[object, ...]] = field(default_factory=set)

    def charge(self, units: int, reason: str, key: tuple[object, ...] | None = None) -> None:
        if key is not None and key in self.seen:
            return
        if self.used + units > self.limit:
            raise _semantics.ScheduleSemanticError(
                "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED",
                f"{self.scope} semantic-work limit {self.limit} would be exceeded while {reason}; used={self.used}, requested={units}.",
            )
        self.used += units
        if key is not None:
            self.seen.add(key)


@dataclass
class _RepoState:
    root: str
    last_reference: str
    ledger: _Ledger


@dataclass(frozen=True)
class _CanonicalSchedule:
    timezone: str
    times: tuple[int, ...]
    predicate: tuple[object, ...]


_STATE: ContextVar[_RepoState | None] = ContextVar("schedule_repository_budget", default=None)


def _repo_ledger(reference: str) -> _Ledger:
    root = _CURRENT_ROOT.get() or "<unknown-root>"
    state = _STATE.get()
    if state is None or state.root != root or reference <= state.last_reference:
        state = _RepoState(root, reference, _Ledger("repository", REPOSITORY_LIMIT))
    else:
        state.last_reference = reference
    _STATE.set(state)
    return state.ledger


def _times(parsed: object) -> tuple[int, ...]:
    return tuple(sorted(hour * 60 + minute for hour in parsed.hour.values for minute in parsed.minute.values))


def _charge(entry: object, workflow: _Ledger, repository: _Ledger) -> object | None:
    for ledger in (workflow, repository):
        ledger.charge(1, "reading a schedule entry")
    if not isinstance(entry, str):
        return None
    parsed = _semantics.parse_cron_expression(entry)
    for ledger in (workflow, repository):
        ledger.charge(8 + len(entry), "parsing a distinct cron", ("cron", entry))
    times = _times(parsed)
    if 1440 - times[-1] + times[0] < _semantics.MINIMUM_INTERVAL_MINUTES:
        key = predicate_key(parsed)
        for ledger in (workflow, repository):
            ledger.charge(
                predicate_work_units(key),
                "evaluating a distinct Gregorian predicate",
                ("predicate",) + key,
            )
    return parsed


def _canonical_schedule(parsed: object, timezone: str) -> _CanonicalSchedule:
    return _CanonicalSchedule(
        timezone=timezone,
        times=_times(parsed),
        predicate=predicate_key(parsed),
    )


def _charge_comparison(workflow: _Ledger, repository: _Ledger, reason: str) -> None:
    for ledger in (workflow, repository):
        ledger.charge(1, reason)


def _require_fixed_offset_aggregate_timezone(
    timezone: str,
    workflow: _Ledger,
    repository: _Ledger,
) -> None:
    for ledger in (workflow, repository):
        ledger.charge(
            TRANSITION_PROOF_WORK_UNITS,
            "loading and verifying pinned timezone transition data",
            ("fixed-offset-transition-proof", timezone),
        )
    validate_fixed_offset_timezone(timezone)


def _aggregate_interval(schedules: list[_CanonicalSchedule], workflow: _Ledger, repository: _Ledger) -> int | None:
    """Return the minimum sub-five-minute gap over the union of all schedules."""
    if not schedules:
        return None
    timezones = sorted({item.timezone for item in schedules})
    if len(timezones) != 1:
        raise _semantics.ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_TIMEZONE_SET_UNSUPPORTED",
            "Multiple schedule timezones cannot be compared on one deterministic timeline; "
            f"observed {timezones!r}.",
        )

    # A single entry remains valid in any pinned IANA timezone because no aggregate
    # comparison is required. Every multi-entry set, including semantic duplicates,
    # must prove that its exact pinned TZif bytes are transition-free before local
    # minute masks can safely represent an absolute timeline.
    if len(schedules) > 1:
        _require_fixed_offset_aggregate_timezone(timezones[0], workflow, repository)

    unique = sorted(
        set(schedules),
        key=lambda item: (item.timezone, item.times, item.predicate),
    )
    occurrence_masks: dict[int, int] = {}
    for item in unique:
        for ledger in (workflow, repository):
            ledger.charge(
                predicate_work_units(item.predicate),
                "evaluating a distinct Gregorian predicate",
                ("predicate",) + item.predicate,
            )
            ledger.charge(
                len(item.times),
                "projecting a distinct schedule into aggregate occurrence times",
                ("aggregate-schedule", item.timezone, item.times, item.predicate),
            )
        date_mask = matching_dates(item.predicate)
        for minute in item.times:
            occurrence_masks[minute] = occurrence_masks.get(minute, 0) | date_mask

    times = sorted(occurrence_masks)
    available = set(times)
    for interval in range(1, _semantics.MINIMUM_INTERVAL_MINUTES):
        for left in times:
            target = left + interval
            if target < 1440:
                if target not in available:
                    continue
                _charge_comparison(
                    workflow, repository, "comparing aggregate same-day occurrences"
                )
                if occurrence_masks[left] & occurrence_masks[target]:
                    return interval
                continue

            right = target - 1440
            if right not in available:
                continue
            _charge_comparison(
                workflow, repository, "comparing aggregate cross-midnight occurrences"
            )
            if adjacent_date_masks(occurrence_masks[left], occurrence_masks[right]):
                return interval
    return None


def _validate_aggregate(schedules: list[_CanonicalSchedule], workflow: _Ledger, repository: _Ledger) -> None:
    interval = _aggregate_interval(schedules, workflow, repository)
    if interval is not None:
        raise _semantics.ScheduleSemanticError(
            "WORKFLOW_SCHEDULE_INTERVAL_TOO_FREQUENT",
            f"the union of schedule entries can run {interval} minute(s) apart; "
            f"the minimum supported interval is {_semantics.MINIMUM_INTERVAL_MINUTES} minutes.",
        )


def _diagnostic(exc: _semantics.ScheduleSemanticError, reference: str) -> dict[str, object]:
    return _structure._diagnostic(
        exc.code,
        f"{exc.message} Schedule resource contract {CONTRACT_VERSION} rejected the workflow before command evidence.",
        reference=reference,
    )


def _schedule_errors(trigger: object, *, reference: str) -> list[dict[str, object]]:
    if not isinstance(trigger, dict) or not isinstance(trigger.get("schedule"), list):
        return []
    workflow = _Ledger("workflow", WORKFLOW_LIMIT)
    repository = _repo_ledger(reference)
    diagnostics: list[dict[str, object]] = []
    canonical: list[_CanonicalSchedule] = []
    structural_incomplete = False
    for index, entry in enumerate(trigger["schedule"]):
        if not isinstance(entry, dict) or "cron" not in entry or any(
            key not in {"cron", "timezone"} for key in entry
        ):
            structural_incomplete = True
            continue
        base = f"{reference}.schedule[{index}]"
        try:
            parsed = _charge(entry["cron"], workflow, repository)
            _schedule.validate_cron_expression(entry["cron"])
            timezone = entry.get("timezone", "UTC")
            if "timezone" in entry:
                if isinstance(timezone, str):
                    for ledger in (workflow, repository):
                        ledger.charge(4, "validating a distinct timezone", ("timezone", timezone))
                validate_pinned_timezone(timezone)
            if parsed is not None and isinstance(timezone, str):
                canonical.append(_canonical_schedule(parsed, timezone))
        except _semantics.ScheduleSemanticError as exc:
            field = "timezone" if exc.code.startswith("WORKFLOW_SCHEDULE_TIMEZONE") else "cron"
            diagnostics.append(_diagnostic(exc, f"{base}.{field}"))
            if exc.code == "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED":
                break

    if diagnostics:
        return diagnostics
    if structural_incomplete:
        return []
    try:
        _validate_aggregate(canonical, workflow, repository)
    except _semantics.ScheduleSemanticError as exc:
        diagnostics.append(_diagnostic(exc, f"{reference}.schedule"))
    return diagnostics


def _parse_with_root(root: Path, path: Path):
    token = _CURRENT_ROOT.set(str(root.resolve()))
    try:
        return _BASE_PARSE(root, path)
    finally:
        _CURRENT_ROOT.reset(token)


def _build_with_fresh_repository_budget(root: Path) -> dict[str, object]:
    token = _STATE.set(None)
    try:
        return _BASE_BUILD_REPOSITORY_MODEL(root)
    finally:
        _STATE.reset(token)


def _install_repository_budget_scope() -> None:
    global _BASE_BUILD_REPOSITORY_MODEL
    from tools import ci_repository_model as _model

    if (
        getattr(_model.build_repository_model, "__schedule_resource_contract__", None)
        == CONTRACT_VERSION
    ):
        return
    _BASE_BUILD_REPOSITORY_MODEL = _model.build_repository_model
    _build_with_fresh_repository_budget.__schedule_resource_contract__ = CONTRACT_VERSION
    _model.build_repository_model = _build_with_fresh_repository_budget


def install_schedule_resource_hardening() -> None:
    global _BASE_PARSE
    install_calendar_bitsets()
    _semantics.validate_timezone_name = validate_pinned_timezone
    _schedule.validate_timezone_name = validate_pinned_timezone
    _schedule._schedule_errors = _schedule_errors
    if getattr(_structure.parse_workflow, "__schedule_resource_contract__", None) != CONTRACT_VERSION:
        _BASE_PARSE = _structure.parse_workflow
        _parse_with_root.__schedule_resource_contract__ = CONTRACT_VERSION
        _structure.parse_workflow = _parse_with_root
    _install_repository_budget_scope()
