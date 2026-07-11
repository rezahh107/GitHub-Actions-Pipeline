"""Versioned nested GitHub Actions structure gate for command evidence."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import yaml

from tools import ci_workflow_structure as _structure
from tools.ci_repository_collectors import GitHubWorkflowLoader, PERMISSION_SCOPES, PERMISSION_VALUES, _text, rel

WORKFLOW_NESTED_SCHEMA_CONTRACT_VERSION = "1.0.0"

# Every admitted first-level property has exactly one validation rule. Rules that
# are scalar still appear here so property-set drift is machine-detectable.
NESTED_SCHEMA_COVERAGE_MAP: dict[str, dict[str, str]] = {
    "workflow": {
        "name": "string", "run-name": "string", "on": "triggers",
        "permissions": "permissions", "env": "scalar_map", "defaults": "defaults",
        "concurrency": "concurrency", "jobs": "jobs",
    },
    "normal_job": {
        "name": "string", "permissions": "permissions", "needs": "string_or_list",
        "if": "condition", "runs-on": "runs_on", "snapshot": "snapshot",
        "environment": "environment", "concurrency": "concurrency",
        "outputs": "scalar_map", "env": "scalar_map", "defaults": "defaults",
        "steps": "steps", "timeout-minutes": "positive_int_or_expression",
        "strategy": "strategy", "continue-on-error": "bool_or_expression",
        "container": "container", "services": "services",
    },
    "reusable_job": {
        "name": "string", "permissions": "permissions", "needs": "string_or_list",
        "if": "condition", "strategy": "strategy", "concurrency": "concurrency",
        "uses": "string", "with": "scalar_map", "secrets": "reusable_secrets",
    },
    "step": {
        "id": "string", "if": "condition", "name": "string", "uses": "string",
        "run": "string", "working-directory": "string", "shell": "string",
        "with": "scalar_map", "env": "scalar_map",
        "continue-on-error": "bool_or_expression",
        "timeout-minutes": "positive_int_or_expression",
        "background": "bool_or_expression", "wait": "string", "wait-all": "null",
        "cancel": "string", "parallel": "parallel_steps",
    },
}

_KNOWN_RULES = frozenset({
    "string", "triggers", "permissions", "scalar_map", "defaults", "concurrency",
    "jobs", "string_or_list", "condition", "runs_on", "snapshot", "environment",
    "steps", "positive_int_or_expression", "strategy", "bool_or_expression",
    "container", "services", "reusable_secrets", "null", "parallel_steps",
})
_EXPR = re.compile(r"^\s*\$\{\{.*\}\}\s*$", re.DOTALL)
_TRIGGER_FILTER_KEYS = frozenset({"branches", "branches-ignore", "tags", "tags-ignore", "paths", "paths-ignore", "types", "workflows"})
_STRATEGY_KEYS = frozenset({"matrix", "fail-fast", "max-parallel"})
_DEFAULTS_KEYS = frozenset({"run"})
_DEFAULTS_RUN_KEYS = frozenset({"shell", "working-directory"})
_CONCURRENCY_KEYS = frozenset({"group", "cancel-in-progress", "queue"})
_ENVIRONMENT_KEYS = frozenset({"name", "url", "deployment"})
_SNAPSHOT_KEYS = frozenset({"image-name", "version", "if"})
_RUNS_ON_KEYS = frozenset({"group", "labels"})
_CONTAINER_KEYS = frozenset({"image", "credentials", "env", "ports", "volumes", "options"})
_SERVICE_KEYS = frozenset(set(_CONTAINER_KEYS) | {"command", "entrypoint"})
_CREDENTIAL_KEYS = frozenset({"username", "password"})


def _diag(code: str, ref: str, message: str) -> dict[str, object]:
    return _structure._diagnostic(code, f"{message} Nested schema contract {WORKFLOW_NESTED_SCHEMA_CONTRACT_VERSION} rejected the workflow before command parsing.", reference=ref)


def _bad(code: str, ref: str, message: str) -> list[dict[str, object]]:
    return [_diag(code, ref, message)]


def _string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _expression(value: object) -> bool:
    return isinstance(value, str) and bool(_EXPR.match(value))


def _scalar(value: object) -> bool:
    return value is not None and isinstance(value, (str, int, float, bool))


def _unknown(value: dict[object, object], allowed: frozenset[str]) -> list[object]:
    return [key for key in value if not isinstance(key, str) or key not in allowed]


def _scalar_map(value: object, ref: str, code: str = "WORKFLOW_NESTED_VALUE_INVALID") -> list[dict[str, object]]:
    if not isinstance(value, dict) or any(not _string(k) or not _scalar(v) for k, v in value.items()):
        return _bad(code, ref, f"{ref} must be a mapping of non-empty string keys to scalar values.")
    return []


def _string_list(value: object, ref: str, code: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value or not all(_string(item) for item in value):
        return _bad(code, ref, f"{ref} must be a non-empty list of strings.")
    return []


def _bool_expr(value: object, ref: str, code: str) -> list[dict[str, object]]:
    return [] if isinstance(value, bool) or _expression(value) else _bad(code, ref, f"{ref} must be boolean or an explicit expression.")


def _positive_int_expr(value: object, ref: str, code: str) -> list[dict[str, object]]:
    valid = isinstance(value, int) and not isinstance(value, bool) and value > 0
    return [] if valid or _expression(value) else _bad(code, ref, f"{ref} must be a positive integer or explicit expression.")


def _permissions(value: object, ref: str) -> list[dict[str, object]]:
    if isinstance(value, str) and value in {"read-all", "write-all"}: return []
    if not isinstance(value, dict): return _bad("WORKFLOW_PERMISSION_STRUCTURE_INVALID", ref, f"{ref} must be a permission mapping or supported shorthand.")
    invalid = [k for k, v in value.items() if k not in PERMISSION_SCOPES or v not in PERMISSION_VALUES]
    return _bad("WORKFLOW_PERMISSION_STRUCTURE_INVALID", ref, f"{ref} contains unsupported permission entries: {invalid!r}.") if invalid else []


def _triggers(value: object, ref: str) -> list[dict[str, object]]:
    if _string(value): return []
    if isinstance(value, list): return _string_list(value, ref, "WORKFLOW_TRIGGER_STRUCTURE_INVALID")
    if not isinstance(value, dict) or not value: return _bad("WORKFLOW_TRIGGER_STRUCTURE_INVALID", ref, f"{ref} must be a trigger name, list, or mapping.")
    out: list[dict[str, object]] = []
    for event, config in value.items():
        eref = f"{ref}.{event}"
        if not _string(event): out += _bad("WORKFLOW_TRIGGER_STRUCTURE_INVALID", eref, f"{eref} has an invalid event name."); continue
        if config is None: continue
        if event == "schedule":
            if not isinstance(config, list) or not config or any(not isinstance(x, dict) or set(x) != {"cron"} or not _string(x.get("cron")) for x in config):
                out += _bad("WORKFLOW_TRIGGER_STRUCTURE_INVALID", eref, f"{eref} must be a non-empty list of cron mappings.")
            continue
        if event in {"workflow_dispatch", "workflow_call"}:
            if not isinstance(config, dict): out += _bad("WORKFLOW_TRIGGER_STRUCTURE_INVALID", eref, f"{eref} must be a mapping or null.")
            elif any(k not in {"inputs", "outputs", "secrets"} for k in config): out += _bad("WORKFLOW_TRIGGER_STRUCTURE_INVALID", eref, f"{eref} contains unsupported properties.")
            elif any(not isinstance(v, dict) for v in config.values()): out += _bad("WORKFLOW_TRIGGER_STRUCTURE_INVALID", eref, f"{eref} nested definitions must be mappings.")
            continue
        if not isinstance(config, dict): out += _bad("WORKFLOW_TRIGGER_STRUCTURE_INVALID", eref, f"{eref} must be a mapping or null."); continue
        unknown = _unknown(config, _TRIGGER_FILTER_KEYS)
        if unknown: out += _bad("WORKFLOW_TRIGGER_STRUCTURE_INVALID", eref, f"{eref} contains unsupported properties: {unknown!r}."); continue
        for key, item in config.items(): out += _string_list(item, f"{eref}.{key}", "WORKFLOW_TRIGGER_STRUCTURE_INVALID")
    return out


def _defaults(value: object, ref: str) -> list[dict[str, object]]:
    if not isinstance(value, dict) or set(value) != _DEFAULTS_KEYS or not isinstance(value.get("run"), dict):
        return _bad("WORKFLOW_DEFAULTS_STRUCTURE_INVALID", ref, f"{ref} must contain only a run mapping.")
    run = value["run"]; unknown = _unknown(run, _DEFAULTS_RUN_KEYS)
    if unknown or not run: return _bad("WORKFLOW_DEFAULTS_STRUCTURE_INVALID", f"{ref}.run", f"{ref}.run contains unsupported or no properties: {unknown!r}.")
    return [] if all(_string(v) for v in run.values()) else _bad("WORKFLOW_DEFAULTS_STRUCTURE_INVALID", f"{ref}.run", f"{ref}.run values must be non-empty strings.")


def _concurrency(value: object, ref: str) -> list[dict[str, object]]:
    if _string(value): return []
    if not isinstance(value, dict): return _bad("WORKFLOW_CONCURRENCY_STRUCTURE_INVALID", ref, f"{ref} must be a string or mapping.")
    unknown = _unknown(value, _CONCURRENCY_KEYS)
    if unknown or "group" not in value or not _string(value.get("group")):
        return _bad("WORKFLOW_CONCURRENCY_STRUCTURE_INVALID", ref, f"{ref} requires group and contains no unsupported properties: {unknown!r}.")
    out = _bool_expr(value["cancel-in-progress"], f"{ref}.cancel-in-progress", "WORKFLOW_CONCURRENCY_STRUCTURE_INVALID") if "cancel-in-progress" in value else []
    if "queue" in value and value["queue"] not in {"single", "max"}: out += _bad("WORKFLOW_CONCURRENCY_STRUCTURE_INVALID", f"{ref}.queue", f"{ref}.queue must be single or max.")
    if value.get("queue") == "max" and value.get("cancel-in-progress") is True: out += _bad("WORKFLOW_CONCURRENCY_STRUCTURE_INVALID", ref, f"{ref} cannot combine queue: max with cancel-in-progress: true.")
    return out


def _runs_on(value: object, ref: str) -> list[dict[str, object]]:
    if _string(value): return []
    if isinstance(value, list): return _string_list(value, ref, "WORKFLOW_RUNS_ON_STRUCTURE_INVALID")
    if not isinstance(value, dict) or not value: return _bad("WORKFLOW_RUNS_ON_STRUCTURE_INVALID", ref, f"{ref} must be a string, list, or group/labels mapping.")
    unknown = _unknown(value, _RUNS_ON_KEYS)
    if unknown: return _bad("WORKFLOW_RUNS_ON_STRUCTURE_INVALID", ref, f"{ref} contains unsupported properties: {unknown!r}.")
    out = []
    if "group" in value and not _string(value["group"]): out += _bad("WORKFLOW_RUNS_ON_STRUCTURE_INVALID", f"{ref}.group", f"{ref}.group must be a string.")
    if "labels" in value and not (_string(value["labels"]) or isinstance(value["labels"], list) and value["labels"] and all(_string(x) for x in value["labels"])): out += _bad("WORKFLOW_RUNS_ON_STRUCTURE_INVALID", f"{ref}.labels", f"{ref}.labels must be a string or string list.")
    return out


def _named_mapping(value: object, ref: str, allowed: frozenset[str], required: str, code: str) -> list[dict[str, object]]:
    if _string(value): return []
    if not isinstance(value, dict): return _bad(code, ref, f"{ref} must be a string or mapping.")
    unknown = _unknown(value, allowed)
    if unknown or required not in value or not _string(value.get(required)): return _bad(code, ref, f"{ref} requires {required} and contains unsupported properties: {unknown!r}.")
    out = []
    for k, v in value.items():
        if k in {required, "url", "version"} and not _string(v): out += _bad(code, f"{ref}.{k}", f"{ref}.{k} must be a string.")
        elif k == "if" and not (isinstance(v, bool) or _string(v)): out += _bad(code, f"{ref}.if", f"{ref}.if must be boolean or condition string.")
        elif k == "deployment": out += _bool_expr(v, f"{ref}.deployment", code)
    return out


def _matrix(value: object, ref: str) -> list[dict[str, object]]:
    if _expression(value): return []
    if not isinstance(value, dict) or not value: return _bad("WORKFLOW_STRATEGY_STRUCTURE_INVALID", ref, f"{ref} must be a non-empty mapping or expression.")
    out = []
    for key, item in value.items():
        kref = f"{ref}.{key}"
        if not _string(key): out += _bad("WORKFLOW_STRATEGY_STRUCTURE_INVALID", kref, f"{kref} has an invalid key."); continue
        if key in {"include", "exclude"}:
            if not isinstance(item, list) or not item or any(not isinstance(x, dict) or not x or any(not _string(k) or not _scalar(v) for k, v in x.items()) for x in item): out += _bad("WORKFLOW_STRATEGY_STRUCTURE_INVALID", kref, f"{kref} must be a non-empty list of scalar mappings.")
        elif not isinstance(item, list) or not item or any(not (_scalar(x) or isinstance(x, dict) and x and all(_string(k) and _scalar(v) for k, v in x.items())) for x in item): out += _bad("WORKFLOW_STRATEGY_STRUCTURE_INVALID", kref, f"{kref} must be a non-empty list of scalar values or scalar mappings.")
    return out


def _strategy(value: object, ref: str) -> list[dict[str, object]]:
    if not isinstance(value, dict) or not value: return _bad("WORKFLOW_STRATEGY_STRUCTURE_INVALID", ref, f"{ref} must be a non-empty mapping.")
    unknown = _unknown(value, _STRATEGY_KEYS)
    if unknown: return _bad("WORKFLOW_STRATEGY_STRUCTURE_INVALID", ref, f"{ref} contains unsupported properties: {unknown!r}.")
    out = _matrix(value["matrix"], f"{ref}.matrix") if "matrix" in value else []
    if "fail-fast" in value: out += _bool_expr(value["fail-fast"], f"{ref}.fail-fast", "WORKFLOW_STRATEGY_STRUCTURE_INVALID")
    if "max-parallel" in value: out += _positive_int_expr(value["max-parallel"], f"{ref}.max-parallel", "WORKFLOW_STRATEGY_STRUCTURE_INVALID")
    return out


def _container_map(value: object, ref: str, service: bool) -> list[dict[str, object]]:
    code = "WORKFLOW_SERVICES_STRUCTURE_INVALID" if service else "WORKFLOW_CONTAINER_STRUCTURE_INVALID"
    allowed = _SERVICE_KEYS if service else _CONTAINER_KEYS
    if not isinstance(value, dict): return _bad(code, ref, f"{ref} must be a mapping.")
    unknown = _unknown(value, allowed)
    if unknown or "image" not in value or not _string(value.get("image")): return _bad(code, ref, f"{ref} requires image and contains unsupported properties: {unknown!r}.")
    out = []
    if "credentials" in value:
        creds = value["credentials"]
        if not isinstance(creds, dict) or set(creds) != _CREDENTIAL_KEYS or not all(_string(x) for x in creds.values()): out += _bad(code, f"{ref}.credentials", f"{ref}.credentials must contain string username and password.")
    if "env" in value: out += _scalar_map(value["env"], f"{ref}.env", code)
    for key in ("ports", "volumes"):
        if key in value and (not isinstance(value[key], list) or not value[key] or any(not isinstance(x, (str, int)) or isinstance(x, bool) for x in value[key])): out += _bad(code, f"{ref}.{key}", f"{ref}.{key} must be a non-empty scalar list.")
    for key in ("options", "command", "entrypoint"):
        if key in value and not _string(value[key]): out += _bad(code, f"{ref}.{key}", f"{ref}.{key} must be a string.")
    return out


def _services(value: object, ref: str) -> list[dict[str, object]]:
    if not isinstance(value, dict): return _bad("WORKFLOW_SERVICES_STRUCTURE_INVALID", ref, f"{ref} must be a service mapping.")
    out = []
    for key, item in value.items():
        sref = f"{ref}.{key}"
        if not _string(key): out += _bad("WORKFLOW_SERVICES_STRUCTURE_INVALID", sref, f"{sref} has an invalid service identifier.")
        else: out += _container_map(item, sref, True)
    return out


def _coverage(ref: str) -> list[dict[str, object]]:
    expected = {"workflow": _structure.WORKFLOW_ROOT_ALLOWED_PROPERTIES, "normal_job": _structure.NORMAL_JOB_ALLOWED_PROPERTIES, "reusable_job": _structure.REUSABLE_JOB_ALLOWED_PROPERTIES, "step": _structure.STEP_ALLOWED_PROPERTIES}
    problems = []
    for surface, allowed in expected.items():
        mapped = set(NESTED_SCHEMA_COVERAGE_MAP.get(surface, {})); rules = set(NESTED_SCHEMA_COVERAGE_MAP.get(surface, {}).values())
        if mapped != set(allowed) or not rules <= _KNOWN_RULES: problems.append(f"{surface}: missing={sorted(set(allowed)-mapped)!r}, extra={sorted(mapped-set(allowed))!r}, unknown_rules={sorted(rules-_KNOWN_RULES)!r}")
    return _bad("WORKFLOW_NESTED_SCHEMA_COVERAGE_GAP", ref, "; ".join(problems)) if problems else []


def _rule(rule: str, value: object, ref: str) -> list[dict[str, object]]:
    if rule == "string": return [] if _string(value) else _bad("WORKFLOW_NESTED_VALUE_INVALID", ref, f"{ref} must be a non-empty string.")
    if rule == "condition": return [] if isinstance(value, bool) or _string(value) else _bad("WORKFLOW_NESTED_VALUE_INVALID", ref, f"{ref} must be boolean or condition string.")
    if rule == "bool_or_expression": return _bool_expr(value, ref, "WORKFLOW_NESTED_VALUE_INVALID")
    if rule == "positive_int_or_expression": return _positive_int_expr(value, ref, "WORKFLOW_NESTED_VALUE_INVALID")
    if rule == "string_or_list": return [] if _string(value) else _string_list(value, ref, "WORKFLOW_NESTED_VALUE_INVALID")
    if rule == "scalar_map": return _scalar_map(value, ref)
    if rule == "permissions": return _permissions(value, ref)
    if rule == "triggers": return _triggers(value, ref)
    if rule == "defaults": return _defaults(value, ref)
    if rule == "concurrency": return _concurrency(value, ref)
    if rule == "runs_on": return _runs_on(value, ref)
    if rule == "snapshot": return _named_mapping(value, ref, _SNAPSHOT_KEYS, "image-name", "WORKFLOW_SNAPSHOT_STRUCTURE_INVALID")
    if rule == "environment": return _named_mapping(value, ref, _ENVIRONMENT_KEYS, "name", "WORKFLOW_ENVIRONMENT_STRUCTURE_INVALID")
    if rule == "strategy": return _strategy(value, ref)
    if rule == "container": return [] if _string(value) else _container_map(value, ref, False)
    if rule == "services": return _services(value, ref)
    if rule == "reusable_secrets": return [] if value == "inherit" else _scalar_map(value, ref, "WORKFLOW_REUSABLE_SECRET_STRUCTURE_INVALID")
    if rule == "null": return [] if value is None else _bad("WORKFLOW_STEP_NESTED_STRUCTURE_INVALID", ref, f"{ref} must be null.")
    return []


def _step(step: dict[object, object], ref: str) -> list[dict[str, object]]:
    out = []
    for key, rule in NESTED_SCHEMA_COVERAGE_MAP["step"].items():
        if key not in step: continue
        if rule == "parallel_steps":
            items = step[key]
            if not isinstance(items, list) or not items: out += _bad("WORKFLOW_STEP_NESTED_STRUCTURE_INVALID", f"{ref}.parallel", f"{ref}.parallel must be a non-empty step list.")
            else:
                for index, item in enumerate(items):
                    iref = f"{ref}.parallel[{index}]"
                    if not isinstance(item, dict): out += _bad("WORKFLOW_STEP_NESTED_STRUCTURE_INVALID", iref, f"{iref} must be a step mapping.")
                    else: out += _step(item, iref)
        else: out += _rule(rule, step[key], f"{ref}.{key}")
    return out


def validate_nested_workflow_structure(data: object, *, reference: str) -> list[dict[str, object]]:
    out = _coverage(reference)
    if out or not isinstance(data, dict): return out
    for key, rule in NESTED_SCHEMA_COVERAGE_MAP["workflow"].items():
        if key not in data: continue
        ref = f"{reference}.{key}"
        if rule == "jobs":
            jobs = data[key]
            if not isinstance(jobs, dict) or not jobs: out += _bad("WORKFLOW_NESTED_VALUE_INVALID", ref, f"{ref} must be a non-empty job mapping."); continue
            for job_id, job in jobs.items():
                jref = f"{reference}#jobs.{job_id}"
                if not _string(job_id) or not isinstance(job, dict): out += _bad("WORKFLOW_NESTED_VALUE_INVALID", jref, f"{jref} must be a named job mapping."); continue
                surface = "reusable_job" if "uses" in job else "normal_job"
                for prop, prop_rule in NESTED_SCHEMA_COVERAGE_MAP[surface].items():
                    if prop not in job: continue
                    pref = f"{jref}.{prop}"
                    if prop_rule == "steps":
                        steps = job[prop]
                        if not isinstance(steps, list): out += _bad("WORKFLOW_NESTED_VALUE_INVALID", pref, f"{pref} must be a step list.")
                        else:
                            for index, step in enumerate(steps):
                                sref = f"{pref}[{index}]"
                                if not isinstance(step, dict): out += _bad("WORKFLOW_NESTED_VALUE_INVALID", sref, f"{sref} must be a step mapping.")
                                else: out += _step(step, sref)
                    else: out += _rule(prop_rule, job[prop], pref)
        else: out += _rule(rule, data[key], ref)
    return out


_BASE_PARSE: Callable[..., object] | None = None


def _patched_parse_workflow(root: Path, path: Path):
    reference = rel(root, path); text = _text(path, root)
    if text is None: return _BASE_PARSE(root, path)
    try:
        composed = yaml.compose(text, Loader=GitHubWorkflowLoader)
        if composed is not None:
            merge_ref = _structure._merge_key_reference(composed, reference)
            if merge_ref is not None: return _BASE_PARSE(root, path)
        data = yaml.load(text, Loader=GitHubWorkflowLoader)
    except yaml.YAMLError:
        return _BASE_PARSE(root, path)
    diagnostics = _structure.validate_workflow_structure(data, reference=reference)
    if not diagnostics: diagnostics = validate_nested_workflow_structure(data, reference=reference)
    if diagnostics:
        return _structure._invalid_workflow(reference), sorted(diagnostics, key=lambda item: (str(item["code"]), str(item["message"])))
    return _BASE_PARSE(root, path)


def install_workflow_nested_validation() -> None:
    global _BASE_PARSE
    if getattr(_structure.parse_workflow, "__nested_schema_contract__", None) == WORKFLOW_NESTED_SCHEMA_CONTRACT_VERSION: return
    _BASE_PARSE = _structure.parse_workflow
    _patched_parse_workflow.__nested_schema_contract__ = WORKFLOW_NESTED_SCHEMA_CONTRACT_VERSION
    _structure.parse_workflow = _patched_parse_workflow
