"""Mode policies, capability evaluation, recommendation sources, and staged ranking."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

STATES = (
    "absent", "nominal", "partial", "operational", "operational_but_weak",
    "unknown", "not_applicable",
)
LEVEL = {"low": 0, "medium": 1, "high": 2, "critical": 3}
EVIDENCE = {"low": 0, "medium": 1, "high": 2}
COST = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class ModePolicy:
    mode: str
    include_baseline_capabilities: bool
    maximum_phase1_items: int
    allow_testability_changes: bool
    minimum_evidence: str


MODE_POLICIES = {
    "minimal-safe-ci": ModePolicy("minimal-safe-ci", False, 3, False, "high"),
    "deep-repository-upgrade": ModePolicy("deep-repository-upgrade", True, 4, True, "medium"),
}


def load_profiles(profile_root: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(profile_root.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"PROFILE_INVALID: {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"PROFILE_INVALID: {path}: expected an object")
        result.append(value)
    return result


def select_profiles(model: dict[str, Any], profiles: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    ecosystems = {
        item for component in model.get("components", [])
        for item in component.get("ecosystems", [])
    }
    archetypes = set(model.get("archetypes", []))
    selected = []
    for profile in profiles:
        match = profile.get("match", {})
        if (
            match.get("always") is True
            or ecosystems.intersection(match.get("ecosystems_any", []))
            or archetypes.intersection(match.get("archetypes_any", []))
        ):
            selected.append(profile)
    return sorted(selected, key=lambda item: item["profile_id"])


def _commands(model: dict[str, Any]) -> list[str]:
    return [
        command.lower()
        for workflow in model.get("workflows", [])
        for command in workflow.get("commands", [])
    ]


def _triggers(model: dict[str, Any]) -> set[str]:
    return {
        trigger
        for workflow in model.get("workflows", [])
        for trigger in workflow.get("triggers", [])
    }


def _contains(values: Iterable[str], tokens: Iterable[str]) -> bool:
    text = "\n".join(values).lower()
    return any(token.lower() in text for token in tokens)


def _all(model: dict[str, Any], field: str) -> list[str]:
    return [
        value for component in model.get("components", [])
        for value in component.get(field, [])
    ]


def _archetype(model: dict[str, Any], *names: str) -> bool:
    return bool(set(model.get("archetypes", [])).intersection(names))


def _tests_on_pr(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    tests, declared = _all(model, "test_files"), _all(model, "test_commands")
    if not tests and not declared:
        return "absent", ["No test files or declared test commands were detected."], []
    evidence = [*[f"test file: {p}" for p in tests[:10]], *[f"declared test command: {c}" for c in declared]]
    runs = _contains(_commands(model), (
        "pytest", "unittest", "npm test", "npm run test", "pnpm test", "yarn test",
        "go test", "cargo test", "mvn test", "gradle test", "dotnet test",
    ))
    if runs and "pull_request" in _triggers(model):
        return "operational", evidence + ["A pull_request workflow executes a recognized test command."], []
    if runs:
        return "partial", evidence, ["Test execution exists, but pull_request coverage was not detected."]
    return "nominal", evidence, ["Tests exist, but recognized CI execution was not detected."]


def _build(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    declared = _all(model, "build_commands")
    if not declared and not _all(model, "manifests"):
        return "not_applicable", [], []
    runs = _contains(_commands(model), (
        "npm run build", "pnpm build", "yarn build", "go build", "cargo build",
        "python -m build", "mvn package", "gradle build", "dotnet build",
    ))
    evidence = [f"declared build command: {c}" for c in declared]
    if runs and "pull_request" in _triggers(model):
        return "operational", evidence + ["Build execution detected on pull requests."], []
    if runs:
        return "partial", evidence, ["Build execution exists without detected pull_request coverage."]
    return "absent", evidence, ["No recognized CI build or package verification was detected."]


def _least_privilege(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    workflows = model.get("workflows", [])
    if not workflows:
        return "not_applicable", [], []
    evidence, weak = [], []
    for workflow in workflows:
        permissions = workflow.get("permissions", {})
        evidence.append(f"{workflow['path']}: permissions={permissions or 'implicit'}")
        if not permissions:
            weak.append(f"{workflow['path']} has no explicit parsed permissions")
        if any(value == "write" for value in permissions.values()):
            weak.append(f"{workflow['path']} grants write permission")
    return ("operational_but_weak", evidence, weak) if weak else ("operational", evidence, [])


def _dependencies(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    components = [c for c in model.get("components", []) if c.get("manifests")]
    if not components:
        return "not_applicable", [], []
    evidence = [
        f"{c['component_id']}: manifests={c['manifests']}, lockfiles={c['lockfiles']}"
        for c in components
    ]
    missing = [
        c["component_id"] for c in components
        if not c.get("lockfiles")
        and set(c.get("ecosystems", [])).intersection({"node", "python", "rust", "php", "ruby"})
    ]
    if missing:
        return "absent", evidence, [f"No lockfile detected for component {item}." for item in missing]
    if _contains(_commands(model), (
        "npm ci", "--frozen-lockfile", "uv sync --frozen", "cargo build --locked",
        "bundle install --deployment",
    )):
        return "operational", evidence + ["A lock-enforcing install command was detected in CI."], []
    return "nominal", evidence, ["Lockfiles exist, but lock-enforcing CI installation was not detected."]


def _static(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if not _all(model, "source_files"):
        return "not_applicable", [], []
    if _contains(_commands(model), (
        "ruff", "flake8", "pylint", "mypy", "pyright", "eslint", "tsc",
        "go vet", "golangci-lint", "cargo clippy", "cargo fmt",
    )):
        return "operational", ["A recognized static validation command is executed by CI."], []
    return "absent", [], ["No operational static validation capability was detected."]


def _schema(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    schemas, validators = _all(model, "schemas"), _all(model, "validators")
    if not schemas:
        return "not_applicable", [], []
    evidence = [*[f"schema: {p}" for p in schemas[:20]], *[f"validator: {p}" for p in validators[:20]]]
    if not validators:
        return "absent", evidence, ["Schemas exist without a detected validator."]
    if _contains(_commands(model), ("validate", "schema", "jsonschema")):
        return "operational", evidence + ["Schema-related CI execution was detected."], []
    return "partial", evidence, ["A validator exists, but CI execution could not be established."]


def _negative(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if not (_all(model, "schemas") or _archetype(model, "python-api-service", "python-django-application")):
        return "not_applicable", [], []
    tests = _all(model, "test_files")
    negative = [p for p in tests if any(t in p.lower() for t in ("invalid", "negative", "malformed", "reject", "error"))]
    if negative and _tests_on_pr(model)[0] == "operational":
        return "operational", [f"negative test or fixture: {p}" for p in negative], []
    if negative:
        return "nominal", [f"negative test or fixture: {p}" for p in negative], [
            "Negative cases exist but pull-request CI execution was not established."
        ]
    if tests:
        return "partial", [f"test file: {p}" for p in tests[:10]], ["No explicit invalid/rejection case was detected."]
    return "absent", [], ["No negative validation cases were detected."]


def _api(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if not _archetype(model, "python-api-service", "python-django-application", "node-service"):
        return "not_applicable", [], []
    tests = [p for p in _all(model, "test_files") if any(t in p.lower() for t in ("api", "route", "endpoint", "client", "request"))]
    if tests and _tests_on_pr(model)[0] == "operational":
        return "operational", [f"API-oriented test: {p}" for p in tests], []
    if tests:
        return "nominal", [f"API-oriented test: {p}" for p in tests], ["API tests exist without proven CI execution."]
    return "absent", [], ["No deterministic API contract test was detected."]


def _data(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if not _archetype(model, "python-data-pipeline", "python-ml-service"):
        return "not_applicable", [], []
    schemas, validators = _all(model, "schemas"), _all(model, "validators")
    evidence = [*[f"schema: {p}" for p in schemas], *[f"validator: {p}" for p in validators]]
    if schemas and validators and _tests_on_pr(model)[0] == "operational":
        return "operational", evidence, []
    if evidence:
        return "partial", evidence, ["Data contract evidence exists without proven operational CI validation."]
    return "absent", [], ["No data input/output contract validator was detected."]


def _worker(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if not _archetype(model, "python-async-worker"):
        return "not_applicable", [], []
    tests = [p for p in _all(model, "test_files") if any(t in p.lower() for t in ("worker", "retry", "idempot", "task"))]
    if tests and _tests_on_pr(model)[0] == "operational":
        return "operational", [f"worker contract test: {p}" for p in tests], []
    if tests:
        return "nominal", [f"worker contract test: {p}" for p in tests], ["Worker tests lack proven CI execution."]
    return "absent", [], ["No retry, idempotency, or worker failure-contract tests were detected."]


def _component_coverage(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    components, commands = model.get("components", []), _commands(model)
    if len(components) < 2:
        return "not_applicable", [], []
    uncovered = [
        c["component_id"] for c in components
        if c["root"] != "." and not any(c["root"].lower() in command for command in commands)
    ]
    evidence = [f"component: {c['component_id']}" for c in components]
    if not uncovered and commands:
        return "operational", evidence, []
    if commands:
        return "partial", evidence, [f"No component-specific CI evidence for: {', '.join(uncovered)}"]
    return "absent", evidence, ["Multiple components exist without operational CI command coverage."]


def _docs(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if not _archetype(model, "documentation-only-repository"):
        return "not_applicable", [], []
    if _contains(_commands(model), ("markdownlint", "linkcheck", "lychee", "mkdocs build", "sphinx-build")):
        return "operational", ["Documentation validation command detected in CI."], []
    return "absent", [], ["No machine-checkable documentation validation was detected."]


def _package_release(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if not _archetype(model, "python-package"):
        return "not_applicable", [], []
    evidence = _all(model, "release_files")
    if _contains(_commands(model), ("python -m build", "twine check")):
        return "operational", evidence + ["Distribution validation executes in CI."], []
    return "absent", evidence, ["No Python distribution build and metadata validation was detected."]


def _artifact(model: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if not _archetype(model, "python-data-pipeline", "python-ml-service"):
        return "not_applicable", [], []
    generated, locks = _all(model, "generated_artifacts"), _all(model, "lockfiles")
    if generated and locks:
        return "partial", [f"generated artifact: {p}" for p in generated], [
            "Artifacts and a lock exist, but input/metadata reproducibility was not proven."
        ]
    if locks:
        return "nominal", ["A dependency lockfile exists."], ["Generated artifact provenance was not detected."]
    return "absent", [], ["No reproducible artifact evidence was detected."]


def _unknown(message: str) -> tuple[str, list[str], list[str]]:
    return "unknown", [], [message]


DETECTORS: dict[str, Callable[[dict[str, Any]], tuple[str, list[str], list[str]]]] = {
    "workflow_least_privilege": _least_privilege,
    "tests_on_pull_request": _tests_on_pr,
    "build_verification": _build,
    "frontend_build_verification": _build,
    "dependency_reproducibility": _dependencies,
    "static_validation": _static,
    "schema_validation": _schema,
    "negative_validation_cases": _negative,
    "api_contract_validation": _api,
    "data_contract_validation": _data,
    "worker_contract_tests": _worker,
    "component_ci_coverage": _component_coverage,
    "documentation_validation": _docs,
    "package_release_verification": _package_release,
    "artifact_reproducibility": _artifact,
    "cross_repository_contract": lambda model: _unknown("Sibling-repository evidence requires connector-fed input."),
}


def evaluate_capabilities(model: dict[str, Any], profiles: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen, result = set(), []
    archetypes = set(model.get("archetypes", []))
    for profile in profiles:
        for item in profile.get("capabilities", []):
            capability_id = item["capability_id"]
            applies = set(item.get("applies_to_archetypes", []))
            if capability_id in seen or (applies and not applies.intersection(archetypes)):
                continue
            seen.add(capability_id)
            detector = DETECTORS.get(item["detector"])
            state, evidence, limitations = (
                detector(model) if detector else _unknown(f"No detector is registered for {item['detector']}.")
            )
            if state not in STATES:
                raise ValueError(f"CAPABILITY_STATE_INVALID: {capability_id}: {state}")
            result.append({
                "capability_id": capability_id,
                "name": item["name"],
                "state": state,
                "importance": item["importance"],
                "evidence": evidence,
                "limitations": limitations,
                "source_profile": profile["profile_id"],
                "recommendation": item["recommendation"],
                "phase_hint": item["phase_hint"],
                "implementation_cost": item["cost"],
                "noise_risk": item["noise_risk"],
            })
    return sorted(result, key=lambda item: item["capability_id"])


def _band(ranking: dict[str, str]) -> str:
    criticality, risk = LEVEL[ranking["invariant_criticality"]], LEVEL[ranking["risk_reduction"]]
    detection, silent = LEVEL[ranking["regression_detection_value"]], LEVEL[ranking["silent_failure_exposure"]]
    evidence = EVIDENCE[ranking["evidence_strength"]]
    cost, noise = COST[ranking["implementation_complexity"]], COST[ranking["noise_risk"]]
    if criticality >= 2 and risk >= 2 and evidence >= 1 and silent >= 2:
        return "critical"
    if risk >= 2 and detection >= 2 and evidence >= 1 and cost <= 1 and noise <= 1:
        return "high"
    if risk >= 1 and evidence >= 1 and ranking["overlap_with_existing_controls"] != "high":
        return "medium"
    return "low"


def _rec(
    recommendation_id: str, source: str, title: str, problem: str, evidence: list[str],
    action: str, *, capability_id: str | None = None, importance: str = "high",
    evidence_strength: str = "high", cost: str = "low", noise: str = "low",
    testability: bool = False,
) -> dict[str, Any]:
    ranking = {
        "risk_reduction": "high" if importance in {"critical", "high"} else "medium",
        "invariant_criticality": importance,
        "regression_detection_value": "high",
        "silent_failure_exposure": "high" if importance in {"critical", "high"} else "medium",
        "evidence_strength": evidence_strength,
        "maintainability_improvement": "high",
        "implementation_complexity": cost,
        "execution_time": "low",
        "noise_risk": noise,
        "ongoing_maintenance_cost": cost,
        "reversibility": "high",
        "overlap_with_existing_controls": "low",
    }
    return {
        "recommendation_id": recommendation_id,
        "source": source,
        "capability_id": capability_id,
        "title": title,
        "problem": problem,
        "evidence": evidence,
        "action": action,
        "testability_change": testability,
        "ranking": {**ranking, "priority_band": _band(ranking)},
    }


def build_recommendations(
    model: dict[str, Any],
    capabilities: list[dict[str, Any]],
    history: dict[str, Any],
    policy: ModePolicy,
) -> list[dict[str, Any]]:
    result, number = [], 1
    for item in history.get("repeated_fix_subsystems", [])[:5]:
        result.append(_rec(
            f"REC-{number:03d}", "observed_failure",
            f"Protect repeatedly repaired subsystem: {item['subsystem']}",
            f"The subsystem appears in {item['fix_commit_count']} bounded fix-related commits.",
            [f"repeated_fix_subsystems: {item}"],
            "Identify the repeated invariant, strengthen its deterministic test, and wire it into pull-request CI.",
            evidence_strength=item["evidence_strength"], cost="medium", noise="medium", testability=True,
        ))
        number += 1

    untested = history.get("production_changes_without_tests", [])
    if len(untested) >= 2:
        result.append(_rec(
            f"REC-{number:03d}", "observed_failure",
            "Audit recurring production changes without adjacent test changes",
            f"{len(untested)} recent commits changed production sources without adjacent test-file changes.",
            [f"{i['commit_sha']}: {i['source_files'][:5]}" for i in untested[:10]],
            "Map critical source paths to tests and add missing behavioral contracts only where the mapping confirms a gap.",
            importance="medium", evidence_strength="high" if len(untested) >= 5 else "medium",
            cost="medium", noise="medium", testability=True,
        ))
        number += 1

    schema_state = next((c["state"] for c in capabilities if c["capability_id"] == "schema_validation"), "unknown")
    for component in model.get("components", []):
        if component.get("schemas") and schema_state != "operational":
            result.append(_rec(
                f"REC-{number:03d}", "structural_invariant",
                f"Protect schema contracts in component {component['component_id']}",
                "Committed schemas can drift from validators and examples without a proven CI oracle.",
                [*[f"schema: {p}" for p in component["schemas"][:10]], *[f"validator: {p}" for p in component["validators"][:10]]],
                "Execute schema validity, example conformance, and invalid-fixture rejection in pull-request CI.",
                capability_id="schema_validation", testability=True,
            ))
            number += 1
        versions = [p for p in component.get("release_files", []) if Path(p).name in {"VERSION", "CHANGELOG.md"}]
        if component.get("manifests") and versions:
            result.append(_rec(
                f"REC-{number:03d}", "structural_invariant",
                f"Prevent version-source drift in component {component['component_id']}",
                "Package metadata and repository version sources can diverge silently.",
                [*[f"manifest: {p}" for p in component["manifests"]], *[f"version source: {p}" for p in versions]],
                "Add one deterministic version-consistency validator and run it on pull requests and release preparation.",
                importance="medium",
            ))
            number += 1

    if policy.include_baseline_capabilities:
        for capability in capabilities:
            if capability["state"] in {"operational", "not_applicable"}:
                continue
            result.append(_rec(
                f"REC-{number:03d}", "baseline_capability",
                f"Close capability gap: {capability['name']}",
                f"Capability state is {capability['state']}.",
                capability["evidence"] or capability["limitations"],
                capability["recommendation"],
                capability_id=capability["capability_id"],
                importance=capability["importance"],
                evidence_strength="medium" if capability["state"] == "unknown" else "high",
                cost=capability["implementation_cost"],
                noise=capability["noise_risk"],
                testability=capability["capability_id"] in {
                    "tests_on_pull_request", "negative_validation_cases", "schema_validation",
                    "api_contract_validation", "data_contract_validation", "worker_contract_tests",
                },
            ))
            number += 1

    source_order = {"observed_failure": 0, "structural_invariant": 1, "baseline_capability": 2}
    deduped, seen = [], set()
    for item in sorted(result, key=lambda i: (source_order[i["source"]], i.get("capability_id") or i["recommendation_id"])):
        key = item.get("capability_id")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(item)

    if policy.mode == "minimal-safe-ci":
        deduped = [
            item for item in deduped
            if item["source"] != "baseline_capability"
            and EVIDENCE[item["ranking"]["evidence_strength"]] >= EVIDENCE[policy.minimum_evidence]
            and item["ranking"]["priority_band"] in {"critical", "high"}
            and (policy.allow_testability_changes or not item["testability_change"])
        ]

    priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(deduped, key=lambda i: (priority[i["ranking"]["priority_band"]], source_order[i["source"]], i["recommendation_id"]))


def build_staged_plan(recommendations: list[dict[str, Any]], policy: ModePolicy) -> dict[str, Any]:
    phase1, phase2 = [], []
    for item in recommendations:
        if len(phase1) < policy.maximum_phase1_items and item["ranking"]["priority_band"] in {"critical", "high"}:
            phase1.append({
                "recommendation_id": item["recommendation_id"],
                "objective": item["action"],
                "validation": [
                    "Run the relevant deterministic command.",
                    "Verify the exact tested SHA.",
                    "Confirm diagnostics identify the affected invariant or capability.",
                ],
            })
        else:
            phase2.append({
                "recommendation_id": item["recommendation_id"],
                "objective": item["action"],
                "reconsider_when": "After Phase 1 evidence is available or when the affected component changes.",
            })
    rejected = [] if recommendations else [{
        "candidate": "unjustified-upgrade",
        "reason": "No recommendation met the active mode's evidence and leverage policy.",
    }]
    return {
        "phase_1": phase1,
        "phase_2": phase2 if policy.mode == "deep-repository-upgrade" else [],
        "rejected_or_intentionally_uncovered": rejected,
    }


def summarize_baseline(model: dict[str, Any], capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {state: 0 for state in STATES}
    for item in capabilities:
        counts[item["state"]] += 1
    return {
        "component_count": len(model.get("components", [])),
        "workflow_count": len(model.get("workflows", [])),
        "archetypes": model.get("archetypes", []),
        "capability_state_counts": counts,
        "operational_capabilities": [c["capability_id"] for c in capabilities if c["state"] == "operational"],
        "gaps": [c["capability_id"] for c in capabilities if c["state"] not in {"operational", "not_applicable"}],
    }
