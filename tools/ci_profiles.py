"""Composable capability-profile loading and evidence-gated domain detection."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from tools.ci_upgrade_models import UpgradeContractError, diagnostic, evidence

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "profiles" / "capability-profiles.v1.json"
_AUTHORITATIVE_CRITERIA = {"languages_any", "frameworks_any", "archetypes_any", "manifest_kinds_any", "entry_point_required", "semantic_signals_any"}
_CODE_SUFFIXES = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".php", ".cs"}
_CODE_MANIFESTS = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "requirements-dev.txt", "requirements-test.txt", "package.json", "Cargo.toml", "go.mod", "pom.xml", "build.gradle"}


def load_profiles(path: Path | None = None) -> dict[str, object]:
    source = path or DEFAULT_PATH
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UpgradeContractError("PROFILE_CATALOG_UNAVAILABLE", f"Could not read capability profile catalog {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UpgradeContractError("PROFILE_CATALOG_INVALID_JSON", f"Capability profile catalog {source} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), list):
        raise UpgradeContractError("PROFILE_CATALOG_INVALID_SHAPE", "Capability profile catalog must contain a profiles array.")
    ids: set[str] = set()
    for profile in data["profiles"]:
        if not isinstance(profile, dict) or not isinstance(profile.get("profile_id"), str):
            raise UpgradeContractError("PROFILE_CATALOG_INVALID_SHAPE", "Every capability profile must contain profile_id.")
        if profile["profile_id"] in ids:
            raise UpgradeContractError("PROFILE_ID_DUPLICATE", f"Duplicate capability profile id: {profile['profile_id']}.")
        ids.add(profile["profile_id"])
    return data


def _all_paths(model: dict[str, object]) -> list[str]:
    result = {str(item) for item in model.get("path_index", []) if isinstance(item, str)}
    for key in ("lockfiles", "config_files", "validators", "schemas", "examples", "generated_artifacts", "release_paths"):
        value = model.get(key)
        if isinstance(value, list):
            result.update(str(item) for item in value)
    for key in ("manifests", "workflows"):
        for item in model.get(key, []) if isinstance(model.get(key), list) else []:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                result.add(item["path"])
    semantic = model.get("semantic_model", {})
    if isinstance(semantic, dict):
        for collection in ("signals", "nodes"):
            for item in semantic.get(collection, []) if isinstance(semantic.get(collection), list) else []:
                if isinstance(item, dict) and isinstance(item.get("source"), str):
                    result.add(item["source"])
    return sorted(result)


def _manifest_refs(model: dict[str, object], kind: str | None = None, dependency_token: str | None = None) -> list[str]:
    refs: list[str] = []
    for item in model.get("manifests", []) if isinstance(model.get("manifests"), list) else []:
        if not isinstance(item, dict):
            continue
        if kind and item.get("kind") != kind:
            continue
        if dependency_token and dependency_token.lower() not in "\n".join(str(value).lower() for value in item.get("dependencies", [])):
            continue
        if item.get("path"):
            refs.append(str(item["path"]))
    return sorted(set(refs))


def _criterion(key: str, requested: list[object], observed: set[str], refs: dict[str, list[str]]) -> dict[str, object]:
    values = sorted(str(item) for item in requested)
    matched = sorted(set(values) & observed)
    references = sorted({reference for value in matched for reference in refs.get(value, [])})
    return {"criterion": key, "requested": values, "matched": matched, "references": references, "satisfied": bool(matched)}


def _is_code_bearing_path(path: str) -> bool:
    candidate = Path(path)
    return candidate.suffix.lower() in _CODE_SUFFIXES or candidate.name in _CODE_MANIFESTS


def _path_token_signal(paths: list[str], values: list[object]) -> dict[str, object]:
    tokens = sorted(str(item) for item in values)
    all_matches = sorted({path for path in paths if any(token.lower() in path.lower() for token in tokens)})
    code_matches = sorted(path for path in all_matches if _is_code_bearing_path(path))
    return {"criterion": "path_tokens_any", "requested": tokens, "matched": code_matches, "references": code_matches, "supporting_references": all_matches, "satisfied": bool(code_matches), "authority": "supporting_only"}


def _evaluate_rule(model: dict[str, object], rule: dict[str, object]) -> tuple[bool, list[dict[str, object]]]:
    languages = {str(item) for item in model.get("languages", [])}
    frameworks = {str(item) for item in model.get("frameworks", [])}
    archetypes = {str(item) for item in model.get("repository_archetypes", [])}
    manifest_kinds = {str(item.get("kind")) for item in model.get("manifests", []) if isinstance(item, dict)}
    paths = _all_paths(model)
    entry_points = model.get("entry_points", [])
    semantic = model.get("semantic_model", {})
    semantic_signals = {str(item.get("signal_type")) for item in semantic.get("signals", []) if isinstance(semantic, dict) and isinstance(item, dict)}
    language_refs = {language: [path for path in paths if Path(path).suffix.lower() in {extension for extension, name in {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".php": "PHP", ".go": "Go", ".rs": "Rust", ".java": "Java", ".rb": "Ruby", ".cs": "C#"}.items() if name == language}] for language in languages}
    framework_refs = {framework: _manifest_refs(model, dependency_token=framework.lower().replace(".js", "")) for framework in frameworks}
    archetype_refs = {archetype: _manifest_refs(model) if archetype in {"python", "javascript-typescript", "monorepo"} else [*model.get("schemas", [])] if archetype == "contract-schema" else paths for archetype in archetypes}
    kind_refs = {kind: _manifest_refs(model, kind=kind) for kind in manifest_kinds}
    signal_refs = {signal: sorted(str(item.get("source")) for item in semantic.get("signals", []) if isinstance(semantic, dict) and isinstance(item, dict) and item.get("signal_type") == signal and item.get("source")) for signal in semantic_signals}
    checks: list[dict[str, object]] = []
    for key, observed, refs in (("languages_any", languages, language_refs), ("frameworks_any", frameworks, framework_refs), ("archetypes_any", archetypes, archetype_refs), ("manifest_kinds_any", manifest_kinds, kind_refs), ("semantic_signals_any", semantic_signals, signal_refs)):
        if key in rule:
            values = rule[key]
            if not isinstance(values, list):
                return False, []
            signal = _criterion(key, values, observed, refs)
            signal["authority"] = "authoritative"
            checks.append(signal)
    if "entry_point_required" in rule:
        required = bool(rule["entry_point_required"])
        present = bool(entry_points)
        references = sorted(str(item.get("source")) for item in entry_points if isinstance(item, dict) and item.get("source"))
        checks.append({"criterion": "entry_point_required", "requested": [required], "matched": [present] if present == required else [], "references": references, "satisfied": present == required, "authority": "authoritative"})
    if "path_tokens_any" in rule:
        values = rule["path_tokens_any"]
        if not isinstance(values, list):
            return False, []
        checks.append(_path_token_signal(paths, values))
    if not checks or not all(bool(item["satisfied"]) for item in checks):
        return False, checks
    if "path_tokens_any" in rule and not any(item.get("authority") == "authoritative" and item.get("satisfied") for item in checks):
        return False, checks
    return True, checks


def _effective_rule(profile: dict[str, object]) -> dict[str, object] | None:
    raw = profile.get("detect")
    if not isinstance(raw, dict):
        return None
    rule = dict(raw)
    if "path_tokens_any" in rule and not any(key in rule for key in _AUTHORITATIVE_CRITERIA):
        category = str(profile.get("category", ""))
        if category == "python":
            rule["languages_any"] = ["Python"]
        elif category == "javascript-typescript":
            rule["languages_any"] = ["JavaScript", "TypeScript"]
        else:
            rule["manifest_kinds_any"] = ["pyproject", "package_json", "setup.py", "setup.cfg", "Cargo.toml", "go.mod", "pom.xml", "build.gradle"]
    return rule


def detect_profiles(model: dict[str, object], catalog: dict[str, object]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for profile in sorted(catalog["profiles"], key=lambda item: str(item.get("profile_id", ""))):
        rule = _effective_rule(profile)
        if rule is None:
            continue
        matched, signals = _evaluate_rule(model, rule)
        if not matched:
            continue
        references = sorted({reference for signal in signals for reference in signal.get("references", [])})
        authoritative = [signal for signal in signals if signal.get("authority") == "authoritative" and signal.get("satisfied")]
        independent = len([signal for signal in signals if signal.get("satisfied")])
        confidence = "high" if len(authoritative) >= 2 or any(signal["criterion"] == "semantic_signals_any" for signal in authoritative) else "medium"
        public_signals = [{key: signal[key] for key in ("criterion", "requested", "matched", "references", "satisfied")} for signal in signals]
        matches.append({"profile_id": profile["profile_id"], "category": profile["category"], "matched_signals": public_signals, "evidence": evidence("derived", references, "Profile matched every effective criterion, including at least one independent authoritative criterion; path tokens are supporting evidence only.", confidence=confidence if independent else "low")})
    return matches


def profile_candidate_diagnostics(model: dict[str, object], catalog: dict[str, object], matches: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    selected = {str(item.get("profile_id")) for item in matches if isinstance(item, dict)}
    diagnostics: list[dict[str, object]] = []
    for profile in sorted(catalog.get("profiles", []), key=lambda item: str(item.get("profile_id", "")) if isinstance(item, dict) else ""):
        if not isinstance(profile, dict) or str(profile.get("profile_id")) in selected:
            continue
        rule = _effective_rule(profile)
        if rule is None or "path_tokens_any" not in rule:
            continue
        _, signals = _evaluate_rule(model, rule)
        path_signal = next((item for item in signals if item.get("criterion") == "path_tokens_any"), None)
        if not path_signal or not path_signal.get("supporting_references"):
            continue
        authoritative = [item for item in signals if item.get("authority") == "authoritative"]
        if authoritative and all(item.get("satisfied") for item in authoritative) and path_signal.get("satisfied"):
            continue
        diagnostics.append(diagnostic("PROFILE_PATH_ONLY_CANDIDATE", f"Path-name correlation suggested profile {profile.get('profile_id')!r}, but authoritative language, manifest, framework, entry-point, or semantic evidence did not establish the domain profile.", affected_area="profile_detection", evidence_references=[str(item) for item in path_signal.get("supporting_references", [])], repair_hint="Treat the path match as an inspection candidate; add or observe independent authoritative repository evidence before selecting this profile.", severity="info"))
    return diagnostics


def compose_profile_contributions(matches: Iterable[dict[str, object]], catalog: dict[str, object]) -> dict[str, object]:
    by_id = {profile["profile_id"]: profile for profile in catalog["profiles"] if isinstance(profile, dict)}
    selected: list[str] = []
    invariants: set[str] = set()
    failures: set[str] = set()
    checks: set[str] = set()
    notes: set[str] = set()
    expected_by: dict[str, set[str]] = {}
    excluded_by: dict[str, set[str]] = {}
    for match in sorted(matches, key=lambda item: str(item["profile_id"])):
        profile_id = str(match["profile_id"])
        profile = by_id[profile_id]
        selected.append(profile_id)
        invariants.update(str(item) for item in profile.get("structural_invariants", []))
        failures.update(str(item) for item in profile.get("common_failure_modes", []))
        checks.update(str(item) for item in profile.get("candidate_checks", []))
        if isinstance(profile.get("cost_noise"), str):
            notes.add(str(profile["cost_noise"]))
        for capability in profile.get("expected_capabilities", []):
            expected_by.setdefault(str(capability), set()).add(profile_id)
        for capability in profile.get("exclusions", []):
            excluded_by.setdefault(str(capability), set()).add(profile_id)
    contributions: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    expected: list[str] = []
    exclusions: list[str] = []
    for capability in sorted(set(expected_by) | set(excluded_by)):
        expecters = sorted(expected_by.get(capability, set()))
        excluders = sorted(excluded_by.get(capability, set()))
        if expecters and excluders:
            resolution = "conflict"
            conflicts.append({"capability_id": capability, "expected_by": expecters, "excluded_by": excluders, "resolution": "unresolved"})
        elif expecters:
            resolution = "expected"
            expected.append(capability)
        else:
            resolution = "excluded"
            exclusions.append(capability)
        contributions.append({"capability_id": capability, "expected_by": expecters, "excluded_by": excluders, "resolution": resolution})
    return {"profile_contract_version": catalog["profile_contract_version"], "selected_profiles": selected, "expected_capabilities": expected, "structural_invariants": sorted(invariants), "common_failure_modes": sorted(failures), "candidate_checks": sorted(checks), "exclusions": exclusions, "cost_noise_notes": sorted(notes), "capability_contributions": contributions, "profile_conflicts": conflicts}


def profile_conflict_diagnostics(composition: dict[str, object]) -> list[dict[str, object]]:
    return [diagnostic("PROFILE_CAPABILITY_CONFLICT", f"Capability {item['capability_id']} is expected and excluded by different matched profiles.", affected_area="profile_composition", evidence_references=[*item["expected_by"], *item["excluded_by"]], repair_hint="Refine profile detection or add a versioned precedence/exclusion rule before using this capability for recommendations.") for item in composition.get("profile_conflicts", []) if isinstance(item, dict)]
