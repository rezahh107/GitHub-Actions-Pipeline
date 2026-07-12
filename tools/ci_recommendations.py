"""Independent recommendation channels with behavior-specific Phase 1 eligibility."""
from __future__ import annotations

from typing import Iterable

from tools.ci_ranking import derive_ranking, load_ranking_policy
from tools.ci_upgrade_models import DEEP_REPOSITORY_UPGRADE, MINIMAL_SAFE_CI, diagnostic

GENERIC_SUBSYSTEMS = {".", "root", "test", "tests", "example", "examples", "docs", ".github", "github", "ci"}


def _caps(model: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(item["capability_id"]): item for item in model.get("capabilities", []) if isinstance(item, dict) and item.get("capability_id")}


def _refs(model: dict[str, object], key: str) -> list[str]:
    return [str(item) for item in model.get(key, []) if isinstance(item, str)]


def _gap(*, failure: str, paths: Iterable[str], limitation: str, assertion: str, oracle: str, validation: Iterable[str], confirmed: bool) -> dict[str, object]:
    return {
        "failure_mode": failure,
        "affected_paths": sorted(set(str(path) for path in paths if path)),
        "existing_control_limitation": limitation,
        "missing_assertion": assertion,
        "proposed_oracle": oracle,
        "validation_plan": [str(step) for step in validation if step],
        "confirmed": confirmed,
    }


def _eligible(gap: dict[str, object], refs: list[str]) -> bool:
    return bool(gap.get("confirmed") and refs and gap.get("failure_mode") and gap.get("affected_paths") and gap.get("existing_control_limitation") and gap.get("missing_assertion") and gap.get("proposed_oracle") and gap.get("validation_plan"))


def _rec(rid: str, source: str, title: str, *, model: dict[str, object], cap: str | None, invariant: str, refs: Iterable[str], basis: str, gap: dict[str, object], confidence: str = "medium", steps: list[str] | None = None, code: str = "CAPABILITY_GAP", message: str = "Repository capability gap detected.", hint: str = "Implement the smallest proven oracle.", complexity_hint: int | None = None, reversibility_hint: int | None = None, maintainability_hint: int | None = None) -> dict[str, object]:
    references = sorted(set(str(item) for item in refs if item))
    implementation = steps or []
    state = str(_caps(model).get(cap, {}).get("state", "unknown")) if cap else "unknown"
    ranking = derive_ranking(source=source, capability_id=cap, capability_state=state, confidence=confidence, evidence_references=references, implementation_steps=implementation, policy=load_ranking_policy(), complexity_hint=complexity_hint, reversibility_hint=reversibility_hint, maintainability_hint=maintainability_hint)
    return {
        "recommendation_id": rid,
        "source": source,
        "title": title,
        "affected_capability": cap,
        "protected_invariant": invariant,
        "evidence": {"references": references, "basis": basis, "confidence": confidence},
        "oracle_gap": gap,
        "phase_1_eligible": _eligible(gap, references),
        "ranking": ranking,
        "implementation": implementation,
        "decision": "deferred",
        "diagnostic": diagnostic(code, message, affected_area=cap or "repository", evidence_references=references, repair_hint=hint),
    }


def observed_failure_recommendations(model: dict[str, object], history: dict[str, object], telemetry: dict[str, object]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    test_state = str(_caps(model).get("tests_run_on_pull_requests", {}).get("state", "unknown"))
    reverts = history.get("revert_chains", [])
    if isinstance(reverts, list) and reverts:
        refs = [str(item.get("commit_sha")) for item in reverts if isinstance(item, dict) and item.get("commit_sha")]
        out.append(_rec("OBS-REVERT-REGRESSION-ORACLE", "observed_failure", "Investigate reverted behavior before adding a regression oracle", model=model, cap="tests_run_on_pull_requests", invariant="Previously reversed behavior must not regress silently.", refs=refs, basis="Explicit reverts are direct historical events, but commit identity alone does not establish the unprotected behavior.", gap=_gap(failure="A revert indicates a prior failure, but its concrete behavior is unresolved.", paths=[], limitation="Existing coverage cannot be evaluated from commit identity alone.", assertion="Unknown until the reverted diff and tests are inspected.", oracle="No executable control is proposed before behavior identification.", validation=["Inspect the revert diff.", "Identify a reproducible invariant.", "Confirm existing tests miss it."], confirmed=False), confidence="medium", steps=["Inspect the revert and affected tests.", "Record the exact behavior and missing assertion.", "Add one regression oracle only after confirmation."], code="OBSERVED_REVERT_REQUIRES_BEHAVIOR_TRIAGE", message="Revert evidence requires behavior-specific triage before Phase 1.", hint="Identify the exact failure, affected path, missing assertion, and verification plan.", complexity_hint=2))

    repeated = history.get("repeated_fix_subsystems", [])
    if isinstance(repeated, list) and test_state not in {"operational", "operational_but_weak"}:
        for item in repeated[:3]:
            if not isinstance(item, dict):
                continue
            subsystem = str(item.get("subsystem") or "unknown")
            if subsystem.lower() in GENERIC_SUBSYSTEMS:
                continue
            paths = [str(value) for value in item.get("affected_paths", []) if value]
            failure = str(item.get("failure_mode") or "")
            assertion = str(item.get("missing_assertion") or "")
            limitation = str(item.get("existing_control_limitation") or "")
            validation = [str(value) for value in item.get("validation_plan", []) if value]
            confirmed = bool(failure and paths and assertion and limitation and validation)
            token = subsystem.replace("/", "-").replace(".", "root").upper()
            refs = [str(value) for value in item.get("commit_shas", []) if value] or [subsystem]
            out.append(_rec(f"OBS-REPEATED-FIX-{token}", "observed_failure", f"Investigate repeated fixes in {subsystem}", model=model, cap="tests_run_on_pull_requests", invariant=f"A concrete repeatedly repaired behavior in {subsystem} must remain stable.", refs=refs, basis=f"{int(item.get('fix_commit_count') or 0)} fix-oriented commits touched this subsystem; this is correlation until a missing oracle is established.", gap=_gap(failure=failure or f"Repeated-fix correlation in {subsystem}; concrete behavior unresolved.", paths=paths, limitation=limitation or "Subsystem correlation does not establish a control limitation.", assertion=assertion or "No missing assertion has been identified.", oracle=f"Add one targeted assertion for {failure}." if confirmed else "No control is proposed until behavior-specific evidence exists.", validation=validation or ["Inspect the cited fixes.", "Identify a reproducible failure.", "Compare it with existing coverage."], confirmed=confirmed), confidence="high" if confirmed else "low", steps=["Inspect bounded fix commits.", "Identify one reproducible failure mode.", "Add a regression oracle only if current controls miss it."], code="REPEATED_FIX_MISSING_ORACLE_CONFIRMED" if confirmed else "REPEATED_FIX_CORRELATION", message=f"Repeated fixes in {subsystem} are not sufficient for Phase 1 without a concrete missing oracle.", hint="Record the exact failure, path, existing-control limitation, assertion, and validation plan.", complexity_hint=2))

    failures = telemetry.get("recurring_failures", [])
    if isinstance(failures, list):
        for item in failures[:3]:
            if not isinstance(item, dict):
                continue
            workflow = str(item.get("workflow") or "unknown")
            out.append(_rec(f"OBS-WORKFLOW-FAILURE-{workflow.replace(' ', '-').upper()}", "observed_failure", f"Triage recurring workflow failures in {workflow}", model=model, cap="tests_run_on_pull_requests", invariant="A required validation path must execute consistently and fail actionably.", refs=[workflow], basis=f"Run telemetry recorded {int(item.get('failure_count') or 0)} unsuccessful runs; run-level correlation does not identify a missing product oracle.", gap=_gap(failure=f"Recurring unsuccessful runs in {workflow}.", paths=[], limitation="Run-level telemetry does not identify the failing step or invariant.", assertion="Unknown until job and step evidence is inspected.", oracle="Triage the failing job before proposing a control.", validation=["Inspect failed jobs and steps.", "Separate product failure from infrastructure noise.", "Confirm a missing machine-checkable assertion."], confirmed=False), confidence="medium", steps=["Inspect failing jobs and steps.", "Separate product failures from infrastructure failures.", "Repair or add an oracle only with direct evidence."], code="RECURRING_WORKFLOW_FAILURE_REQUIRES_TRIAGE", message=f"Workflow {workflow} has recurring failures but no behavior-specific oracle gap.", hint="Collect failing job/step evidence before promotion.", complexity_hint=2, reversibility_hint=2))
    return out


def structural_invariant_recommendations(model: dict[str, object]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    caps = _caps(model)
    workflows = [str(item.get("path")) for item in model.get("workflows", []) if isinstance(item, dict) and item.get("path")]

    item = caps.get("schema_validation")
    if item and item.get("state") in {"nominal", "partial", "absent"}:
        refs = _refs(model, "schemas") + _refs(model, "examples") + _refs(model, "validators")
        out.append(_rec("INV-SCHEMA-PRODUCER-COMPATIBILITY", "structural_invariant", "Connect schemas, examples, validators, and malformed fixtures", model=model, cap="schema_validation", invariant="Structured producers, examples, and validators must agree with the active closed schema.", refs=refs, basis="Contract surfaces exist but executable positive and mutation-negative compatibility is not proven.", gap=_gap(failure="Malformed or drifted contract objects can validate or reach consumers.", paths=refs, limitation="Existing schema validation is not operational across producer, examples, registries, and negative mutations.", assertion="Every canonical object must reject unknown, missing, malformed, duplicate, and mode-incompatible data.", oracle="Validate positive generated reports and mutation-negative fixtures against the closed schema.", validation=["Check the schema itself.", "Validate generated reports and registries.", "Mutate every major nested object and assert rejection."], confirmed=bool(refs)), confidence="high" if len(refs) >= 2 else "medium", steps=["Use one deterministic schema validator.", "Validate positive examples and generated reports.", "Add mutation-negative fixtures with instance paths."], code="SCHEMA_COMPATIBILITY_NOT_OPERATIONAL", message="Canonical contract compatibility is not proven operational.", hint="Connect all contract surfaces to closed-schema positive and negative validation.", complexity_hint=2, maintainability_hint=3))

    item = caps.get("tests_run_on_pull_requests")
    if item and item.get("state") in {"nominal", "partial", "absent"}:
        refs = [str(value) for value in model.get("test_suites", {}).get("files", [])] + workflows
        out.append(_rec("INV-TESTS-EXECUTED-ON-PR", "structural_invariant", "Execute the repository's resolved test command on pull requests", model=model, cap="tests_run_on_pull_requests", invariant="Changes must not merge without executing the deterministic behavioral oracle.", refs=refs, basis="Tests or workflows exist, but pull-request execution of a bounded resolved test invocation was not proven.", gap=_gap(failure="Changes can reach review without behavioral tests executing.", paths=refs, limitation="No pull-request workflow contains a bounded resolved test invocation.", assertion="The canonical repository test command must exit successfully for every pull request.", oracle="Invoke one unambiguous canonical test command from a least-privilege workflow.", validation=["Run the generated workflow in a temporary repository.", "Verify the command executes rather than appears as text.", "Confirm failure blocks the stable job."], confirmed=bool(refs)), confidence="high" if refs else "medium", steps=["Resolve one canonical test command.", "Run it on pull_request with least privilege.", "Tie failures to the component or test."], code="TESTS_NOT_PROVEN_IN_PULL_REQUEST_CI", message="The test suite is not proven operational on pull requests.", hint="Use a recipe only when one unambiguous command and component are resolved.", complexity_hint=1, reversibility_hint=3))

    item = caps.get("reproducible_dependency_install")
    if item and item.get("state") in {"partial", "absent"} and model.get("manifests"):
        refs = _refs(model, "lockfiles") + [str(value.get("path")) for value in model.get("manifests", []) if isinstance(value, dict)]
        out.append(_rec("INV-REPRODUCIBLE-INSTALL", "structural_invariant", "Make dependency installation reproducible", model=model, cap="reproducible_dependency_install", invariant="CI must install the declared dependency graph, not a drifting approximation.", refs=refs, basis="A lockfile-enforcing install path was not proven.", gap=_gap(failure="Dependency resolution can drift between runs.", paths=refs, limitation="A lockfile and resolved frozen install invocation are not both connected to CI.", assertion="A clean-checkout install must consume the canonical lock contract.", oracle="Use the ecosystem-native frozen install command and fail on drift.", validation=["Install from a clean checkout.", "Verify lockfile enforcement.", "Reject manifest/lock mismatch."], confirmed=bool(refs)), confidence="medium", steps=["Use the existing lockfile.", "Choose the native frozen install command.", "Report manifest and lock paths on inconsistency."], code="DEPENDENCY_INSTALL_NOT_REPRODUCIBLE", message="Dependency installation may drift.", hint="Enforce the ecosystem lockfile in CI.", complexity_hint=2))

    item = caps.get("build_verified")
    if item and item.get("state") == "nominal":
        refs = [str(value.get("path")) for value in model.get("manifests", []) if isinstance(value, dict)]
        out.append(_rec("INV-BUILD-VERIFICATION", "structural_invariant", "Execute the declared build in CI", model=model, cap="build_verified", invariant="A declared build must remain executable from a clean checkout.", refs=refs, basis="A build script or backend exists but bounded CI execution was not proven.", gap=_gap(failure="The declared build may fail after tests pass.", paths=refs, limitation="No bounded resolved build invocation is connected to CI.", assertion="A clean-checkout build must complete through the declared build entry.", oracle="Invoke the existing build entry after deterministic installation.", validation=["Install deterministically.", "Execute the declared build.", "Verify successful exit and expected artifact behavior."], confirmed=bool(refs)), confidence="high", steps=["Invoke the existing build.", "Do not duplicate build logic in YAML.", "Report component and command on failure."], code="DECLARED_BUILD_NOT_VERIFIED", message="A declared build was not proven to run in CI.", hint="Wire the declared build command into pull-request validation.", complexity_hint=1))
    return out


def baseline_capability_recommendations(model: dict[str, object], profiles: dict[str, object]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    caps = _caps(model)
    profile_ids = list(profiles.get("selected_profiles", []))
    conflicts = {str(item.get("capability_id")) for item in profiles.get("profile_conflicts", []) if isinstance(item, dict)}
    for capability_id in profiles.get("expected_capabilities", []):
        capability_id = str(capability_id)
        if capability_id in conflicts:
            continue
        item = caps.get(capability_id)
        state = str(item.get("state")) if item else "unknown"
        if state in {"operational", "not_applicable"}:
            continue
        refs = list(profile_ids)
        if item and isinstance(item.get("evidence"), dict):
            refs += [str(value) for value in item["evidence"].get("references", [])]
        out.append(_rec(f"BASE-{capability_id.replace('_', '-').upper()}", "baseline_capability", f"Establish baseline capability: {capability_id}", model=model, cap=capability_id, invariant=f"Detected profiles expect {capability_id} unless evidence excludes it.", refs=refs, basis=f"Profiles {profile_ids} expect this capability; current state is {state}.", gap=_gap(failure=f"Profile-required capability {capability_id} is {state}.", paths=refs, limitation=f"Current state {state} does not prove operational execution.", assertion=f"A deterministic assertion must transition {capability_id} to operational or establish an exclusion.", oracle=f"Implement the smallest profile-appropriate executable oracle for {capability_id}.", validation=["Run a positive fixture.", "Run a negative or no-op fixture.", "Verify the deterministic capability transition."], confirmed=bool(refs)), confidence="medium" if profile_ids else "low", steps=["Confirm the executable oracle.", "Implement an operational control, not a nominal file.", "Add a negative or no-op case."], code="BASELINE_CAPABILITY_GAP", message=f"Profiles expect {capability_id}, but its state is {state}.", hint=f"Implement and test operational {capability_id}, or record an evidence-based exclusion.", complexity_hint=2))
    return out


def assign_decisions(items: list[dict[str, object]], *, mode: str, max_phase_1_items: int) -> list[dict[str, object]]:
    ordered = sorted(items, key=lambda item: (-int(item["ranking"]["ordinal_total"]), str(item["source"]), str(item["recommendation_id"])))
    used = 0
    for item in ordered:
        band = item["ranking"]["priority_band"]
        confidence = item["evidence"]["confidence"]
        eligible = bool(item.get("phase_1_eligible"))
        if not eligible and item["source"] == "observed_failure":
            item["decision"] = "deferred"
        elif mode == MINIMAL_SAFE_CI and item["source"] == "baseline_capability":
            item["decision"] = "deferred"
        elif eligible and band == "high" and confidence in {"high", "medium"} and used < max_phase_1_items:
            item["decision"] = "phase_1"
            used += 1
        elif band in {"high", "medium"} or (band == "low" and mode == DEEP_REPOSITORY_UPGRADE):
            item["decision"] = "phase_2"
        else:
            item["decision"] = "deferred"
    return ordered


def generate_recommendations(model: dict[str, object], history: dict[str, object], telemetry: dict[str, object], profile_contributions: dict[str, object], *, mode: str, max_phase_1_items: int) -> dict[str, object]:
    observed = observed_failure_recommendations(model, history, telemetry)
    structural = structural_invariant_recommendations(model)
    baseline = baseline_capability_recommendations(model, profile_contributions) if mode == DEEP_REPOSITORY_UPGRADE else []
    ranked = assign_decisions([*observed, *structural, *baseline], mode=mode, max_phase_1_items=max_phase_1_items)
    return {"observed_failures": [item for item in ranked if item["source"] == "observed_failure"], "structural_invariants": [item for item in ranked if item["source"] == "structural_invariant"], "baseline_capabilities": [item for item in ranked if item["source"] == "baseline_capability"], "ranked": ranked}
