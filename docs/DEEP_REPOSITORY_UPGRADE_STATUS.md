# Deep Repository Upgrade Status

Tracker version: `1.1.0`  
Target repository version: `0.3.0`  
Current report schema: `schemas/repository_upgrade_report.v1.1.schema.json`  
Legacy report schema: `schemas/repository_upgrade_report.v1.schema.json`

Status vocabulary:

```text
not_started
in_progress
implemented_unverified
verified
deferred_with_reason
blocked_with_evidence
not_applicable
```

## Requirement traceability

| Workstream | Status | Implementation | Verification |
|---|---|---|---|
| Two-mode architecture | verified | `ci_upgrade_models.py`, `ci_upgrade_engine.py` | mode-separation tests |
| Repository model | verified | `ci_repository_model.py` | nominal/operational and workspace tests |
| Bounded semantic resolution | verified | `ci_semantic_analysis.py` | AST import, route, entry-point, and source/test tests |
| Workflow/package command resolution | verified | `ci_semantic_analysis.py` | execution-graph tests |
| Capability classification | verified | `ci_repository_model.py` | operational-state tests |
| Evidence-rich profiles | verified | `ci_profiles.py` | matched-signal tests |
| Conflict-aware profile composition | verified | `ci_profiles.py` | expected/excluded conflict test |
| Structural history | verified | `ci_history_analysis.py` | temporary real-Git fixture |
| Optional telemetry | verified | `ci_telemetry.py` | unavailable and fake-transport tests |
| Three recommendation channels | verified | `ci_recommendations.py` | channel and cold-start tests |
| Ranking v1.1 | verified | `ci_ranking.py`, `ranking-policy.v1.json` | policy, rationale, determinism, malformed tests |
| Staged deep plan | verified | `ci_upgrade_engine.py` | deep schema and phase tests |
| Dry-run implementation package | verified | `ci_implementation_engine.py` | applicable/blocked recipe tests |
| Exact-HEAD allowlisted application | verified | `ci_implementation_engine.py`, CLI | temporary Git apply, dirty-tree, and head-mismatch tests |
| Review-only profile evolution | verified | `ci_outcome_registry.py`, `profile_evolution.py` | threshold and deterministic no-auto-mutation tests |
| Contract evolution | verified | legacy `1.0.0` retained; new `1.1.0` added | old examples plus generated v1.1 reports |
| Documentation | implemented_unverified | README, AGENTS, architecture, protocol, prompt, changelog | repository CI checks files; semantic completeness remains review-based |

## Verification evidence

Targeted local validation before repository write:

```text
python -m unittest tests.test_repository_upgrade_hardening -v
Ran 9 tests
OK

python -m py_compile tools/*.py
exit code 0
```

The complete repository suite and report generation are executed by GitHub Actions. Exact-head SHA and workflow-run evidence are maintained in pull request `#8`; embedding them here would create a new head and immediately stale the claim.

## Backward compatibility

- `ci_detective` remains `0.1.1`;
- legacy upgrade report `1.0.0` and its examples remain valid;
- new reports use `1.1.0`;
- Minimal Safe CI remains the default;
- mutation is opt-in and unavailable in Minimal Safe CI;
- no automatic profile-registry mutation exists.

## Known limitations

- semantic parsing currently covers Python AST and declarative package scripts, not JavaScript/TypeScript ASTs or runtime call graphs;
- dynamic imports, reflection, dependency injection, generated-code semantics, and network behavior remain unresolved;
- source-to-test is resolved only when a test imports a local Python module; other relationships remain inferred;
- generated-source relationships require declarative evidence;
- structural Git analysis remains bounded to 200 commits;
- telemetry is run-level and does not yet normalize per-job logs;
- implementation recipes intentionally cover only narrow, versioned, preconditioned changes;
- implementation validation commands are not automatically executed because repository code is untrusted;
- profile evolution proposals require human review and do not prove causality.

## Intentionally deferred

| Item | Status | Reason |
|---|---|---|
| JavaScript/TypeScript AST analyzer | deferred_with_reason | requires a separate versioned parser contract and fixtures |
| Dynamic runtime architecture discovery | deferred_with_reason | would exceed deterministic static evidence boundaries |
| Per-job log intelligence | deferred_with_reason | requires additional API volume, identity, and privacy contracts |
| Arbitrary patch synthesis | deferred_with_reason | unsupported changes must not be represented as executable recipes |
| Automatic registry learning | deferred_with_reason | hidden self-modification conflicts with determinism and reviewability |
| Breaking replacement of legacy contracts | deferred_with_reason | parallel schemas preserve existing consumers |

## Next safe continuation step

Review pull request `#8` and its exact-head workflow evidence. Merge remains a human decision. A later slice may add one versioned JavaScript/TypeScript semantic analyzer or another narrowly proven implementation recipe, but not both without separate fixtures and measurement.
