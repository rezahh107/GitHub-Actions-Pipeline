"""Fail-closed, event-specific GitHub Actions trigger validation."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import yaml

from tools import ci_workflow_structure as _structure
from tools.ci_repository_collectors import GitHubWorkflowLoader, _text, rel

WORKFLOW_TRIGGER_SCHEMA_CONTRACT_VERSION = "1.0.0"

PR_ACTIVITIES = frozenset({
    "assigned", "unassigned", "labeled", "unlabeled", "opened", "edited",
    "closed", "reopened", "synchronize", "converted_to_draft", "locked",
    "unlocked", "enqueued", "dequeued", "milestoned", "demilestoned",
    "ready_for_review", "review_requested", "review_request_removed",
    "auto_merge_enabled", "auto_merge_disabled",
})
WORKFLOW_RUN_ACTIVITIES = frozenset({"completed", "requested", "in_progress"})

EVENT_TRIGGER_SCHEMA_REGISTRY: dict[str, dict[str, object]] = {
    "push": {"form": "push"},
    "pull_request": {"form": "pull_request", "activities": PR_ACTIVITIES},
    "pull_request_target": {"form": "pull_request", "activities": PR_ACTIVITIES},
    "workflow_run": {"form": "workflow_run", "activities": WORKFLOW_RUN_ACTIVITIES},
    "repository_dispatch": {"form": "repository_dispatch"},
    "workflow_dispatch": {"form": "workflow_dispatch"},
    "workflow_call": {"form": "workflow_call"},
    "schedule": {"form": "schedule"},
    "branch_protection_rule": {
        "form": "types_only", "activities": frozenset({"created", "edited", "deleted"}),
    },
    "watch": {"form": "types_only", "activities": frozenset({"started"})},
    "fork": {"form": "null_only"},
    "gollum": {"form": "null_only"},
    "page_build": {"form": "null_only"},
    "public": {"form": "null_only"},
    "status": {"form": "null_only"},
}

MAX_ITEMS = 256
DISPATCH_TYPES = frozenset({"boolean", "choice", "number", "environment", "string"})
CALL_TYPES = frozenset({"boolean", "number", "string"})


def _diag(code: str, ref: str, message: str) -> dict[str, object]:
    return _structure._diagnostic(
        code,
        f"{message} Trigger schema contract {WORKFLOW_TRIGGER_SCHEMA_CONTRACT_VERSION} rejected the workflow before permissions, jobs, conditions, or command parsing.",
        reference=ref,
    )


def _bad(code: str, ref: str, message: str) -> list[dict[str, object]]:
    return [_diag(code, ref, message)]


def _string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unknown(value: dict[object, object], allowed: frozenset[str]) -> list[object]:
    return [key for key in value if not isinstance(key, str) or key not in allowed]


def _mapping(value: object, ref: str, allowed: frozenset[str]):
    if not isinstance(value, dict):
        return None, _bad("WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID", ref, f"{ref} must be a mapping or null.")
    unknown = _unknown(value, allowed)
    if unknown:
        return None, _bad("WORKFLOW_TRIGGER_PROPERTY_UNSUPPORTED", ref, f"{ref} contains unsupported properties: {sorted(map(repr, unknown))!r}.")
    return value, []


def _strings(value: object, ref: str, code: str = "WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID"):
    if not isinstance(value, list) or not value or len(value) > MAX_ITEMS or not all(_string(item) for item in value):
        return _bad(code, ref, f"{ref} must be a non-empty bounded list of strings.")
    return []


def _activities(value: object, ref: str, allowed: frozenset[str]):
    errors = _strings(value, ref, "WORKFLOW_TRIGGER_ACTIVITY_INVALID")
    if errors:
        return errors
    unsupported = sorted(set(value) - allowed)  # type: ignore[arg-type]
    return _bad("WORKFLOW_TRIGGER_ACTIVITY_INVALID", ref, f"{ref} contains unsupported activity values: {unsupported!r}.") if unsupported else []


def _conflicts(value: dict[object, object], ref: str, pairs: tuple[tuple[str, str], ...]):
    found = [(left, right) for left, right in pairs if left in value and right in value]
    return _bad("WORKFLOW_TRIGGER_FILTER_CONFLICT", ref, f"{ref} combines mutually exclusive filters: {found!r}.") if found else []


def _filters(value: object, ref: str, allowed: frozenset[str], pairs: tuple[tuple[str, str], ...], activities=None):
    if value is None:
        return []
    config, errors = _mapping(value, ref, allowed)
    if errors:
        return errors
    assert config is not None
    errors += _conflicts(config, ref, pairs)
    for key, item in config.items():
        errors += _activities(item, f"{ref}.{key}", activities) if key == "types" else _strings(item, f"{ref}.{key}")
    return errors


def _push(value, ref, schema):
    return _filters(
        value, ref,
        frozenset({"branches", "branches-ignore", "tags", "tags-ignore", "paths", "paths-ignore"}),
        (("branches", "branches-ignore"), ("tags", "tags-ignore"), ("paths", "paths-ignore")),
    )


def _pull_request(value, ref, schema):
    return _filters(
        value, ref,
        frozenset({"branches", "branches-ignore", "paths", "paths-ignore", "types"}),
        (("branches", "branches-ignore"), ("paths", "paths-ignore")),
        schema["activities"],
    )


def _workflow_run(value, ref, schema):
    if value is None:
        return _bad("WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID", ref, f"{ref} requires workflows.")
    config, errors = _mapping(value, ref, frozenset({"workflows", "types", "branches", "branches-ignore"}))
    if errors:
        return errors
    assert config is not None
    if "workflows" not in config:
        errors += _bad("WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID", ref, f"{ref} requires workflows.")
    errors += _conflicts(config, ref, (("branches", "branches-ignore"),))
    for key, item in config.items():
        errors += _activities(item, f"{ref}.{key}", schema["activities"]) if key == "types" else _strings(item, f"{ref}.{key}")
    return errors


def _repository_dispatch(value, ref, schema):
    if value is None:
        return []
    config, errors = _mapping(value, ref, frozenset({"types"}))
    if errors or not config:
        return errors
    errors += _strings(config["types"], f"{ref}.types")
    if not errors and any(len(item) > 100 for item in config["types"]):
        errors += _bad("WORKFLOW_TRIGGER_ACTIVITY_INVALID", f"{ref}.types", "repository_dispatch type values must not exceed 100 characters.")
    return errors


def _default_matches(value: object, kind: str) -> bool:
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, str)


def _dispatch_input(name: object, value: object, ref: str):
    allowed = frozenset({"description", "type", "required", "default", "options"})
    if not _string(name) or not isinstance(value, dict):
        return _bad("WORKFLOW_DISPATCH_INPUT_INVALID", ref, f"{ref} must be a named input mapping.")
    unknown, kind = _unknown(value, allowed), value.get("type", "string")
    if unknown or kind not in DISPATCH_TYPES:
        return _bad("WORKFLOW_DISPATCH_INPUT_INVALID", ref, f"{ref} has unsupported properties or type: {unknown!r}, {kind!r}.")
    errors = []
    if "description" in value and not isinstance(value["description"], str):
        errors += _bad("WORKFLOW_DISPATCH_INPUT_INVALID", f"{ref}.description", "description must be a string.")
    if "required" in value and not isinstance(value["required"], bool):
        errors += _bad("WORKFLOW_DISPATCH_INPUT_INVALID", f"{ref}.required", "required must be boolean.")
    options = value.get("options")
    if kind == "choice":
        if not isinstance(options, list) or not options or len(options) > MAX_ITEMS or not all(_string(item) for item in options) or len(set(options)) != len(options):
            errors += _bad("WORKFLOW_DISPATCH_INPUT_INVALID", f"{ref}.options", "choice options must be a non-empty bounded list of unique strings.")
    elif "options" in value:
        errors += _bad("WORKFLOW_DISPATCH_INPUT_INVALID", f"{ref}.options", "options are valid only for choice inputs.")
    if "default" in value:
        default = value["default"]
        if not _default_matches(default, kind):
            errors += _bad("WORKFLOW_DISPATCH_INPUT_INVALID", f"{ref}.default", f"default does not match {kind!r}.")
        elif kind == "choice" and isinstance(options, list) and default not in options:
            errors += _bad("WORKFLOW_DISPATCH_INPUT_INVALID", f"{ref}.default", "choice default must be one of options.")
    return errors


def _workflow_dispatch(value, ref, schema):
    if value is None:
        return []
    config, errors = _mapping(value, ref, frozenset({"inputs"}))
    if errors or not config:
        return errors
    inputs = config.get("inputs")
    if not isinstance(inputs, dict) or len(inputs) > 25:
        return _bad("WORKFLOW_DISPATCH_INPUT_INVALID", f"{ref}.inputs", "inputs must be a mapping with at most 25 entries.")
    for name, item in inputs.items():
        errors += _dispatch_input(name, item, f"{ref}.inputs.{name}")
    return errors


def _call_input(name: object, value: object, ref: str):
    allowed = frozenset({"description", "type", "required", "default"})
    if not _string(name) or not isinstance(value, dict):
        return _bad("WORKFLOW_CALL_INPUT_INVALID", ref, f"{ref} must be a named input mapping.")
    unknown, kind = _unknown(value, allowed), value.get("type")
    if unknown or kind not in CALL_TYPES:
        return _bad("WORKFLOW_CALL_INPUT_INVALID", ref, f"{ref} requires a supported type and no unknown properties: {unknown!r}, {kind!r}.")
    errors = []
    if "description" in value and not isinstance(value["description"], str):
        errors += _bad("WORKFLOW_CALL_INPUT_INVALID", f"{ref}.description", "description must be a string.")
    if "required" in value and not isinstance(value["required"], bool):
        errors += _bad("WORKFLOW_CALL_INPUT_INVALID", f"{ref}.required", "required must be boolean.")
    if "default" in value and not _default_matches(value["default"], kind):
        errors += _bad("WORKFLOW_CALL_INPUT_INVALID", f"{ref}.default", f"default does not match {kind!r}.")
    return errors


def _call_secret(name: object, value: object, ref: str):
    allowed = frozenset({"description", "required"})
    if not _string(name) or not isinstance(value, dict) or _unknown(value, allowed):
        return _bad("WORKFLOW_CALL_SECRET_INVALID", ref, f"{ref} must be a supported secret mapping.")
    errors = []
    if "description" in value and not isinstance(value["description"], str):
        errors += _bad("WORKFLOW_CALL_SECRET_INVALID", f"{ref}.description", "description must be a string.")
    if "required" in value and not isinstance(value["required"], bool):
        errors += _bad("WORKFLOW_CALL_SECRET_INVALID", f"{ref}.required", "required must be boolean.")
    return errors


def _call_output(name: object, value: object, ref: str):
    allowed = frozenset({"description", "value"})
    if not _string(name) or not isinstance(value, dict) or _unknown(value, allowed) or "value" not in value:
        return _bad("WORKFLOW_CALL_OUTPUT_INVALID", ref, f"{ref} must be a supported output mapping with value.")
    errors = []
    if "description" in value and not isinstance(value["description"], str):
        errors += _bad("WORKFLOW_CALL_OUTPUT_INVALID", f"{ref}.description", "description must be a string.")
    if not _string(value["value"]):
        errors += _bad("WORKFLOW_CALL_OUTPUT_INVALID", f"{ref}.value", "value must be a non-empty string.")
    return errors


def _workflow_call(value, ref, schema):
    if value is None:
        return []
    config, errors = _mapping(value, ref, frozenset({"inputs", "outputs", "secrets"}))
    if errors:
        return errors
    validators = {"inputs": (_call_input, "WORKFLOW_CALL_INPUT_INVALID"), "secrets": (_call_secret, "WORKFLOW_CALL_SECRET_INVALID"), "outputs": (_call_output, "WORKFLOW_CALL_OUTPUT_INVALID")}
    for section, definitions in config.items():
        validator, code = validators[section]
        if not isinstance(definitions, dict):
            errors += _bad(code, f"{ref}.{section}", f"{ref}.{section} must be a mapping.")
            continue
        for name, item in definitions.items():
            errors += validator(name, item, f"{ref}.{section}.{name}")
    return errors


def _schedule(value, ref, schema):
    if not isinstance(value, list) or not value or len(value) > MAX_ITEMS:
        return _bad("WORKFLOW_SCHEDULE_STRUCTURE_INVALID", ref, f"{ref} must be a non-empty bounded list.")
    errors = []
    for index, item in enumerate(value):
        item_ref = f"{ref}[{index}]"
        if not isinstance(item, dict):
            errors += _bad("WORKFLOW_SCHEDULE_STRUCTURE_INVALID", item_ref, "schedule entry must be a mapping.")
            continue
        unknown = _unknown(item, frozenset({"cron", "timezone"}))
        if unknown or not _string(item.get("cron")):
            errors += _bad("WORKFLOW_SCHEDULE_STRUCTURE_INVALID", item_ref, f"schedule entry requires cron and no unknown properties: {unknown!r}.")
        if "timezone" in item and not _string(item["timezone"]):
            errors += _bad("WORKFLOW_SCHEDULE_STRUCTURE_INVALID", f"{item_ref}.timezone", "timezone must be a non-empty string.")
    return errors


def _null_only(value, ref, schema):
    return [] if value is None else _bad("WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID", ref, f"{ref} supports only null shorthand.")


def _types_only(value, ref, schema):
    if value is None:
        return []
    config, errors = _mapping(value, ref, frozenset({"types"}))
    if errors or not config:
        return errors
    return _activities(config["types"], f"{ref}.types", schema["activities"])


_TRIGGER_FORM_HANDLERS: dict[str, Callable[..., list[dict[str, object]]]] = {
    "push": _push,
    "pull_request": _pull_request,
    "workflow_run": _workflow_run,
    "repository_dispatch": _repository_dispatch,
    "workflow_dispatch": _workflow_dispatch,
    "workflow_call": _workflow_call,
    "schedule": _schedule,
    "null_only": _null_only,
    "types_only": _types_only,
}


def _coverage(ref: str):
    forms = {schema.get("form") for schema in EVENT_TRIGGER_SCHEMA_REGISTRY.values() if isinstance(schema, dict)}
    missing = sorted(form for form in forms if form not in _TRIGGER_FORM_HANDLERS)
    malformed = sorted(event for event, schema in EVENT_TRIGGER_SCHEMA_REGISTRY.items() if not _string(event) or not isinstance(schema, dict) or not _string(schema.get("form")))
    return _bad("WORKFLOW_TRIGGER_SCHEMA_COVERAGE_GAP", ref, f"registry coverage incomplete: missing={missing!r}, malformed={malformed!r}.") if missing or malformed else []


def _event(event: object, value: object, ref: str):
    if not _string(event) or event not in EVENT_TRIGGER_SCHEMA_REGISTRY:
        return _bad("WORKFLOW_TRIGGER_EVENT_UNSUPPORTED", ref, f"unsupported event: {event!r}.")
    schema = EVENT_TRIGGER_SCHEMA_REGISTRY[event]
    handler = _TRIGGER_FORM_HANDLERS.get(schema["form"])
    return handler(value, ref, schema) if handler else _bad("WORKFLOW_TRIGGER_SCHEMA_COVERAGE_GAP", ref, f"no handler for {schema['form']!r}.")


def validate_trigger_structure(trigger: object, *, reference: str):
    errors = _coverage(reference)
    if errors:
        return errors
    if _string(trigger):
        return _event(trigger, None, f"{reference}.{trigger}")
    if isinstance(trigger, list):
        if not trigger or len(trigger) > MAX_ITEMS or len(set(trigger)) != len(trigger):
            return _bad("WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID", reference, "event list must be non-empty, bounded, and duplicate-free.")
        for event in trigger:
            errors += _event(event, None, f"{reference}.{event}")
        return errors
    if not isinstance(trigger, dict) or not trigger:
        return _bad("WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID", reference, "on must be a supported event name, list, or non-empty mapping.")
    for event, value in trigger.items():
        errors += _event(event, value, f"{reference}.{event}")
    return errors


_BASE_PARSE: Callable[..., object] | None = None


def _patched_parse_workflow(root: Path, path: Path):
    reference, text = rel(root, path), _text(path, root)
    if text is None:
        return _BASE_PARSE(root, path)
    try:
        data = yaml.load(text, Loader=GitHubWorkflowLoader)
    except yaml.YAMLError:
        return _BASE_PARSE(root, path)
    errors = (
        validate_trigger_structure(data["on"], reference=f"{reference}.on")
        if isinstance(data, dict) and "on" in data
        else _bad("WORKFLOW_TRIGGER_EVENT_STRUCTURE_INVALID", f"{reference}.on", f"{reference} must declare on.")
    )
    if errors:
        return _structure._invalid_workflow(reference), sorted(errors, key=lambda item: (str(item["code"]), str(item["message"])))
    return _BASE_PARSE(root, path)


def install_workflow_trigger_validation() -> None:
    global _BASE_PARSE
    if getattr(_structure.parse_workflow, "__trigger_schema_contract__", None) == WORKFLOW_TRIGGER_SCHEMA_CONTRACT_VERSION:
        return
    _BASE_PARSE = _structure.parse_workflow
    _patched_parse_workflow.__trigger_schema_contract__ = WORKFLOW_TRIGGER_SCHEMA_CONTRACT_VERSION
    _structure.parse_workflow = _patched_parse_workflow
