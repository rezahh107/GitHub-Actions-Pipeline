"""Composable capability-profile loading, detection, and contribution merging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from tools.ci_upgrade_models import UpgradeContractError, evidence


def _profile_path(root: Path | None = None) -> Path:
    if root is not None:
        return root
    return Path(__file__).resolve().parents[1] / "profiles" / "capability-profiles.v1.json"


def load_profiles(path: Path | None = None) -> dict[str, object]:
    profile_path = _profile_path(path)
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UpgradeContractError(
            "PROFILE_CATALOG_UNAVAILABLE",
            f"Could not read capability profile catalog {profile_path}: {exc}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise UpgradeContractError(
            "PROFILE_CATALOG_INVALID_JSON",
            f"Capability profile catalog {profile_path} is not valid JSON: {exc}",
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), list):
        raise UpgradeContractError(
            "PROFILE_CATALOG_INVALID_SHAPE",
            "Capability profile catalog must contain a profiles array.",
        )
    ids: set[str] = set()
    for profile in data["profiles"]:
        if not isinstance(profile, dict) or not isinstance(profile.get("profile_id"), str):
            raise UpgradeContractError(
                "PROFILE_CATALOG_INVALID_SHAPE",
                "Every capability profile must be an object with profile_id.",
            )
        profile_id = profile["profile_id"]
        if profile_id in ids:
            raise UpgradeContractError(
                "PROFILE_ID_DUPLICATE",
                f"Duplicate capability profile id: {profile_id}.",
            )
        ids.add(profile_id)
    return data


def _manifest_kinds(model: dict[str, object]) -> set[str]:
    result: set[str] = set()
    for manifest in model.get("manifests", []):
        if isinstance(manifest, dict) and isinstance(manifest.get("kind"), str):
            result.add(manifest["kind"])
    return result


def _all_paths(model: dict[str, object]) -> list[str]:
    paths: set[str] = set()
    for key in (
        "lockfiles",
        "config_files",
        "validators",
        "schemas",
        "examples",
        "generated_artifacts",
        "release_paths",
    ):
        value = model.get(key)
        if isinstance(value, list):
            paths.update(str(item) for item in value)
    for manifest in model.get("manifests", []):
        if isinstance(manifest, dict) and isinstance(manifest.get("path"), str):
            paths.add(manifest["path"])
    for workflow in model.get("workflows", []):
        if isinstance(workflow, dict) and isinstance(workflow.get("path"), str):
            paths.add(workflow["path"])
    return sorted(paths)


def _matches_rule(model: dict[str, object], rule: dict[str, object]) -> bool:
    languages = set(str(item) for item in model.get("languages", []))
    frameworks = set(str(item) for item in model.get("frameworks", []))
    archetypes = set(str(item) for item in model.get("repository_archetypes", []))
    manifest_kinds = _manifest_kinds(model)
    entry_points = model.get("entry_points", [])
    paths_text = "\n".join(_all_paths(model)).lower()

    checks: list[bool] = []
    for key, values, observed in (
        ("languages_any", rule.get("languages_any"), languages),
        ("frameworks_any", rule.get("frameworks_any"), frameworks),
        ("archetypes_any", rule.get("archetypes_any"), archetypes),
        ("manifest_kinds_any", rule.get("manifest_kinds_any"), manifest_kinds),
    ):
        if values is not None:
            if not isinstance(values, list):
                return False
            checks.append(bool(set(str(item) for item in values) & observed))
    if "entry_point_required" in rule:
        checks.append(bool(entry_points) is bool(rule["entry_point_required"]))
    if "path_tokens_any" in rule:
        values = rule["path_tokens_any"]
        if not isinstance(values, list):
            return False
        checks.append(any(str(token).lower() in paths_text for token in values))
    return all(checks) if checks else False


def detect_profiles(
    model: dict[str, object],
    catalog: dict[str, object],
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for profile in sorted(
        catalog["profiles"], key=lambda item: str(item.get("profile_id", ""))
    ):
        rule = profile.get("detect")
        if isinstance(rule, dict) and _matches_rule(model, rule):
            matches.append(
                {
                    "profile_id": profile["profile_id"],
                    "category": profile["category"],
                    "evidence": evidence(
                        "derived",
                        _all_paths(model),
                        "Profile matched explicit catalog detection rules against the repository model.",
                        confidence="medium",
                    ),
                }
            )
    return matches


def compose_profile_contributions(
    matches: Iterable[dict[str, object]],
    catalog: dict[str, object],
) -> dict[str, object]:
    by_id = {
        profile["profile_id"]: profile
        for profile in catalog["profiles"]
        if isinstance(profile, dict)
    }
    expected: set[str] = set()
    invariants: set[str] = set()
    failure_modes: set[str] = set()
    candidate_checks: set[str] = set()
    exclusions: set[str] = set()
    cost_notes: set[str] = set()
    selected_ids: list[str] = []

    for match in sorted(matches, key=lambda item: str(item["profile_id"])):
        profile_id = str(match["profile_id"])
        profile = by_id[profile_id]
        selected_ids.append(profile_id)
        expected.update(str(item) for item in profile.get("expected_capabilities", []))
        invariants.update(str(item) for item in profile.get("structural_invariants", []))
        failure_modes.update(str(item) for item in profile.get("common_failure_modes", []))
        candidate_checks.update(str(item) for item in profile.get("candidate_checks", []))
        exclusions.update(str(item) for item in profile.get("exclusions", []))
        note = profile.get("cost_noise")
        if isinstance(note, str):
            cost_notes.add(note)

    expected -= exclusions
    return {
        "profile_contract_version": catalog["profile_contract_version"],
        "selected_profiles": selected_ids,
        "expected_capabilities": sorted(expected),
        "structural_invariants": sorted(invariants),
        "common_failure_modes": sorted(failure_modes),
        "candidate_checks": sorted(candidate_checks),
        "exclusions": sorted(exclusions),
        "cost_noise_notes": sorted(cost_notes),
    }
