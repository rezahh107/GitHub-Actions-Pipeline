#!/usr/bin/env python3
"""Offline renderer and structural checker for Scope Claim Audit packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

REQUIRED_TOP_LEVEL = [
    "schema_version",
    "target_repository",
    "pr_number",
    "reviewed_head_sha",
    "claim_sources",
    "deterministic_diff_facts",
    "sensitive_surfaces",
    "claim_classification",
    "scope_claim_result",
    "signal_confidence",
    "why_it_matters",
    "recommended_action",
    "enforcement_mode",
    "wired_enforcement_gate",
    "blocking",
    "limitations",
]

REQUIRED_DIFF_FIELDS = [
    "files_changed",
    "additions",
    "deletions",
    "changed_file_paths",
    "changed_file_statuses",
    "source_method",
    "source_limitations",
]

REQUIRED_SURFACE_FIELDS = [
    "protocol",
    "schema",
    "validator",
    "workflow",
    "release_lock",
    "package_metadata",
    "tests_fixtures",
    "generated_output",
    "docs",
    "scripts",
    "other",
]

REQUIRED_WIRED_GATE_FIELDS = [
    "target_repository",
    "gate_name",
    "workflow_path",
    "check_name",
    "enforcement_evidence",
    "policy_reference",
]

VALID_RESULTS = {
    "congruent",
    "scope_expanded_but_declared",
    "scope_underreported",
    "mismatch",
    "not_assessable",
}

VALID_ENFORCEMENT_MODES = {"advisory", "enforced"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read input file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("audit package must be a JSON object")
    return data


def require_keys(mapping: dict[str, Any], keys: list[str], context: str) -> None:
    missing = [key for key in keys if key not in mapping]
    if missing:
        raise ValueError(f"{context} missing required fields: {', '.join(missing)}")


def validate_enforcement_contract(data: dict[str, Any]) -> None:
    enforcement_mode = data["enforcement_mode"]
    wired_gate = data["wired_enforcement_gate"]
    blocking = data["blocking"]

    if enforcement_mode not in VALID_ENFORCEMENT_MODES:
        raise ValueError(f"invalid enforcement_mode: {enforcement_mode}")

    if enforcement_mode == "advisory":
        if blocking:
            raise ValueError("blocking=true requires enforcement_mode=enforced")
        if wired_gate is not None:
            raise ValueError("advisory packages must use wired_enforcement_gate=null")
        return

    if not isinstance(wired_gate, dict):
        raise ValueError("enforcement_mode=enforced requires a wired_enforcement_gate object")
    require_keys(wired_gate, REQUIRED_WIRED_GATE_FIELDS, "wired_enforcement_gate")
    for key in REQUIRED_WIRED_GATE_FIELDS:
        if not isinstance(wired_gate[key], str) or not wired_gate[key].strip():
            raise ValueError(f"wired_enforcement_gate.{key} must be a non-empty string")


def validate_package(data: dict[str, Any]) -> None:
    require_keys(data, REQUIRED_TOP_LEVEL, "top-level package")

    if data["scope_claim_result"] not in VALID_RESULTS:
        raise ValueError(f"invalid scope_claim_result: {data['scope_claim_result']}")
    if not isinstance(data["blocking"], bool):
        raise ValueError("blocking must be boolean")
    if not isinstance(data["reviewed_head_sha"], str) or not FULL_SHA_RE.fullmatch(data["reviewed_head_sha"]):
        raise ValueError("reviewed_head_sha must be a full 40-character lowercase hexadecimal SHA")
    validate_enforcement_contract(data)
    if not isinstance(data["claim_sources"], list) or not data["claim_sources"]:
        raise ValueError("claim_sources must be a non-empty array")
    for idx, source in enumerate(data["claim_sources"]):
        if not isinstance(source, dict):
            raise ValueError(f"claim_sources item at index {idx} must be an object")
    if not isinstance(data["deterministic_diff_facts"], dict):
        raise ValueError("deterministic_diff_facts must be an object")
    require_keys(data["deterministic_diff_facts"], REQUIRED_DIFF_FIELDS, "deterministic_diff_facts")
    if not isinstance(data["sensitive_surfaces"], dict):
        raise ValueError("sensitive_surfaces must be an object")
    require_keys(data["sensitive_surfaces"], REQUIRED_SURFACE_FIELDS, "sensitive_surfaces")
    if not isinstance(data["limitations"], list):
        raise ValueError("limitations must be an array")


def non_empty_surfaces(data: dict[str, Any]) -> list[str]:
    surfaces = data.get("sensitive_surfaces", {})
    return [name for name in REQUIRED_SURFACE_FIELDS if surfaces.get(name)]


def render_summary(data: dict[str, Any]) -> str:
    diff = data["deterministic_diff_facts"]
    claim_excerpt = data["claim_sources"][0].get("excerpt", "")
    surfaces = non_empty_surfaces(data)
    blocking_label = "yes" if data["blocking"] else "no"
    limitations = data.get("limitations", [])
    wired_gate = data.get("wired_enforcement_gate")

    lines = [
        "# Scope Claim Audit advisory summary",
        "",
        f"- Target repository: `{data['target_repository']}`",
        f"- PR number: `{data['pr_number']}`",
        f"- Reviewed head SHA: `{data['reviewed_head_sha']}`",
        f"- Claim excerpt: {claim_excerpt}",
        f"- Files changed: {diff['files_changed']}",
        f"- Additions/deletions: +{diff['additions']} / -{diff['deletions']}",
        f"- Sensitive surfaces: {', '.join(surfaces) if surfaces else 'none recorded'}",
        f"- Scope claim result: `{data['scope_claim_result']}`",
        f"- Signal confidence: `{data['signal_confidence']}`",
        f"- Enforcement mode: `{data['enforcement_mode']}`",
        f"- Blocking: `{blocking_label}`",
    ]
    if wired_gate:
        lines.extend([
            f"- Wired gate: `{wired_gate['gate_name']}`",
            f"- Check name: `{wired_gate['check_name']}`",
        ])
    lines.extend([
        "",
        "## Why it matters",
        data["why_it_matters"],
        "",
        "## Recommended action",
        data["recommended_action"],
    ])
    if limitations:
        lines.extend(["", "## Limitations", *[f"- {item}" for item in limitations]])
    lines.append("")
    return "\n".join(lines)


def run_check(path: Path) -> int:
    data = load_json(path)
    validate_package(data)
    print(
        f"Scope Claim Audit package OK: {path} "
        f"result={data['scope_claim_result']} "
        f"enforcement_mode={data['enforcement_mode']} "
        f"blocking={data['blocking']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and render an offline Scope Claim Audit package.")
    parser.add_argument("--input", help="Path to Scope Claim Audit JSON package")
    parser.add_argument("--out", help="Path to write Markdown advisory summary")
    parser.add_argument("--check", help="Validate package structure and print a concise result")
    args = parser.parse_args(argv)

    try:
        if args.check:
            return run_check(Path(args.check))
        if not args.input or not args.out:
            parser.error("use either --check PATH or --input PATH --out PATH")
        data = load_json(Path(args.input))
        validate_package(data)
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_summary(data), encoding="utf-8")
        print(f"Wrote Scope Claim Audit summary to {output}")
        return 0
    except ValueError as exc:
        print(f"scope_claim_audit error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
