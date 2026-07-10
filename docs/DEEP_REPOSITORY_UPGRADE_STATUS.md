# Deep Repository Upgrade Status

Tracker version: `1.0.0`  
Target repository version: `0.2.0`  
Canonical report schema: `schemas/repository_upgrade_report.v1.schema.json`

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

| # | Workstream | Status | Implementation | Verification |
|---:|---|---|---|---|
| 1 | Two-mode architecture | verified | `tools/ci_upgrade_models.py`, `tools/ci_upgrade_engine.py`, `tools/repository_upgrade.py` | `test_modes_are_explicit_and_output_contracts_are_separate` |
| 2 | Repository model | verified | `tools/ci_repository_model.py` | repository-model capability-state tests |
| 3 | Deeper collector | verified | manifest, TOML/JSON/YAML, workflow, command, component, schema/test/release collectors | `test_repository_model_distinguishes_nominal_from_operational` |
| 4 | Workflow telemetry | verified | `tools/ci_telemetry.py`; optional API or offline snapshot; explicit fallback | telemetry fake-transport and unavailable tests |
| 5 | Evidence mining beyond keywords | verified | `tools/ci_history_analysis.py` | real temporary-Git fixture covers reverts, co-change, production-without-test, and repeated fixes |
| 6 | Three recommendation sources | verified | `tools/ci_recommendations.py` | channel assertions and schema enum |
| 7 | Cold-start handling | verified | `tools/ci_upgrade_engine.py::_cold_start_state` | cold-start fixture test |
| 8 | Composable profiles | verified | `profiles/capability-profiles.v1.json`, `tools/ci_profiles.py` | profile schema and composition tests |
| 9 | Deep audit protocol | verified | `prompts/05-deep-repository-upgrade.md`, `deep_audit` output | deep mode schema test |
| 10 | High-leverage ranking | verified | bounded ordinal model in `tools/ci_upgrade_models.py` | ranking determinism and malformed-factor test |
| 11 | Capability-gap analysis | verified | capability states in `tools/ci_repository_model.py` | nominal-versus-operational test |
| 12 | Broader implementation protocol | verified | `pipeline/09-deep-repository-upgrade.md` and staged recommendations | report contract and documentation |
| 13 | Staged upgrade plan | verified | `staged_upgrade` output | deep report schema validation |
| 14 | Schema and contract evolution | verified | three v1 schemas; old `0.1.1` contract retained | positive and negative schema tests |
| 15 | Actionable diagnostics | verified | diagnostic contract and repair hints | `test_diagnostics_are_repair_oriented` |
| 16 | Measurement and validation | verified | deterministic/hash/schema/mode/cold-start/telemetry tests | `tests/test_repository_upgrade*.py` |
| 17 | Repository memory and traceability | verified | this file | direct content inspection plus CI artifact generation |
| 18 | Documentation | implemented_unverified | README, AGENTS, architecture, prompt, protocol, changelog | files are exercised by repository CI, but semantic documentation completeness is not automatically proven |

## Verification evidence

Executed locally before repository write:

```text
python -m unittest tests.test_repository_upgrade tests.test_repository_upgrade_schemas -v
Ran 20 tests
OK
```

GitHub Actions also executes the complete repository suite, generates the legacy report plus both new operating-mode reports, checks Scope Claim Audit examples, and uploads the report artifacts.

The exact head SHA, workflow run ID, and final conclusion are maintained in pull request `#8`. They are not embedded here because changing this file creates a new head SHA and would make an embedded exact-head claim self-referential and immediately stale.

## Backward compatibility

- `tools/ci_detective.py` unchanged.
- `schemas/ci_detective_report.schema.json` remains report `0.1.1`.
- new behavior is opt-in through `tools/repository_upgrade.py`;
- default new-mode selection is `minimal-safe-ci`;
- new report contract is version `1.0.0`.

## Known limitations

- framework detection is manifest-based and cannot prove runtime behavior;
- source-to-test mapping is explicitly `inferred`;
- generated-source relationships are not resolved without declarative evidence;
- Git structural analysis is bounded to 200 commits;
- telemetry run collection does not yet retrieve per-job step logs;
- co-change and repeated-fix evidence are correlations, not causal conclusions;
- exact workflow flakiness classification remains unavailable without repeated telemetry and stable job identity.

## Intentionally deferred

| Item | Status | Reason |
|---|---|---|
| Automatic per-job log collection | deferred_with_reason | adds API volume and permissions complexity; run-level telemetry is the safe first contract |
| Ecosystem-specific AST parsing | deferred_with_reason | current deterministic manifest/config model provides useful coverage without a tool-heavy architecture |
| Automatic repository modification from recommendations | deferred_with_reason | recommendation and implementation authorization remain separate safety boundaries |
| Breaking replacement of `ci_detective` | deferred_with_reason | backward compatibility is preserved by parallel versioned contracts |

## Next safe continuation step

Review pull request `#8` and its exact-head workflow evidence. Merge remains a human decision; this repository automation must not merge or enable auto-merge.
