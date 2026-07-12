"""Fail-closed structural validation for GitHub Actions workflow evidence.

This module is intentionally narrower than the GitHub Actions service parser. It
accepts only versioned workflow, job, and step property sets that are represented
by the repository's static evidence model. Any structural uncertainty blocks the
entire workflow from contributing resolved command families.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from tools.ci_repository_collectors import (
    GitHubWorkflowLoader,
    _text,
    parse_workflow as _parse_workflow,
    rel,
)
from tools.ci_upgrade_models import diagnostic

WORKFLOW_STRUCTURE_CONTRACT_VERSION = "1.0.0"

WORKFLOW_ROOT_ALLOWED_PROPERTIES = frozenset({
    "name",
    "run-name",
    "on",
    "permissions",
    "env",
    "defaults",
    "concurrency",
    "jobs",
})

NORMAL_JOB_ALLOWED_PROPERTIES = frozenset({
    "name",
    "permissions",
    "needs",
    "if",
    "runs-on",
    "snapshot",
    "environment",
    "concurrency",
    "outputs",
    "env",
    "defaults",
    "steps",
    "timeout-minutes",
    "strategy",
    "continue-on-error",
    "container",
    "services",
})

REUSABLE_JOB_ALLOWED_PROPERTIES = frozenset({
    "name",
    "permissions",
    "needs",
    "if",
    "strategy",
    "concurrency",
    "uses",
    "with",
    "secrets",
})

STEP_ALLOWED_PROPERTIES = frozenset({
    "id",
    "if",
    "name",
    "uses",
    "run",
    "working-directory",
    "shell",
    "with",
    "env",
    "continue-on-error",
    "timeout-minutes",
    "background",
    "wait",
    "wait-all",
    "cancel",
    "parallel",
})

_STEP_EXECUTION_PROPERTIES = frozenset({"uses", "run", "wait", "wait-all", "cancel", "parallel"})
_MERGE_TAG = "tag:yaml.org,2002:merge"
_MAX_COMPOSED_NODES = 50_000


def _diagnostic(
    code: str,
    message: str,
    *,
    reference: str,
) -> dict[str, object]:
    return diagnostic(
        code,
        f"{message} Structural contract {WORKFLOW_STRUCTURE_CONTRACT_VERSION} rejected the workflow before command parsing.",
        affected_area="workflow_structure",
        evidence_references=[reference],
        repair_hint="Use only supported GitHub Actions workflow, job, and step properties and execution forms; do not use YAML merge keys for executable evidence.",
        severity="warning",
    )


def _format_properties(values: Iterable[object]) -> str:
    return ", ".join(sorted(repr(value) for value in values))


def _merge_key_reference(node: Node, root_reference: str) -> str | None:
    stack: list[tuple[Node, str]] = [(node, root_reference)]
    seen: set[int] = set()
    visited = 0
    while stack:
        current, reference = stack.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        visited += 1
        if visited > _MAX_COMPOSED_NODES:
            return f"{root_reference}#yaml-node-limit"
        if isinstance(current, MappingNode):
            for key_node, value_node in current.value:
                key_value = key_node.value if isinstance(key_node, ScalarNode) else "<non-scalar-key>"
                child_reference = f"{reference}.{key_value}"
                if key_node.tag == _MERGE_TAG or key_value == "<<":
                    return child_reference
                stack.append((value_node, child_reference))
        elif isinstance(current, SequenceNode):
            for index, child in enumerate(current.value):
                stack.append((child, f"{reference}[{index}]"))
    return None


def _unknown_properties(
    container: dict[object, object],
    allowed: frozenset[str],
) -> list[object]:
    return [key for key in container if not isinstance(key, str) or key not in allowed]


def _validate_step(
    step: dict[object, object],
    *,
    reference: str,
    allow_parallel: bool = True,
) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    unknown = _unknown_properties(step, STEP_ALLOWED_PROPERTIES)
    if unknown:
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_PROPERTY_UNSUPPORTED",
            f"Step {reference} contains unsupported properties: {_format_properties(unknown)}.",
            reference=reference,
        ))
        return diagnostics

    forms = sorted(key for key in _STEP_EXECUTION_PROPERTIES if key in step)
    if len(forms) != 1:
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
            f"Step {reference} must contain exactly one execution property; observed {forms!r}.",
            reference=reference,
        ))
        return diagnostics

    form = forms[0]
    if not allow_parallel and form not in {"run", "uses"}:
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
            f"Parallel entry {reference} must use run or uses; observed {form!r}.",
            reference=reference,
        ))
        return diagnostics
    if not allow_parallel and "background" in step:
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
            f"Parallel entry {reference} cannot declare background because parallel supplies that execution mode.",
            reference=reference,
        ))
    if "background" in step and form not in {"run", "uses"}:
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
            f"Step {reference} uses background without run or uses.",
            reference=reference,
        ))
    if "working-directory" in step and form != "run":
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
            f"Step {reference} uses working-directory without run.",
            reference=reference,
        ))
    if "shell" in step and form != "run":
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
            f"Step {reference} uses shell without run.",
            reference=reference,
        ))
    if "with" in step and form != "uses":
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
            f"Step {reference} uses with without uses.",
            reference=reference,
        ))
    if form in {"wait", "wait-all", "cancel"} and "if" in step:
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
            f"Step {reference} uses if on an always-running {form} step.",
            reference=reference,
        ))

    if form == "wait-all" and step.get("wait-all") is not None:
        diagnostics.append(_diagnostic(
            "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
            f"Step {reference} gives wait-all an argument even though it takes none.",
            reference=reference,
        ))
    if form == "parallel":
        nested = step.get("parallel")
        if not isinstance(nested, list) or not nested:
            diagnostics.append(_diagnostic(
                "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
                f"Step {reference} must provide a non-empty parallel step list.",
                reference=reference,
            ))
        else:
            for index, item in enumerate(nested):
                nested_reference = f"{reference}.parallel[{index}]"
                if not isinstance(item, dict):
                    diagnostics.append(_diagnostic(
                        "WORKFLOW_STEP_EXECUTION_FORM_INVALID",
                        f"Parallel entry {nested_reference} must be a mapping.",
                        reference=nested_reference,
                    ))
                    continue
                diagnostics.extend(_validate_step(item, reference=nested_reference, allow_parallel=False))
    return diagnostics


def validate_workflow_structure(
    data: object,
    *,
    reference: str,
) -> list[dict[str, object]]:
    if not isinstance(data, dict):
        return []

    root_unknown = _unknown_properties(data, WORKFLOW_ROOT_ALLOWED_PROPERTIES)
    if root_unknown:
        return [_diagnostic(
            "WORKFLOW_ROOT_PROPERTY_UNSUPPORTED",
            f"Workflow {reference} contains unsupported root properties: {_format_properties(root_unknown)}.",
            reference=reference,
        )]

    raw_jobs = data.get("jobs")
    if not isinstance(raw_jobs, dict):
        return []

    diagnostics: list[dict[str, object]] = []
    for job_id, raw_job in sorted(raw_jobs.items(), key=lambda pair: str(pair[0])):
        job_reference = f"{reference}#jobs.{job_id}"
        if not isinstance(raw_job, dict):
            continue
        reusable = "uses" in raw_job
        allowed = REUSABLE_JOB_ALLOWED_PROPERTIES if reusable else NORMAL_JOB_ALLOWED_PROPERTIES
        unknown = _unknown_properties(raw_job, allowed)
        if unknown:
            diagnostics.append(_diagnostic(
                "WORKFLOW_REUSABLE_JOB_PROPERTY_UNSUPPORTED" if reusable else "WORKFLOW_NORMAL_JOB_PROPERTY_UNSUPPORTED",
                f"Job {job_reference} contains unsupported properties: {_format_properties(unknown)}.",
                reference=job_reference,
            ))
            continue
        if reusable:
            continue
        raw_steps = raw_job.get("steps")
        if not isinstance(raw_steps, list):
            continue
        for index, raw_step in enumerate(raw_steps):
            step_reference = f"{job_reference}.steps[{index}]"
            if not isinstance(raw_step, dict):
                continue
            diagnostics.extend(_validate_step(raw_step, reference=step_reference))
    return diagnostics


def _invalid_workflow(reference: str) -> dict[str, object]:
    return {
        "path": reference,
        "parse_status": "invalid_shape",
        "name": None,
        "triggers": [],
        "permissions": None,
        "permission_declaration": {
            "presence": "missing",
            "form": "malformed",
            "values": {},
            "source": f"{reference}#permissions",
            "supported": False,
            "reason": "Workflow structure failed before permission evaluation.",
        },
        "jobs": [],
        "commands": [],
        "command_evidence": [],
    }


def parse_workflow(
    root: Path,
    path: Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Validate workflow structure before delegating to command extraction."""
    reference = rel(root, path)
    text = _text(path, root)
    if text is None:
        return _parse_workflow(root, path)
    try:
        composed = yaml.compose(text, Loader=GitHubWorkflowLoader)
        if composed is not None:
            merge_reference = _merge_key_reference(composed, reference)
            if merge_reference is not None:
                item = _diagnostic(
                    "WORKFLOW_YAML_MERGE_KEY_UNSUPPORTED",
                    f"Workflow {reference} uses a YAML merge key at {merge_reference}.",
                    reference=merge_reference,
                )
                return _invalid_workflow(reference), [item]
        data = yaml.load(text, Loader=GitHubWorkflowLoader)
    except yaml.YAMLError:
        return _parse_workflow(root, path)

    diagnostics = validate_workflow_structure(data, reference=reference)
    if diagnostics:
        return _invalid_workflow(reference), sorted(
            diagnostics,
            key=lambda item: (str(item["code"]), str(item["message"])),
        )
    return _parse_workflow(root, path)
