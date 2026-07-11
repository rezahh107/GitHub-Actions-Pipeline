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
    install_calendar_bitsets,
    predicate_key,
    predicate_work_units,
)
from tools.ci_pinned_timezone import validate_pinned_timezone

CONTRACT_VERSION = "1.0.0"
WORKFLOW_LIMIT = 4096
REPOSITORY_LIMIT = 8192
_BASE_PARSE: Callable[..., object] | None = None
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


def _times(parsed: object) -> list[int]:
    return sorted(hour * 60 + minute for hour in parsed.hour.values for minute in parsed.minute.values)


def _charge(entry: object, workflow: _Ledger, repository: _Ledger) -> None:
    for ledger in (workflow, repository):
        ledger.charge(1, "reading a schedule entry")
    if not isinstance(entry, str):
        return
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
    for index, entry in enumerate(trigger["schedule"]):
        if not isinstance(entry, dict) or "cron" not in entry or any(
            key not in {"cron", "timezone"} for key in entry
        ):
            continue
        base = f"{reference}.schedule[{index}]"
        try:
            _charge(entry["cron"], workflow, repository)
            _schedule.validate_cron_expression(entry["cron"])
            if "timezone" in entry:
                timezone = entry["timezone"]
                if isinstance(timezone, str):
                    for ledger in (workflow, repository):
                        ledger.charge(4, "validating a distinct timezone", ("timezone", timezone))
                validate_pinned_timezone(timezone)
        except _semantics.ScheduleSemanticError as exc:
            field = "timezone" if exc.code.startswith("WORKFLOW_SCHEDULE_TIMEZONE") else "cron"
            diagnostics.append(_diagnostic(exc, f"{base}.{field}"))
            if exc.code == "WORKFLOW_SCHEDULE_SEMANTIC_WORK_LIMIT_EXCEEDED":
                break
    return diagnostics


def _parse_with_root(root: Path, path: Path):
    token = _CURRENT_ROOT.set(str(root.resolve()))
    try:
        return _BASE_PARSE(root, path)
    finally:
        _CURRENT_ROOT.reset(token)


def install_schedule_resource_hardening() -> None:
    global _BASE_PARSE
    install_calendar_bitsets()
    _semantics.validate_timezone_name = validate_pinned_timezone
    _schedule.validate_timezone_name = validate_pinned_timezone
    _schedule._schedule_errors = _schedule_errors
    if getattr(_structure.parse_workflow, "__schedule_resource_contract__", None) == CONTRACT_VERSION:
        return
    _BASE_PARSE = _structure.parse_workflow
    _parse_with_root.__schedule_resource_contract__ = CONTRACT_VERSION
    _structure.parse_workflow = _parse_with_root
