# Deep Repository Upgrade Status

Tracker version: `1.2.0`  
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

`verified` requires an executed command and result on the relevant exact source head. A unit test alone does not verify repository-wide enforcement.

## Requirement traceability

| Workstream | Status | Implementation | Verification |
|---|---|---|---|
| Two-mode architecture | verified | `ci_upgrade_models.py`, `ci_upgrade_engine.py` | Existing mode-separation suite and prior exact-head CI evidence |
| Repository model | implemented_unverified | `ci_repository_model.py` | Final exact-head suite pending after adversarial command/permission refactor |
| Bounded semantic resolution | implemented_unverified | `ci_semantic_analysis.py` | Final exact-head suite pending; unresolved workflow text is no longer emitted as an executable node |
| Bounded executable-command evidence (`PRF-001`) | implemented_unverified | `ci_command_evidence.py`, collectors, model | Local adversarial harness passed; complete repository suite and final CI pending |
| Effective workflow/job permissions (`PRF-002`) | implemented_unverified | `ci_repository_collectors.py`, `ci_repository_model.py` | Missing/empty/override/malformed adversarial cases added; final CI pending |
| Closed report contract `1.1.0` (`PRF-003`) | implemented_unverified | `repository_upgrade_report.v1.1.schema.json` | Draft-07 schema check and mutation-negative tests added; generated-report CI pending |
| Exact-head outcome trust boundary (`PRF-004`) | implemented_unverified | `ci_outcome_registry.py`, `repository_outcomes.v1.schema.json` | Invalid SHA, duplicate/conflict, head mismatch, threshold tests added; final CI pending |
| Phase 1 oracle eligibility (`PRF-005`) | implemented_unverified | `ci_recommendations.py` | Generic correlation and duplicate-control regressions added; final CI pending |
| Recoverable mutation and persistence (`PRF-006`) | implemented_unverified | `ci_implementation_engine.py`, `ci_transaction.py`, CLI, recovery schema | Boundary failure injection and rollback/recovery tests added; final CI pending |
| Exact workflow summary identity (`PRF-007`) | implemented_unverified | `render_workflow_summary.sh`, `validate.yml` | Executed shell regression added; final workflow artifact evidence pending |
| Evidence-rich profiles | verified | `ci_profiles.py` | Existing matched-signal tests and prior exact-head CI evidence |
| Conflict-aware profile composition | verified | `ci_profiles.py` | Existing expected/excluded conflict test and prior exact-head CI evidence |
| Structural history | verified | `ci_history_analysis.py` | Existing temporary real-Git fixture and prior exact-head CI evidence |
| Optional telemetry | verified | `ci_telemetry.py` | Existing unavailable/fake-transport tests and prior exact-head CI evidence |
| Ranking v1.1 | implemented_unverified | `ci_ranking.py`, `ranking-policy.v1.json`, recommendation eligibility | Deterministic ordinal tests retained; final eligibility suite pending |
| Staged deep plan | implemented_unverified | `ci_upgrade_engine.py`, closed staged schema | Generated deep report validation pending on final exact head |
| Dry-run implementation package | implemented_unverified | `ci_implementation_engine.py`, closed implementation action schema | Generated package and successful temporary apply pending final CI |
| Review-only profile evolution | implemented_unverified | `ci_outcome_registry.py`, `profile_evolution.py` | Complete schema-valid registry trust boundary pending final CI |
| Contract evolution | implemented_unverified | legacy `1.0.0` retained; closed `1.1.0` and recovery journal added | Legacy examples plus generated current reports pending final CI |
| Documentation synchronization | implemented_unverified | README, changelog, `PR8_REPAIR_EVIDENCE.md`, this tracker | Independent re-inspection and final exact-head CI pending |

## Executed validation available before final CI

A local isolated harness containing the newly authored boundaries was executed:

```text
python -m py_compile <authored Python modules>
exit code 0

Draft7Validator.check_schema(repository_upgrade_report.v1.1.schema.json)
result: valid schema; 66 reusable definitions

PYTHONPATH=/mnt/data/pr8_repair \
  python -m unittest /mnt/data/pr8_repair/tests/test_repository_upgrade_adversarial.py -q
Ran 24 tests
OK

bash -n tools/render_workflow_summary.sh
exit code 0
```

This is targeted development evidence, not the complete repository suite. The authoritative repository validation commands remain:

```bash
python -m py_compile tools/*.py
python -m unittest discover -s tests
```

The final PR source head, checked-out/tested SHA, workflow run, generated artifacts, and digests must be recorded in the PR after GitHub Actions completes. Embedding those identities in this tracked file would create a new head and immediately stale the claim.

## Backward compatibility

- `ci_detective` remains `0.1.1`;
- legacy upgrade report `1.0.0` and its examples remain valid;
- current reports remain independently versioned as `1.1.0`;
- Minimal Safe CI remains the default;
- Deep Mode and mutation remain explicit opt-in;
- no automatic profile or recipe registry mutation exists;
- no repository command is executed by the generic implementation engine;
- exact expected HEAD and clean worktree remain mandatory;
- report, package, result, and recovery journal stay outside the target repository during mutation.

## Known limitations

- the command-evidence parser intentionally does not emulate full shell semantics;
- semantic parsing covers Python AST and declarative package scripts, not JavaScript/TypeScript ASTs or runtime call graphs;
- dynamic imports, reflection, dependency injection, generated-code semantics, and network behavior remain unresolved;
- source-to-test is resolved only when a test imports a local Python module; other relationships remain inferred;
- generated-source relationships require declarative evidence;
- structural Git analysis remains bounded to 200 commits;
- telemetry is run-level and does not yet normalize per-job logs;
- implementation recipes intentionally cover only narrow, versioned, preconditioned create-file changes;
- implementation validation commands are not automatically executed because repository code is untrusted;
- profile evolution proposals require human review and do not prove causality.

## Intentionally deferred

| Item | Status | Reason |
|---|---|---|
| Full Bash/PowerShell execution semantics | deferred_with_reason | unsafe and non-deterministic without a separately versioned analyzer/runtime contract |
| JavaScript/TypeScript AST analyzer | deferred_with_reason | requires a separate versioned parser contract and fixtures |
| Dynamic runtime architecture discovery | deferred_with_reason | exceeds deterministic static evidence boundaries |
| Per-job log intelligence | deferred_with_reason | requires additional API volume, identity, and privacy contracts |
| Arbitrary patch synthesis | deferred_with_reason | unsupported changes must not be represented as executable recipes |
| Automatic registry learning | deferred_with_reason | hidden self-modification conflicts with determinism and reviewability |
| Breaking replacement of legacy contracts | deferred_with_reason | parallel schemas preserve existing consumers |

## Next safe continuation step

Wait for GitHub Actions on the final exact PR source head, inspect all failing or successful jobs and artifacts, update the PR description without changing the source head, and request an independent PR Inspector rerun. Merge remains a human decision.
