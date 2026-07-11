"""Install fail-closed semantic validation for represented schedules."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import yaml

from tools import ci_workflow_nested_patch as _nested
from tools import ci_workflow_structure as _structure
from tools.ci_repository_collectors import GitHubWorkflowLoader, _text, rel
from tools.ci_schedule_semantics import (
    SCHEDULE_SEMANTICS_CONTRACT_VERSION,
    ScheduleSemanticError,
    validate_cron_expression,
    validate_timezone_name,
)

_BASE_PARSE: Callable[..., object] | None = None
_BASE_NESTED_TRIGGERS: Callable[..., list[dict[str, object]]] | None = None


def _diagnostic(code: str, reference: str, message: str) -> dict[str, object]:
    return _structure._diagnostic(
        code,
        (
            f"{message} Schedule semantics contract "
            f"{SCHEDULE_SEMANTICS_CONTRACT_VERSION} rejected the workflow before "
            "permissions, jobs, conditions, or command parsing."
        ),
        reference=reference,
    )


def _schedule_errors(trigger: object, *, reference: str) -> list[dict[str, object]]:
    if not isinstance(trigger, dict) or "schedule" not in trigger:
        return []
    schedule = trigger["schedule"]
    if not isinstance(schedule, list):
        return []

    diagnostics: list[dict[str, object]] = []
    for index, entry in enumerate(schedule):
        entry_reference = f"{reference}.schedule[{index}]"
        if (
            not isinstance(entry, dict)
            or "cron" not in entry
            or any(key not in {"cron", "timezone"} for key in entry)
        ):
            continue
        try:
            validate_cron_expression(entry["cron"])
        except ScheduleSemanticError as exc:
            diagnostics.append(
                _diagnostic(exc.code, f"{entry_reference}.cron", exc.message)
            )
        if "timezone" in entry:
            try:
                validate_timezone_name(entry["timezone"])
            except ScheduleSemanticError as exc:
                diagnostics.append(
                    _diagnostic(exc.code, f"{entry_reference}.timezone", exc.message)
                )
    return diagnostics


def _nested_triggers_with_schedule_timezone(
    value: object,
    ref: str,
) -> list[dict[str, object]]:
    if not isinstance(value, dict) or "schedule" not in value:
        return _BASE_NESTED_TRIGGERS(value, ref)

    remaining = {key: item for key, item in value.items() if key != "schedule"}
    diagnostics = _BASE_NESTED_TRIGGERS(remaining, ref) if remaining else []
    schedule = value["schedule"]
    schedule_ref = f"{ref}.schedule"
    if not isinstance(schedule, list) or not schedule:
        diagnostics += _nested._bad(
            "WORKFLOW_TRIGGER_STRUCTURE_INVALID",
            schedule_ref,
            f"{schedule_ref} must be a non-empty list of cron mappings.",
        )
        return diagnostics

    for index, entry in enumerate(schedule):
        entry_ref = f"{schedule_ref}[{index}]"
        if not isinstance(entry, dict):
            diagnostics += _nested._bad(
                "WORKFLOW_TRIGGER_STRUCTURE_INVALID",
                entry_ref,
                f"{entry_ref} must be a cron mapping.",
            )
            continue
        unknown = [
            key
            for key in entry
            if not isinstance(key, str) or key not in {"cron", "timezone"}
        ]
        if unknown or "cron" not in entry or not _nested._string(entry.get("cron")):
            diagnostics += _nested._bad(
                "WORKFLOW_TRIGGER_STRUCTURE_INVALID",
                entry_ref,
                f"{entry_ref} requires a string cron and contains no unsupported properties: {unknown!r}.",
            )
            continue
        if "timezone" in entry and not _nested._string(entry["timezone"]):
            diagnostics += _nested._bad(
                "WORKFLOW_TRIGGER_STRUCTURE_INVALID",
                f"{entry_ref}.timezone",
                f"{entry_ref}.timezone must be a non-empty string.",
            )
    return diagnostics


def _install_nested_schedule_timezone_compatibility() -> None:
    global _BASE_NESTED_TRIGGERS
    if (
        getattr(_nested._triggers, "__schedule_timezone_contract__", None)
        == SCHEDULE_SEMANTICS_CONTRACT_VERSION
    ):
        return
    _BASE_NESTED_TRIGGERS = _nested._triggers
    _nested_triggers_with_schedule_timezone.__schedule_timezone_contract__ = (
        SCHEDULE_SEMANTICS_CONTRACT_VERSION
    )
    _nested._triggers = _nested_triggers_with_schedule_timezone


def _patched_parse_workflow(root: Path, path: Path):
    reference, text = rel(root, path), _text(path, root)
    if text is None:
        return _BASE_PARSE(root, path)
    try:
        data = yaml.load(text, Loader=GitHubWorkflowLoader)
    except yaml.YAMLError:
        return _BASE_PARSE(root, path)

    diagnostics = (
        _schedule_errors(data["on"], reference=f"{reference}.on")
        if isinstance(data, dict) and "on" in data
        else []
    )
    if diagnostics:
        return _structure._invalid_workflow(reference), sorted(
            diagnostics,
            key=lambda item: (str(item["code"]), str(item["message"])),
        )
    return _BASE_PARSE(root, path)


def install_workflow_schedule_validation() -> None:
    global _BASE_PARSE
    _install_nested_schedule_timezone_compatibility()
    if (
        getattr(_structure.parse_workflow, "__schedule_semantics_contract__", None)
        == SCHEDULE_SEMANTICS_CONTRACT_VERSION
    ):
        return
    _BASE_PARSE = _structure.parse_workflow
    _patched_parse_workflow.__schedule_semantics_contract__ = (
        SCHEDULE_SEMANTICS_CONTRACT_VERSION
    )
    _structure.parse_workflow = _patched_parse_workflow
