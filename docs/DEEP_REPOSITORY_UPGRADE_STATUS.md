# Deep Repository Upgrade — Implementation Status

Canonical implementation target: `0.2.0`

Starting main SHA: `ddfc70ab8ed8278e369b191f24a5934e1c281b0e`

Working branch: `feat/deep-repository-upgrade-v0-2`

Status vocabulary: `not_started`, `in_progress`, `implemented_unverified`, `verified`, `deferred_with_reason`, `blocked_with_evidence`, `not_applicable`.

| Workstream | Status | Implementation | Evidence / limitation |
|---|---|---|---|
| Two-mode architecture | verified | `tools/upgrade_engine.py`, `tools/repository_upgrade.py` | Unit tests cover explicit mode separation and minimal-mode empty Phase 2. |
| Structured repository model | verified | `tools/repository_model.py` | Tests cover manifest-aware FastAPI detection and multi-component separation. |
| Deeper collector | verified | `tools/repository_model.py` | Parses JSON/TOML manifests, lockfiles, test/build commands, bounded workflow structure. Dynamic execution remains explicitly unresolved. |
| Workflow telemetry | implemented_unverified | `--telemetry-json` input in `tools/repository_upgrade.py` | Connector collection is intentionally external; local fallback is `not_collected`. |
| Evidence mining beyond keywords | verified | `tools/deep_git_evidence.py` | Tests prove source changes without adjacent test files are detected. Correlation guards are preserved. |
| Three recommendation sources | verified | `tools/upgrade_engine.py` | Sources are `observed_failure`, `structural_invariant`, and `baseline_capability`. |
| Cold-start handling | verified | Deep-mode tests | Baseline recommendations are emitted without historical failures; minimal mode remains conservative. |
| Composable profiles | verified | `profiles/*.json`, `schemas/capability_profile.schema.json` | Generic, Python, API, data/ML, worker, Node, frontend, service, monorepo, browser extension, schema, docs, and multi-repo profiles validate. |
| Deep audit protocol | verified | `pipeline/09-repository-capability-audit.md`, `prompts/05-deep-repository-upgrade.md` | Prompt and executable CLI agree. |
| High-leverage ranking | verified | `tools/upgrade_engine.py` | Bounded ordinal dimensions and deterministic priority bands; no fake decimal precision. |
| Capability-gap analysis | verified | `evaluate_capabilities` | States distinguish absent, nominal, partial, operational, weak, unknown, and not applicable. |
| Broader implementation protocol | implemented_unverified | Deep-mode staged actions | The report authorizes bounded testability work; automated patch generation is not yet part of this slice. |
| Staged upgrade plan | verified | `build_staged_plan` | Phase 1, Phase 2, and intentionally uncovered/rejected sections are schema-valid. |
| Schema evolution | verified | `schemas/repository_upgrade_report.schema.json` | Closed nested contracts, mode conditionals, profile schema, positive and negative tests. |
| Actionable diagnostics | verified | Capability limitations and CLI stable error prefix | Tests cover operational-vs-nominal diagnostics; further per-ecosystem wording can be expanded. |
| Measurement and validation | verified | Unit and schema tests; exact-head GitHub Actions | Workflow run `29103743326` succeeded on implementation head `28c8a300a6c68750e03feca9c434d7730c722343`; every validation and artifact step passed. |
| Durable memory | verified | This file | Update after each implementation slice and exact-head validation. |
| Documentation | verified | README, overview, protocol, prompt, changelog | Included in the successful exact-head workflow validation on implementation head `28c8a300a6c68750e03feca9c434d7730c722343`. |

## Implemented files

- `tools/repository_model.py`
- `tools/deep_git_evidence.py`
- `tools/upgrade_engine.py`
- `tools/repository_upgrade.py`
- `profiles/*.json`
- `schemas/capability_profile.schema.json`
- `schemas/repository_upgrade_report.schema.json`
- `examples/repository_upgrade.*.example.json`
- `tests/test_repository_upgrade.py`
- `tests/test_upgrade_schemas.py`
- `pipeline/09-repository-capability-audit.md`
- `prompts/05-deep-repository-upgrade.md`

## Intentionally deferred

- Direct connector/API collection of workflow telemetry inside the local CLI. The CLI accepts connector-fed telemetry without making authentication mandatory.
- Automatic implementation of arbitrary Phase 1 patches. The current slice produces executable, evidence-based objectives; repository-specific patching remains an agent operation.
- Full YAML semantic evaluation, dynamic imports, runtime framework introspection, and production credentials.
- Empirical risk-reduction percentages. The system uses explicit bounded ordinal judgments instead.

## Next safe continuation step

Pilot deep mode against several materially different target repositories and add only evidence-backed detector/profile refinements. The implementation head passed GitHub Actions run `29103743326`; this evidence-only status update must also remain green on the final PR head.
