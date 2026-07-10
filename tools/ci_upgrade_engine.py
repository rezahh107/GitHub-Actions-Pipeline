"""Two-mode repository analysis and staged improvement engine."""

from __future__ import annotations

import hashlib
import os
from copy import deepcopy
from pathlib import Path
from typing import Mapping

from tools.ci_history_analysis import collect_structural_history
from tools.ci_models import canonical_json_bytes, normalize_generated_at
from tools.ci_profiles import (
    compose_profile_contributions,
    detect_profiles,
    load_profiles,
)
from tools.ci_recommendations import generate_recommendations
from tools.ci_repository_model import build_repository_model
from tools.ci_telemetry import (
    collect_github_telemetry,
    load_telemetry_snapshot,
    unavailable_telemetry,
)
from tools.ci_upgrade_models import (
    DEEP_REPOSITORY_UPGRADE,
    MINIMAL_SAFE_CI,
    diagnostic,
    get_policy,
)

UPGRADE_REPORT_VERSION = "1.0.0"
UPGRADE_CANONICALIZATION_VERSION = "1"
HASH_EXCLUDED_FIELDS = {"generated_at", "evidence_sha256", "run_context"}


def compute_upgrade_sha256(report: Mapping[str, object]) -> str:
    payload = deepcopy(dict(report))
    for field in HASH_EXCLUDED_FIELDS:
        payload.pop(field, None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _capability_map(model: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(item["capability_id"]): item
        for item in model.get("capabilities", [])
        if isinstance(item, dict) and item.get("capability_id")
    }


def _history_not_collected(reason: str) -> dict[str, object]:
    return {
        "status": "not_collected",
        "commit_limit": 0,
        "revert_chains": [],
        "co_change_pairs": [],
        "production_without_test_changes": [],
        "workflow_config_churn": [],
        "repeated_fix_subsystems": [],
        "diagnostics": [
            diagnostic(
                "STRUCTURAL_HISTORY_NOT_COLLECTED",
                reason,
                affected_area="history_analysis",
                repair_hint="Use --mode deep-repository-upgrade to collect bounded structural history.",
                severity="info",
            )
        ],
    }


def _cold_start_state(history: dict[str, object], model: dict[str, object]) -> dict[str, object]:
    status = history.get("status")
    commit_count = history.get("commit_count_analyzed")
    observed_signal_count = sum(
        len(history.get(key, []))
        for key in ("revert_chains", "repeated_fix_subsystems")
        if isinstance(history.get(key), list)
    )
    if status in {"unavailable", "not_collected"}:
        return {
            "status": "limited_history",
            "confidence_adjustment": "baseline and structural recommendations remain available; observed-failure confidence is unavailable",
            "not_yet_observed_is_not_not_needed": True,
        }
    if isinstance(commit_count, int) and commit_count < 10:
        return {
            "status": "cold_start",
            "confidence_adjustment": "historical recommendations require stronger direct evidence; profile and structural channels remain active",
            "not_yet_observed_is_not_not_needed": True,
        }
    if observed_signal_count == 0:
        return {
            "status": "no_recorded_failures",
            "confidence_adjustment": "absence of recorded regressions does not disable structural invariants or baseline capabilities",
            "not_yet_observed_is_not_not_needed": True,
        }
    return {
        "status": "history_informative",
        "confidence_adjustment": "observed, structural, and baseline channels can all contribute independently",
        "not_yet_observed_is_not_not_needed": True,
    }


def _testability_gaps(model: dict[str, object]) -> list[dict[str, object]]:
    capabilities = _capability_map(model)
    gaps: list[dict[str, object]] = []
    for capability_id in (
        "negative_parser_validator_tests",
        "tests_run_on_pull_requests",
        "generated_artifact_validation",
    ):
        item = capabilities.get(capability_id)
        if item and item.get("state") in {
            "absent",
            "nominal",
            "partial",
            "unknown",
            "operational_but_weak",
        }:
            gaps.append(
                {
                    "capability_id": capability_id,
                    "state": item["state"],
                    "evidence": item["evidence"],
                    "affected_conclusion": "The repository may lack a reliable machine-checkable oracle for this surface.",
                    "required_evidence_or_fixture": item.get(
                        "repair_hint",
                        "Provide an executable command and representative positive and negative fixtures.",
                    ),
                    "partial_processing_possible": True,
                }
            )
    return gaps


def _ci_blind_spots(model: dict[str, object], telemetry: dict[str, object]) -> list[dict[str, object]]:
    capabilities = _capability_map(model)
    blind_spots: list[dict[str, object]] = []
    descriptions = {
        "tests_run_on_pull_requests": "Behavioral regressions can merge without the canonical test suite executing.",
        "build_verified": "A declared production build can fail after unit tests pass.",
        "schema_validation": "Schema, producer, validator, and example drift can remain silent.",
        "release_artifact_validation": "Release artifacts can be incomplete or inconsistent with source metadata.",
        "generated_artifact_validation": "Committed generated outputs can drift from their source.",
    }
    for capability_id, description in descriptions.items():
        item = capabilities.get(capability_id)
        if item and item.get("state") not in {
            "operational",
            "not_applicable",
        }:
            blind_spots.append(
                {
                    "blind_spot_id": capability_id,
                    "capability_state": item["state"],
                    "description": description,
                    "evidence": item["evidence"],
                }
            )
    if telemetry.get("status") != "collected":
        blind_spots.append(
            {
                "blind_spot_id": "workflow_runtime_telemetry",
                "capability_state": "unknown",
                "description": "Recurring failures, skips, duration, and branch coverage cannot be established from local files alone.",
                "evidence": telemetry["evidence"],
            }
        )
    return sorted(blind_spots, key=lambda item: item["blind_spot_id"])


def _baseline_summary(model: dict[str, object]) -> dict[str, object]:
    capabilities = _capability_map(model)
    counts: dict[str, int] = {}
    for item in capabilities.values():
        state = str(item["state"])
        counts[state] = counts.get(state, 0) + 1
    return {
        "archetypes": model.get("repository_archetypes", []),
        "components": [
            item.get("component_id")
            for item in model.get("components", [])
            if isinstance(item, dict)
        ],
        "capability_state_counts": {
            key: counts[key] for key in sorted(counts)
        },
        "workflow_count": len(model.get("workflows", [])),
        "test_file_count": len(model.get("test_suites", {}).get("files", [])),
        "schema_count": len(model.get("schemas", [])),
    }


def _staged_upgrade(
    recommendations: dict[str, object],
    model: dict[str, object],
    history: dict[str, object],
    telemetry: dict[str, object],
    profile_contributions: dict[str, object],
) -> dict[str, object]:
    ranked = recommendations["ranked"]
    return {
        "current_engineering_baseline": _baseline_summary(model),
        "repository_model_summary": {
            "archetypes": model.get("repository_archetypes", []),
            "frameworks": model.get("frameworks", []),
            "components": model.get("components", []),
            "critical_execution_paths": model.get("critical_execution_paths", []),
        },
        "critical_unprotected_invariants": [
            {
                "recommendation_id": item["recommendation_id"],
                "invariant": item["protected_invariant"],
                "source": item["source"],
            }
            for item in ranked
            if item["decision"] in {"phase_1", "phase_2"}
        ],
        "observed_failures": recommendations["observed_failures"],
        "structural_invariants": recommendations["structural_invariants"],
        "baseline_capability_gaps": recommendations["baseline_capabilities"],
        "testability_gaps": _testability_gaps(model),
        "ci_blind_spots": _ci_blind_spots(model, telemetry),
        "ranked_high_leverage_improvements": ranked,
        "phase_1": [
            item for item in ranked if item["decision"] == "phase_1"
        ],
        "phase_2": [
            item for item in ranked if item["decision"] == "phase_2"
        ],
        "intentionally_uncovered": [
            {
                "area": exclusion,
                "reason": "Excluded by the composed capability profiles; no contrary repository evidence was found.",
            }
            for exclusion in profile_contributions.get("exclusions", [])
        ],
        "unresolved_evidence_limitations": [
            *history.get("diagnostics", []),
            *telemetry.get("diagnostics", []),
            *model.get("unresolved_evidence", []),
        ],
        "validation_and_measurement_plan": [
            "Run the full deterministic test suite and schema validation on the exact head SHA.",
            "Compare minimal and deep reports on the same fixture and timestamp.",
            "Confirm each Phase 1 item changes a capability state or adds a tested oracle.",
            "Track workflow duration and recurring failures only when telemetry is available.",
            "Reject recommendations whose evidence disappears or whose control duplicates an existing operational capability.",
        ],
    }


def build_upgrade_report(
    repo_root: Path,
    *,
    mode: str = MINIMAL_SAFE_CI,
    generated_at: str | None = None,
    repository: str | None = None,
    telemetry_json: Path | None = None,
    collect_telemetry: bool = False,
    environ: Mapping[str, str] | None = None,
    profile_catalog_path: Path | None = None,
) -> dict[str, object]:
    policy = get_policy(mode)
    environment = os.environ if environ is None else environ
    root = repo_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"repository root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"repository root is not a directory: {root}")

    model = build_repository_model(root)
    catalog = load_profiles(profile_catalog_path)
    matched_profiles = detect_profiles(model, catalog)
    profile_contributions = compose_profile_contributions(
        matched_profiles, catalog
    )

    history = (
        collect_structural_history(root)
        if policy.collect_history_structure
        else _history_not_collected(
            "Minimal Safe CI intentionally skips structural history analysis."
        )
    )

    resolved_repository = (
        repository
        or environment.get("GITHUB_REPOSITORY")
        or root.name
    )
    if telemetry_json is not None:
        telemetry = load_telemetry_snapshot(telemetry_json)
    elif (
        policy.collect_remote_telemetry
        and collect_telemetry
    ):
        telemetry = collect_github_telemetry(
            resolved_repository,
            token=environment.get("GITHUB_TOKEN"),
        )
    else:
        telemetry = unavailable_telemetry(
            "WORKFLOW_TELEMETRY_NOT_REQUESTED",
            "Workflow telemetry was not requested for this run.",
            "Pass --telemetry-json or --collect-telemetry in Deep Repository Upgrade mode.",
        )

    recommendations = generate_recommendations(
        model,
        history,
        telemetry,
        profile_contributions,
        mode=mode,
        max_phase_1_items=policy.max_phase_1_items,
    )
    cold_start = _cold_start_state(history, model)

    report: dict[str, object] = {
        "report_version": UPGRADE_REPORT_VERSION,
        "canonicalization_version": UPGRADE_CANONICALIZATION_VERSION,
        "generated_at": normalize_generated_at(generated_at, environment),
        "evidence_sha256": "",
        "repository": resolved_repository,
        "operating_mode": mode,
        "mode_policy": {
            "collect_history_structure": policy.collect_history_structure,
            "collect_remote_telemetry": policy.collect_remote_telemetry,
            "include_baseline_capabilities": policy.include_baseline_capabilities,
            "include_testability_gaps": policy.include_testability_gaps,
            "recommendation_scope": policy.recommendation_scope,
            "max_phase_1_items": policy.max_phase_1_items,
        },
        "repository_model": model,
        "profiles": {
            "matches": matched_profiles,
            "composition": profile_contributions,
        },
        "history_analysis": history,
        "workflow_telemetry": telemetry,
        "cold_start": cold_start,
        "recommendations": recommendations,
        "diagnostics": sorted(
            [
                *model.get("unresolved_evidence", []),
                *history.get("diagnostics", []),
                *telemetry.get("diagnostics", []),
                *[
                    item["diagnostic"]
                    for item in recommendations["ranked"]
                    if item["decision"] in {"phase_1", "phase_2", "deferred"}
                ],
            ],
            key=lambda item: (
                str(item.get("severity")),
                str(item.get("code")),
                str(item.get("message")),
            ),
        ),
    }

    if mode == MINIMAL_SAFE_CI:
        report["minimal_gate_plan"] = {
            "phase_1": [
                item
                for item in recommendations["ranked"]
                if item["decision"] == "phase_1"
            ],
            "deferred": [
                item
                for item in recommendations["ranked"]
                if item["decision"] in {"phase_2", "deferred"}
            ],
            "constraint": "Only strongly justified, low-noise, reversible controls are eligible.",
        }
    elif mode == DEEP_REPOSITORY_UPGRADE:
        report["deep_audit"] = {
            "executable_architecture": {
                "components": model.get("components", []),
                "entry_points": model.get("entry_points", []),
                "workflows": model.get("workflows", []),
                "critical_execution_paths": model.get("critical_execution_paths", []),
            },
            "principal_contracts": [
                *profile_contributions.get("structural_invariants", []),
                *[
                    item.get("rationale")
                    for item in model.get("relationships", [])
                    if isinstance(item, dict)
                ],
            ],
            "silent_or_late_failures": _ci_blind_spots(model, telemetry),
            "high_risk_without_oracle": _testability_gaps(model),
            "nominal_capabilities": [
                item
                for item in model.get("capabilities", [])
                if isinstance(item, dict)
                and item.get("state")
                in {"nominal", "partial", "operational_but_weak"}
            ],
            "current_ci_cannot_detect": _ci_blind_spots(model, telemetry),
            "testability_first": bool(_testability_gaps(model)),
            "decision_rationale": "Recommendations are independently sourced from observed failures, structural invariants, and profile baselines, then ranked with bounded ordinal factors.",
        }
        report["staged_upgrade"] = _staged_upgrade(
            recommendations,
            model,
            history,
            telemetry,
            profile_contributions,
        )

    report["evidence_sha256"] = compute_upgrade_sha256(report)
    return report
